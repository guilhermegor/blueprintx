"""Unit tests for the docs-drift gate (blueprintx#1233)."""

import functools
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest


_BIN = Path(__file__).resolve().parents[2] / "bin"
STR_TASKS = '[tool.poe.tasks.lint]\ncmd = "ruff check"\n'


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


def test_a_defined_task_in_a_fence_passes(tmp_path: Path) -> None:
    """A cited task the project defines is not drift.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _project(tmp_path, str_readme="```bash\npoe lint\n```\n")
    assert gate.poe_problems(path_root, list_docs=gate.doc_files(path_root)) == []


def test_an_undefined_task_in_a_fence_fails(tmp_path: Path) -> None:
    """Should-fail witness: a code block cites a task that does not exist.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _project(tmp_path, str_readme="```bash\npoe offline_only\n```\n")
    assert (
        "poe offline_only is not defined"
        in gate.poe_problems(path_root, list_docs=gate.doc_files(path_root))[0]
    )


def test_an_undefined_task_in_an_inline_span_fails(tmp_path: Path) -> None:
    """Should-fail witness: an inline code span cites a task that does not exist.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _project(tmp_path, str_readme="Run `poe ghost` first.\n")
    assert (
        "poe ghost is not defined"
        in gate.poe_problems(path_root, list_docs=gate.doc_files(path_root))[0]
    )


def test_prose_mentioning_poe_is_not_a_citation(tmp_path: Path) -> None:
    """Only code is read, so the sentence 'poe the poet' is never a task.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _project(tmp_path, str_readme="We use poe the poet for tasks.\n")
    assert gate.poe_problems(path_root, list_docs=gate.doc_files(path_root)) == []


def test_an_export_missing_from_the_reference_fails(tmp_path: Path) -> None:
    """Should-fail witness: a name in ``__all__`` the API page never mentions.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _project(
        tmp_path, str_readme="x\n", str_all='__all__ = ["Shown", "Hidden"]\n', str_ref="`Shown`\n"
    )
    assert "Hidden is in __all__" in gate.all_problems(path_root)[0]


def test_an_export_in_a_table_row_passes(tmp_path: Path) -> None:
    """Any word-bounded mention counts, so a table row documents the name.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _project(
        tmp_path, str_readme="x\n", str_all='__all__ = ["Shown"]\n', str_ref="| `Shown` | a |\n"
    )
    assert gate.all_problems(path_root) == []


def test_a_dunder_export_needs_no_reference_entry(tmp_path: Path) -> None:
    """``__version__`` is metadata, not an API symbol.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _project(
        tmp_path, str_readme="x\n", str_all='__all__ = ["__version__"]\n', str_ref="page\n"
    )
    assert gate.all_problems(path_root) == []


def test_all_without_a_reference_page_fails(tmp_path: Path) -> None:
    """Should-fail witness: an export list with no page to document it.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    path_root = _project(tmp_path, str_readme="x\n", str_all='__all__ = ["A"]\n')
    assert "does not exist" in gate.all_problems(path_root)[0]


def test_a_root_with_no_pages_fails(tmp_path: Path, *, capsys: pytest.CaptureFixture) -> None:
    """Should-fail witness: discovery finding nothing is a failure, never a pass.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture
        Captures the gate's report.
    """
    int_code = gate.main(["--root", str(tmp_path)])
    assert (int_code, "nothing was checked" in capsys.readouterr().out) == (1, True)


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
    gate.main(["--root", str(_project(tmp_path, str_readme="`poe lint`\n"))])
    assert "1 page(s)" in capsys.readouterr().out


def _repo_with_change(path_root: Path, *, str_message: str) -> Path:
    """Build a repo whose ``feature`` branch edits ``pyproject.toml`` but not the README.

    Parameters
    ----------
    path_root : pathlib.Path
        Repository root.
    str_message : str
        Commit message of the source change.

    Returns
    -------
    pathlib.Path
        ``path_root``.
    """
    _project(path_root, str_readme="x\n")
    (path_root / ".docs-coupling.yaml").write_text(
        "couplings:\n  - source: pyproject.toml\n    docs: [README.md]\n", encoding="utf-8"
    )
    (path_root / "pyproject.toml").write_text("a\n", encoding="utf-8")
    _git(path_root, "init", "-q", "-b", "main")
    _git(path_root, "add", ".")
    _git(path_root, "commit", "-q", "-m", "base")
    _git(path_root, "checkout", "-q", "-b", "feature")
    (path_root / "pyproject.toml").write_text("b\n", encoding="utf-8")
    _git(path_root, "commit", "-q", "-am", str_message)
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
