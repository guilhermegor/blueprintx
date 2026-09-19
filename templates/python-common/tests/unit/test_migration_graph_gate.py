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


def test_two_heads_message_names_both_head_revisions(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
	"""The message must name the offending heads, not just 'branched'."""
	path_versions = tmp_path / "migrations" / "versions"
	path_versions.mkdir(parents=True)
	_migration_file(path_versions, "20260901_root.py", "root", "None")
	_migration_file(path_versions, "20260902_branch_a.py", "branch_a", '"root"')
	_migration_file(path_versions, "20260902_branch_b.py", "branch_b", '"root"')
	monkeypatch.chdir(tmp_path)

	gate.main()

	str_err = capsys.readouterr().err
	assert "branch_a" in str_err
	assert "branch_b" in str_err
	assert "2 head revisions present" in str_err


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
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
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
	# The exit code alone is not the assertion: the OLD code also exited 1 here, but via
	# "2 head revisions present" -- it had silently promoted the unverifiable file to a
	# root and then complained about the consequence. Assert the cause is named.
	str_err = capsys.readouterr().err
	assert "cannot verify" in str_err
	assert "20260902_child.py" in str_err


def test_main_fails_when_down_revision_is_absent_entirely(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
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
	# Same as above: the old code exited 1 for the wrong reason (an extra head). The
	# finding must name the file whose metadata could not be read.
	str_err = capsys.readouterr().err
	assert "no 'down_revision' assignment" in str_err


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



def test_main_fails_on_a_cycle_that_coexists_with_a_valid_chain(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
	"""Head-counting alone cannot see this: the valid chain supplies the one head.

	Two components — a 2-node cycle (loop_a <-> loop_b) and a root->child chain. The head
	count is exactly 1, so the head check passes and the cycle went unreported.
	"""
	path_versions = tmp_path / "migrations" / "versions"
	path_versions.mkdir(parents=True)
	_migration_file(path_versions, "20260901_root.py", "root", "None")
	_migration_file(path_versions, "20260902_child.py", "child", '"root"')
	_migration_file(path_versions, "20260903_loop_a.py", "loop_a", '"loop_b"')
	_migration_file(path_versions, "20260904_loop_b.py", "loop_b", '"loop_a"')
	monkeypatch.chdir(tmp_path)

	assert gate.main() == 1
	str_err = capsys.readouterr().err
	assert "cycle" in str_err
	assert "loop_a" in str_err
	assert "loop_b" in str_err
