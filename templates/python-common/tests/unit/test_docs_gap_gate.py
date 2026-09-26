"""Unit tests for ``bin/check_docs_gap.py`` — the docs orphan-page / index-sync gate.

blueprintx#340 measured the defect before this gate existed: ``docs/decision-records.md``
and ``docs/issue-scope.md`` sit in BlueprintX's own ``docs/``, are built by MkDocs, and are
absent from both ``mkdocs.yml`` ``nav:`` and ``docs/CLAUDE.md``'s file index. The should-fail
cases below reproduce that exact shape on a fabricated project so the gate is proven against
the defect it exists to catch, not only against its own passing case.
"""

import importlib.util
import pathlib
import sys
import types

import pytest
import yaml


def _load_gate() -> types.ModuleType:
	"""Import ``check_docs_gap.py`` by path — ``bin/`` is not an importable package.

	Returns
	-------
	types.ModuleType
		The loaded gate module.
	"""
	path_gate = pathlib.Path(__file__).resolve().parents[2] / "bin" / "check_docs_gap.py"
	cls_spec = importlib.util.spec_from_file_location("check_docs_gap", path_gate)
	cls_module = importlib.util.module_from_spec(cls_spec)
	sys.modules["check_docs_gap"] = cls_module
	cls_spec.loader.exec_module(cls_module)
	return cls_module


cls_gate = _load_gate()


# --------------------------
# Module Utilities
# --------------------------


def _build_project(
	tmp_path: pathlib.Path,
	dict_pages: dict[str, str],
	str_nav_yaml: str,
	str_exclude_docs: str = "",
	str_claude_index_body: str | None = None,
) -> pathlib.Path:  # complexity-ok: fixture builder, branching is the work
	"""Fabricate a minimal BlueprintX-shaped project (``docs/`` + ``mkdocs.yml``).

	Parameters
	----------
	tmp_path : pathlib.Path
		pytest's per-test temporary directory, used as the project root.
	dict_pages : dict of str to str
		``{docs-relative path: file content}`` for every page to create.
	str_nav_yaml : str
		The YAML ``nav:`` value (as a Python literal, embedded via ``yaml.dump``).
	str_exclude_docs : str
		The ``exclude_docs:`` block content, one entry per line (default: none).
	str_claude_index_body : str or None
		When given, written as ``docs/CLAUDE.md``. When ``None``, no such file is created.

	Returns
	-------
	pathlib.Path
		The project root (``tmp_path`` itself).
	"""
	path_docs = tmp_path / "docs"
	path_docs.mkdir()
	for str_rel, str_body in dict_pages.items():
		path_page = path_docs / str_rel
		path_page.parent.mkdir(parents=True, exist_ok=True)
		path_page.write_text(str_body, encoding="utf-8")
	if str_claude_index_body is not None:
		(path_docs / "CLAUDE.md").write_text(str_claude_index_body, encoding="utf-8")
	dict_mkdocs = {"nav": yaml.safe_load(str_nav_yaml)}
	if str_exclude_docs:
		dict_mkdocs["exclude_docs"] = str_exclude_docs
	(tmp_path / "mkdocs.yml").write_text(yaml.safe_dump(dict_mkdocs), encoding="utf-8")
	return tmp_path


_STR_INDEX_TABLE = (
	"# CLAUDE.md — docs/\n\n## 1. File index\n\n"
	"| Path | Type | Purpose |\n|------|------|---------|\n"
	"| `index.md` | Utility page | Home |\n"
)


# --------------------------
# Tests — Layer 1 (orphan pages)
# --------------------------


def test_orphan_page_is_reported(tmp_path: pathlib.Path) -> None:
	"""A page on disk but absent from ``nav:`` is flagged by name, reproducing blueprintx#340."""
	path_root = _build_project(
		tmp_path,
		{"index.md": "# Home", "decision-records.md": "# Decisions"},
		"[{Home: index.md}]",
	)
	int_exit = cls_gate.main(["--root", str(path_root)])
	assert int_exit == 1


def test_orphan_page_message_names_the_file(
	tmp_path: pathlib.Path, capsys: pytest.CaptureFixture
) -> None:
	"""The finding names the orphan page and explains the silent-vanish mechanism."""
	path_root = _build_project(
		tmp_path,
		{"index.md": "# Home", "decision-records.md": "# Decisions"},
		"[{Home: index.md}]",
	)
	cls_gate.main(["--root", str(path_root)])
	str_stderr = capsys.readouterr().err
	assert "docs/decision-records.md" in str_stderr
	assert "not registered in mkdocs.yml nav" in str_stderr


def test_page_registered_in_nav_is_not_reported(tmp_path: pathlib.Path) -> None:
	"""The ordinary case: every page is in ``nav:`` — no orphan finding."""
	path_root = _build_project(
		tmp_path,
		{"index.md": "# Home", "usage.md": "# Usage"},
		"[{Home: index.md}, {Usage: usage.md}]",
	)
	assert cls_gate.main(["--root", str(path_root)]) == 0


def test_excluded_backlog_page_is_not_flagged(tmp_path: pathlib.Path) -> None:
	"""A page under an ``exclude_docs:`` folder is never an orphan finding."""
	path_root = _build_project(
		tmp_path,
		{"index.md": "# Home", "backlog/notes.md": "# WIP"},
		"[{Home: index.md}]",
		str_exclude_docs="backlog/\n",
	)
	assert cls_gate.main(["--root", str(path_root)]) == 0


# --------------------------
# Tests — Layer 2 (CLAUDE.md file-index sync)
# --------------------------


def test_claude_index_missing_row_is_reported(
	tmp_path: pathlib.Path, capsys: pytest.CaptureFixture
) -> None:
	"""A page on disk, in ``nav:``, but absent from the file-index table is still flagged."""
	path_root = _build_project(
		tmp_path,
		{"index.md": "# Home", "usage.md": "# Usage"},
		"[{Home: index.md}, {Usage: usage.md}]",
		str_claude_index_body=_STR_INDEX_TABLE,
	)
	int_exit = cls_gate.main(["--root", str(path_root)])
	str_stderr = capsys.readouterr().err
	assert int_exit == 1
	assert "docs/usage.md" in str_stderr
	assert "missing from the docs/CLAUDE.md file index" in str_stderr


def test_claude_index_stale_row_is_reported(
	tmp_path: pathlib.Path, capsys: pytest.CaptureFixture
) -> None:
	"""A row naming a file that no longer exists on disk is a finding, not silence."""
	str_index_with_ghost = _STR_INDEX_TABLE + "| `removed.md` | Utility page | Gone |\n"
	path_root = _build_project(
		tmp_path,
		{"index.md": "# Home"},
		"[{Home: index.md}]",
		str_claude_index_body=str_index_with_ghost,
	)
	int_exit = cls_gate.main(["--root", str(path_root)])
	str_stderr = capsys.readouterr().err
	assert int_exit == 1
	assert "removed.md" in str_stderr
	assert "does not exist on disk" in str_stderr


def test_claude_index_in_sync_passes(tmp_path: pathlib.Path) -> None:
	"""A file index that matches disk and nav exactly produces no Layer 2 finding."""
	path_root = _build_project(
		tmp_path,
		{"index.md": "# Home"},
		"[{Home: index.md}]",
		str_claude_index_body=_STR_INDEX_TABLE,
	)
	assert cls_gate.main(["--root", str(path_root)]) == 0


def test_prose_only_claude_md_skips_layer_two(tmp_path: pathlib.Path) -> None:
	"""A generated project's prose-only ``docs/CLAUDE.md`` has no file-index table.

	Only Layer 1 applies then, matching every shipped skeleton's own ``docs/CLAUDE.md``.
	"""
	path_root = _build_project(
		tmp_path,
		{"index.md": "# Home"},
		"[{Home: index.md}]",
		str_claude_index_body="# CLAUDE.md — docs/\n\nJust prose, no table here.\n",
	)
	assert cls_gate.main(["--root", str(path_root)]) == 0


# --------------------------
# Tests — fail-closed discovery guards
# --------------------------


def test_missing_docs_dir_fails_closed(
	tmp_path: pathlib.Path, capsys: pytest.CaptureFixture
) -> None:
	"""No ``docs/`` at all is a hard failure, never a silent 'nothing to check'."""
	int_exit = cls_gate.main(["--root", str(tmp_path)])
	str_stderr = capsys.readouterr().err
	assert int_exit == 1
	assert "no docs/ directory found" in str_stderr


def test_missing_mkdocs_yml_fails_closed(
	tmp_path: pathlib.Path, capsys: pytest.CaptureFixture
) -> None:
	"""A ``docs/`` with no ``mkdocs.yml`` beside it is a hard failure, not a pass."""
	(tmp_path / "docs").mkdir()
	(tmp_path / "docs" / "index.md").write_text("# Home", encoding="utf-8")
	int_exit = cls_gate.main(["--root", str(tmp_path)])
	str_stderr = capsys.readouterr().err
	assert int_exit == 1
	assert "no mkdocs.yml found" in str_stderr
