"""Unit tests for the docs-drift gate (blueprintx#1233)."""

import functools
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest


_BIN = Path(__file__).resolve().parents[2] / "bin"
STR_TASKS = '[tool.poe.tasks.lint]\ncmd = "ruff check"\n'
STR_COUPLING = "couplings:\n  - source: pyproject.toml\n    docs: [README.md]\n"


def _load(str_name: str) -> ModuleType:
    """Load a ``bin/`` script by path (``bin/`` is not a package).

    Parameters
    ----------
    str_name : str
        Module stem under ``bin/``.

    Returns
    -------
    ModuleType
        The imported module.
    """
    cls_spec = importlib.util.spec_from_file_location(str_name, _BIN / f"{str_name}.py")
    assert cls_spec is not None
    assert cls_spec.loader is not None
    cls_module = importlib.util.module_from_spec(cls_spec)
    sys.modules[str_name] = cls_module
    cls_spec.loader.exec_module(cls_module)
    return cls_module


gate = _load("check_docs_drift")


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide the developer's Git configuration from every fixture and checker command.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest's environment patcher.
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _write(tuple_item: tuple, *, path_root: Path) -> None:
    """Write one ``(relative path, content)`` pair under ``path_root``.

    Parameters
    ----------
    tuple_item : tuple
        The relative path and the file content.
    path_root : pathlib.Path
        Project root.
    """
    path_file = path_root / tuple_item[0]
    path_file.parent.mkdir(parents=True, exist_ok=True)
    path_file.write_text(tuple_item[1], encoding="utf-8")


def _project(path_root: Path, *, str_readme: str, str_all: str = "", str_ref: str = "") -> Path:
    """Write a minimal project under ``path_root``.

    Parameters
    ----------
    path_root : pathlib.Path
        Project root.
    str_readme : str
        ``README.md`` content.
    str_all : str
        Body of ``src/pkg/__init__.py``, skipped when empty.
    str_ref : str
        ``docs/api/reference.md`` content, skipped when empty.

    Returns
    -------
    pathlib.Path
        ``path_root``.
    """
    dict_files = {
        "poe_tasks.toml": STR_TASKS,
        "README.md": str_readme,
        "src/pkg/__init__.py": str_all,
        "docs/api/reference.md": str_ref,
    }
    list(
        map(
            functools.partial(_write, path_root=path_root),
            filter(lambda tuple_item: tuple_item[1], dict_files.items()),
        )
    )
    return path_root


def _verdict(path_root: Path, *, capsys: pytest.CaptureFixture, list_flags: tuple = ()) -> tuple:
    """Run the gate's ``main`` on a project and return its exit status and report.

    Parameters
    ----------
    path_root : pathlib.Path
        Project root.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    list_flags : tuple
        Extra command-line arguments.

    Returns
    -------
    tuple
        The exit status and everything the gate printed.
    """
    int_code = gate.main(["--root", str(path_root), *list_flags])
    return int_code, capsys.readouterr().out


def _git(path_root: Path, *list_args: str) -> None:
    """Run a git command in ``path_root``.

    Parameters
    ----------
    path_root : pathlib.Path
        Repository root.
    *list_args : str
        Arguments after ``git``.
    """
    subprocess.run(  # noqa: S603 -- constant argv
        ["git", "-C", str(path_root), "-c", "user.name=dev", "-c", "user.email=d@e.f", *list_args],  # noqa: S607
        check=True,
        capture_output=True,
    )


def test_a_defined_task_in_a_fence_passes(
    tmp_path: Path, *, capsys: pytest.CaptureFixture
) -> None:
    """A cited task the project defines is not drift.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(tmp_path, str_readme="```bash\npoe lint\n```\n")
    assert _verdict(path_root, capsys=capsys)[0] == 0


def test_an_undefined_task_in_a_fence_fails(
    tmp_path: Path, *, capsys: pytest.CaptureFixture
) -> None:
    """Should-fail witness: a code block cites a task that does not exist.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(tmp_path, str_readme="```bash\npoe offline_only\n```\n")
    int_code, str_out = _verdict(path_root, capsys=capsys)
    assert (int_code, "README.md: poe offline_only is not defined" in str_out) == (1, True)


def test_an_undefined_task_in_an_inline_span_fails(
    tmp_path: Path, *, capsys: pytest.CaptureFixture
) -> None:
    """Should-fail witness: an inline code span cites a task that does not exist.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(tmp_path, str_readme="Run `poe ghost` first.\n")
    int_code, str_out = _verdict(path_root, capsys=capsys)
    assert (int_code, "README.md: poe ghost is not defined" in str_out) == (1, True)


def test_an_inline_span_wrapping_across_lines_is_read(
    tmp_path: Path, *, capsys: pytest.CaptureFixture
) -> None:
    """Should-fail witness: a span broken over two source lines renders as one.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(tmp_path, str_readme="Run `poe\nghost` first.\n")
    int_code, str_out = _verdict(path_root, capsys=capsys)
    assert (int_code, "README.md: poe ghost is not defined" in str_out) == (1, True)


def test_a_longer_fence_is_not_closed_by_a_shorter_one(
    tmp_path: Path, *, capsys: pytest.CaptureFixture
) -> None:
    """Should-fail witness: three backticks inside a four-backtick block are content.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(tmp_path, str_readme="````md\n```\npoe ghost\n```\n````\n")
    int_code, str_out = _verdict(path_root, capsys=capsys)
    assert (int_code, "README.md: poe ghost is not defined" in str_out) == (1, True)


def test_a_shell_comment_in_a_fence_is_not_a_citation(
    tmp_path: Path, *, capsys: pytest.CaptureFixture
) -> None:
    """A ``# ... poe ...`` comment in a code block is prose, not a command.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(
        tmp_path,
        str_readme="```bash\nbash bin/venv.sh   # poe lives inside it\n# poe ghost\n```\n",
    )
    assert _verdict(path_root, capsys=capsys)[0] == 0


def test_prose_after_a_closed_fence_is_not_a_citation(
    tmp_path: Path, *, capsys: pytest.CaptureFixture
) -> None:
    """Only code is read, so prose below the real closing fence is ignored.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(tmp_path, str_readme="````md\n```\n````\nWe use poe the poet.\n")
    assert _verdict(path_root, capsys=capsys)[0] == 0


def test_an_export_missing_from_the_reference_fails(
    tmp_path: Path, *, capsys: pytest.CaptureFixture
) -> None:
    """Should-fail witness: a name in ``__all__`` the API page never mentions.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(
        tmp_path, str_readme="x\n", str_all='__all__ = ["Shown", "Hidden"]\n', str_ref="`Shown`\n"
    )
    int_code, str_out = _verdict(path_root, capsys=capsys)
    assert (int_code, "reference.md: Hidden is in __all__" in str_out) == (1, True)


def test_an_annotated_all_is_read(tmp_path: Path, *, capsys: pytest.CaptureFixture) -> None:
    """Should-fail witness: ``__all__: list[str] = [...]`` is an ``AnnAssign``, not an ``Assign``.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(
        tmp_path,
        str_readme="x\n",
        str_all='__all__: list[str] = ["Hidden"]\n',
        str_ref="nothing\n",
    )
    int_code, str_out = _verdict(path_root, capsys=capsys)
    assert (int_code, "reference.md: Hidden is in __all__" in str_out) == (1, True)


def test_an_export_in_a_table_row_passes(tmp_path: Path, *, capsys: pytest.CaptureFixture) -> None:
    """Any word-bounded mention counts, so a table row documents the name.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(
        tmp_path, str_readme="x\n", str_all='__all__ = ["Shown"]\n', str_ref="| `Shown` | a |\n"
    )
    assert _verdict(path_root, capsys=capsys)[0] == 0


def test_a_dunder_export_needs_no_reference_entry(
    tmp_path: Path, *, capsys: pytest.CaptureFixture
) -> None:
    """``__version__`` is metadata, not an API symbol.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(
        tmp_path, str_readme="x\n", str_all='__all__ = ["__version__"]\n', str_ref="page\n"
    )
    assert _verdict(path_root, capsys=capsys)[0] == 0


def test_all_without_a_reference_page_fails(
    tmp_path: Path, *, capsys: pytest.CaptureFixture
) -> None:
    """Should-fail witness: an export list with no page to document it.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(tmp_path, str_readme="x\n", str_all='__all__ = ["A"]\n')
    int_code, str_out = _verdict(path_root, capsys=capsys)
    assert (int_code, "reference.md does not exist" in str_out) == (1, True)


def test_a_root_with_no_pages_fails(tmp_path: Path, *, capsys: pytest.CaptureFixture) -> None:
    """Should-fail witness: discovery finding nothing is a failure, never a pass.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    int_code, str_out = _verdict(tmp_path, capsys=capsys)
    assert (int_code, "nothing was checked" in str_out) == (1, True)


def test_a_clean_run_prints_the_page_count(
    tmp_path: Path, *, capsys: pytest.CaptureFixture
) -> None:
    """A passing run names how many pages it read.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _project(tmp_path, str_readme="`poe lint`\n")
    assert "1 page(s)" in _verdict(path_root, capsys=capsys)[1]


def _repo_with_change(
    path_root: Path,
    *,
    str_message: str,
    str_coupling: str = STR_COUPLING,
    str_author: str = "dev <d@e.f>",
) -> Path:
    """Build a repo whose ``feature`` branch edits ``pyproject.toml`` but not the README.

    Parameters
    ----------
    path_root : pathlib.Path
        Repository root.
    str_message : str
        Commit message of the source change.
    str_coupling : str
        Content of ``.docs-coupling.yaml``.
    str_author : str
        ``Name <email>`` author of the source change.

    Returns
    -------
    pathlib.Path
        ``path_root``.
    """
    _project(path_root, str_readme="x\n")
    (path_root / ".docs-coupling.yaml").write_text(str_coupling, encoding="utf-8")
    (path_root / "pyproject.toml").write_text("a\n", encoding="utf-8")
    _git(path_root, "init", "-q", "-b", "main")
    _git(path_root, "add", ".")
    _git(path_root, "commit", "-q", "-m", "base")
    _git(path_root, "checkout", "-q", "-b", "feature")
    (path_root / "pyproject.toml").write_text("b\n", encoding="utf-8")
    _git(path_root, "commit", "-q", "-am", str_message, "--author", str_author)
    return path_root


def test_a_changed_source_without_its_doc_is_reported(tmp_path: Path) -> None:
    """Should-fail witness: the coupling map flags a source change with no doc change.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _repo_with_change(tmp_path, str_message="feat: change")
    assert "pyproject.toml changed" in gate.coupling_problems(path_root, str_base="main")[0]


def test_the_escape_line_silences_the_coupling_report(tmp_path: Path) -> None:
    """A ``Docs: not needed because`` line in the range is the audited escape.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _repo_with_change(
        tmp_path, str_message="feat: change\n\nDocs: not needed because internal"
    )
    assert gate.coupling_problems(path_root, str_base="main") == []


def test_an_escape_reason_on_the_next_line_does_not_silence(tmp_path: Path) -> None:
    """Should-fail witness: whitespace after ``because`` must not cross a newline.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _repo_with_change(
        tmp_path, str_message="feat: change\n\nDocs: not needed because\nTesting: passed"
    )
    assert "pyproject.toml changed" in gate.coupling_problems(path_root, str_base="main")[0]


def test_a_bot_name_in_the_message_is_not_a_bot_author(tmp_path: Path) -> None:
    """Should-fail witness: only the author name exempts, never the commit body.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _repo_with_change(tmp_path, str_message="feat: change\n\nlike dependabot[bot]")
    assert "pyproject.toml changed" in gate.coupling_problems(path_root, str_base="main")[0]


def test_a_bot_author_is_exempt(tmp_path: Path) -> None:
    """A commit whose author name ends in ``[bot]`` silences the coupling report.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _repo_with_change(
        tmp_path, str_message="chore: bump", str_author="dependabot[bot] <b@e.f>"
    )
    assert gate.coupling_problems(path_root, str_base="main") == []


def test_a_comment_only_coupling_map_is_no_rules(tmp_path: Path) -> None:
    """Should-fail witness: ``safe_load`` returns None for a comment-only file.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _repo_with_change(tmp_path, str_message="feat: x", str_coupling="# none yet\n")
    assert gate.coupling_problems(path_root, str_base="main") == []


def test_a_malformed_coupling_map_is_an_advisory_not_a_crash(tmp_path: Path) -> None:
    """Should-fail witness: broken YAML is reported and never raises.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _repo_with_change(tmp_path, str_message="feat: x", str_coupling="couplings: [\n")
    assert "could not be read" in gate.coupling_problems(path_root, str_base="main")[0]


def test_an_unknown_base_is_reported_and_stays_advisory(
    tmp_path: Path, *, capsys: pytest.CaptureFixture
) -> None:
    """Should-fail witness: a ref git cannot resolve is named, and the exit status stays 0.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    path_root = _repo_with_change(tmp_path, str_message="feat: x")
    int_code, str_out = _verdict(
        path_root, capsys=capsys, list_flags=("--coupling", "--base", "no-such-ref")
    )
    assert (int_code, "advisory: git could not diff against no-such-ref" in str_out) == (0, True)
