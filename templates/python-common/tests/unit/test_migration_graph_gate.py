"""Unit tests for the migration-graph gate (blueprintx#308; offline, no DB/alembic import).

The two-heads case is the negative control the whole gate exists for — a should-fail witness
on a synthetic branched graph proves the gate actually fires, same rule as
``test_migration_slug_gate.py`` and ``test_rmw_race_gate.py``.
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


_BIN = Path(__file__).resolve().parents[2] / "bin"


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
    cls_module = importlib.util.module_from_spec(cls_spec)
    sys.modules[str_name] = cls_module
    cls_spec.loader.exec_module(cls_module)
    return cls_module


gate = _load("check_migration_graph")


def _migration_file(
    path_dir: Path, str_filename: str, str_revision: str, str_down_revision_repr: str
) -> Path:
    """Write a synthetic migration version file and return its path.

    Parameters
    ----------
    path_dir : pathlib.Path
        Directory to write into.
    str_filename : str
        Filename, including extension.
    str_revision : str
        The ``revision`` id to embed.
    str_down_revision_repr : str
        The ``down_revision`` right-hand side, already formatted as Python source
        (``"None"``, ``'"abc123"'``, or ``'("a", "b")'``).

    Returns
    -------
    pathlib.Path
        The written file.
    """
    path_file = path_dir / str_filename
    path_file.write_text(
        f'"""synthetic migration"""\n\n'
        f'revision: str = "{str_revision}"\n'
        f"down_revision = {str_down_revision_repr}\n",
        encoding="utf-8",
    )
    return path_file


# --------------------------
# Directory-level self-skip
# --------------------------


def test_main_skips_when_migrations_dir_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tier with no migrations/versions/ (most Python tiers today) must pass, not fail."""
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 0


def test_main_skips_when_versions_dir_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh scaffold's versions/ holding only .gitkeep must pass, not fail."""
    (tmp_path / "migrations" / "versions").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 0


# --------------------------
# Should-PASS witnesses
# --------------------------


def test_main_passes_on_a_single_linear_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A root revision plus one child, with a single head, must pass."""
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_root.py", "root", "None")
    _migration_file(path_versions, "20260902_child.py", "child", '"root"')
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 0


def test_main_passes_after_a_merge_revision_joins_two_heads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The documented fix — a merge revision whose down_revision is a tuple — resolves it."""
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_root.py", "root", "None")
    _migration_file(path_versions, "20260902_branch_a.py", "branch_a", '"root"')
    _migration_file(path_versions, "20260902_branch_b.py", "branch_b", '"root"')
    _migration_file(path_versions, "20260903_merge.py", "merged", '("branch_a", "branch_b")')
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 0


# --------------------------
# 🔴 The negative control — the gate must be able to FAIL, naming the heads
# --------------------------


def test_main_fails_on_two_heads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two independent PRs branching off the same parent must be reported as two heads."""
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_root.py", "root", "None")
    _migration_file(path_versions, "20260902_branch_a.py", "branch_a", '"root"')
    _migration_file(path_versions, "20260902_branch_b.py", "branch_b", '"root"')
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 1


@pytest.fixture
def str_two_heads_err(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> str:
    """Run the gate over two migrations branching off one root; return its stderr.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway project root.
    monkeypatch : pytest.MonkeyPatch
        Used to run the gate from the project root.
    capsys : pytest.CaptureFixture[str]
        Captures the gate's message.

    Returns
    -------
    str
        What the gate wrote to stderr.
    """
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_root.py", "root", "None")
    _migration_file(path_versions, "20260902_branch_a.py", "branch_a", '"root"')
    _migration_file(path_versions, "20260902_branch_b.py", "branch_b", '"root"')
    monkeypatch.chdir(tmp_path)
    gate.main()
    return capsys.readouterr().err


@pytest.mark.parametrize("str_needle", ["branch_a", "branch_b", "2 head revisions present"])
def test_two_heads_message_names_both_head_revisions(
    str_two_heads_err: str, str_needle: str
) -> None:
    """The message must name the offending heads, not just 'branched'.

    Parameters
    ----------
    str_two_heads_err : str
        What the gate wrote to stderr.
    str_needle : str
        Text the message must contain.
    """
    assert str_needle in str_two_heads_err


# --------------------------
# Other findings the graph read must catch
# --------------------------


def test_main_fails_on_a_dangling_down_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A down_revision with no matching file (a torn-out migration) must be reported."""
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_child.py", "child", '"missing_parent"')
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 1


def test_main_fails_on_a_duplicate_revision_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two files claiming the same revision id must be reported."""
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_a.py", "dupe", "None")
    _migration_file(path_versions, "20260902_b.py", "dupe", "None")
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 1


def test_main_fails_on_a_self_referencing_down_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A revision naming itself as its own parent must be reported."""
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_loop.py", "loop", '"loop"')
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 1


def test_main_fails_on_an_unparsable_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A migration file that is not valid Python cannot be verified — a finding, not a skip."""
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    (path_versions / "20260901_broken.py").write_text("def upgrade(:\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 1


def test_main_fails_on_a_file_missing_the_revision_assignment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file with no 'revision' literal cannot be verified — a finding, not a silent skip."""
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    (path_versions / "20260901_no_header.py").write_text(
        "down_revision = None\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 1


def test_main_fails_on_a_non_literal_down_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A down_revision this reader cannot evaluate is unverifiable, never a root.

    ``_literal`` returned ``None`` for a name/call/f-string, which is byte-identical to a
    genuine ``down_revision = None`` — so the file silently became a head and the head
    count was wrong in whichever direction happened to apply.
    """
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_root.py", "root", "None")
    _migration_file(path_versions, "20260902_child.py", "child", "PREVIOUS_REVISION")
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 1


@pytest.fixture
def str_non_literal_err(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> str:
    """Run the gate over a migration whose ``down_revision`` is a bare name; return stderr.

    The exit code alone is not the assertion: the OLD code also exited 1 here, but via
    "2 head revisions present" -- it had silently promoted the unverifiable file to a root
    and then complained about the consequence. The tests below assert the cause is named.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway project root.
    monkeypatch : pytest.MonkeyPatch
        Used to run the gate from the project root.
    capsys : pytest.CaptureFixture[str]
        Captures the gate's message.

    Returns
    -------
    str
        What the gate wrote to stderr.
    """
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_root.py", "root", "None")
    _migration_file(path_versions, "20260902_child.py", "child", "PREVIOUS_REVISION")
    monkeypatch.chdir(tmp_path)
    gate.main()
    return capsys.readouterr().err


@pytest.mark.parametrize("str_needle", ["cannot verify", "20260902_child.py"])
def test_non_literal_down_revision_names_the_cause(
    str_non_literal_err: str, str_needle: str
) -> None:
    """The finding names the unverifiable cause and the file, not a consequence.

    Parameters
    ----------
    str_non_literal_err : str
        What the gate wrote to stderr.
    str_needle : str
        Text the message must contain.
    """
    assert str_needle in str_non_literal_err


def test_main_fails_when_down_revision_is_absent_entirely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing key is 'cannot verify', not 'this is a root' — a root says so explicitly."""
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_root.py", "root", "None")
    (path_versions / "20260902_child.py").write_text(
        '"""synthetic migration"""\n\nrevision: str = "child"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 1


def test_absent_down_revision_names_the_missing_assignment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same as above: the old code exited 1 for the wrong reason (an extra head).

    The finding must say the metadata could not be read.
    """
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_root.py", "root", "None")
    (path_versions / "20260902_child.py").write_text(
        '"""synthetic migration"""\n\nrevision: str = "child"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    gate.main()

    assert "no 'down_revision' assignment" in capsys.readouterr().err


def test_main_fails_on_a_tuple_with_a_non_string_element(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A merge tuple holding a non-string had that element silently dropped."""
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_a.py", "a", "None")
    _migration_file(path_versions, "20260902_merge.py", "merge", '("a", 123)')
    monkeypatch.chdir(tmp_path)

    assert gate.main() == 1


@pytest.fixture
def tuple_cycle_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> tuple:
    """Run the gate over a 2-node cycle that coexists with a valid root->child chain.

    Head-counting alone cannot see this: the valid chain supplies the one head, the head
    count is exactly 1, so the head check passes and the cycle went unreported.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway project root.
    monkeypatch : pytest.MonkeyPatch
        Used to run the gate from the project root.
    capsys : pytest.CaptureFixture[str]
        Captures the gate's message.

    Returns
    -------
    tuple
        ``(int_status, str_err)``.
    """
    path_versions = tmp_path / "migrations" / "versions"
    path_versions.mkdir(parents=True)
    _migration_file(path_versions, "20260901_root.py", "root", "None")
    _migration_file(path_versions, "20260902_child.py", "child", '"root"')
    _migration_file(path_versions, "20260903_loop_a.py", "loop_a", '"loop_b"')
    _migration_file(path_versions, "20260904_loop_b.py", "loop_b", '"loop_a"')
    monkeypatch.chdir(tmp_path)
    int_status = gate.main()
    return int_status, capsys.readouterr().err


def test_main_fails_on_a_cycle_that_coexists_with_a_valid_chain(tuple_cycle_run: tuple) -> None:
    """A cycle beside a valid chain still fails the run.

    Parameters
    ----------
    tuple_cycle_run : tuple
        ``(int_status, str_err)``.
    """
    assert tuple_cycle_run[0] == 1


@pytest.mark.parametrize("str_needle", ["cycle", "loop_a", "loop_b"])
def test_a_cycle_finding_names_the_cycle_and_its_members(
    tuple_cycle_run: tuple, str_needle: str
) -> None:
    """The finding says "cycle" and names both revisions on it.

    Parameters
    ----------
    tuple_cycle_run : tuple
        ``(int_status, str_err)``.
    str_needle : str
        Text the message must contain.
    """
    assert str_needle in tuple_cycle_run[1]
