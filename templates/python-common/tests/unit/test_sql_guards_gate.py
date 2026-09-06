"""Unit tests for the SQL guards gate (blueprintx#355; offline, no git, no network).

Each guard needs BOTH directions proven: the dangerous form must FAIL naming the file, the
line, the fix and the escape hatch; the safe form must PASS. A gate that cannot fail is
reporting its own blindness as OK — the exact failure mode this repo's gates exist to
prevent. The false-positive tests (a plain ``dict.update()``, a single-instance
``session.delete(record)``) are just as load-bearing: the issue's own review history is full
of matchers that fired on every ORM mutation and became 100% noise on first use.
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


gate = _load("check_sql_guards")


def _python_file(path_dir: Path, str_source: str) -> Path:
	"""Write a Python source file and return its path.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory to write into.
	str_source : str
		File contents.

	Returns
	-------
	pathlib.Path
		The written file.
	"""
	path_file = path_dir / "sample.py"
	path_file.write_text(str_source, encoding="utf-8")
	return path_file


# --------------------------
# 🔴 WHERE-less DELETE/UPDATE — the negative control
# --------------------------


def test_whereless_core_delete_is_reported(tmp_path: Path) -> None:
	"""A bare Core ``delete(...)`` with no ``.where()`` is a violation."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy import delete\n\nstmt = delete(comments)\n",
	)

	list_problems = gate.check_python_file(path_file)

	assert len(list_problems) == 1
	assert "delete(...) has no .where()" in list_problems[0]
	assert str(path_file) in list_problems[0]
	assert "sql-guard-ok:" in list_problems[0]


def test_whereless_module_qualified_delete_is_reported(tmp_path: Path) -> None:
	"""``sa.delete(t)`` is a Core builder, not the ambiguous ``.delete()`` attribute form."""
	path_file = _python_file(
		tmp_path,
		"import sqlalchemy as sa\n\nstmt = sa.delete(comments)\n",
	)

	assert len(gate.check_python_file(path_file)) == 1


def test_whereless_module_qualified_update_is_reported(tmp_path: Path) -> None:
	"""The unaliased spelling reaches the same branch — the module name IS the alias."""
	path_file = _python_file(
		tmp_path,
		'import sqlalchemy\n\nstmt = sqlalchemy.update(comments).values(status="x")\n',
	)

	assert len(gate.check_python_file(path_file)) == 1


def test_module_qualified_delete_with_where_passes(tmp_path: Path) -> None:
	"""Widening to the module alias must not fire on a properly scoped mutation."""
	path_file = _python_file(
		tmp_path,
		"import sqlalchemy as sa\n\nstmt = sa.delete(comments).where(comments.c.id == 1)\n",
	)

	assert gate.check_python_file(path_file) == []


def test_whereless_core_delete_with_where_passes(tmp_path: Path) -> None:
	"""The same call with a ``.where()`` chained on is clean."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy import delete\n\nstmt = delete(comments).where(comments.c.id == 1)\n",
	)

	assert gate.check_python_file(path_file) == []


def test_whereless_core_update_values_only_is_reported(tmp_path: Path) -> None:
	"""``update(...).values(...)`` with no ``.where()`` mutates every row."""
	path_file = _python_file(
		tmp_path,
		'from sqlalchemy import update\n\nstmt = update(comments).values(status="x")\n',
	)

	list_problems = gate.check_python_file(path_file)

	assert len(list_problems) == 1
	assert "update(...) has no .where()" in list_problems[0]


def test_whereless_query_style_delete_is_reported(tmp_path: Path) -> None:
	"""``session.query(Model).delete()`` with no ``.filter()`` is a violation."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy.orm import Session\n\nsession.query(Model).delete()\n",
	)

	list_problems = gate.check_python_file(path_file)

	assert len(list_problems) == 1
	assert "delete(...) has no .where()" in list_problems[0]


def test_query_style_update_with_filter_passes(tmp_path: Path) -> None:
	"""``session.query(Model).filter(...).update(...)`` is a safe, scoped mutation."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy.orm import Session\n\n"
		'session.query(Model).filter_by(id=1).update({"x": 1})\n',
	)

	assert gate.check_python_file(path_file) == []


# --------------------------
# 🔴 False-positive guards — a matcher that fires on every ORM mutation is 100% noise
# --------------------------


def test_single_instance_session_delete_is_not_flagged(tmp_path: Path) -> None:
	"""``session.delete(record)`` (primary-key-scoped) must never be flagged.

	This is the ONLY delete pattern this repo's own ORM templates ship today — a matcher
	that fires here would break on first use, exactly the failure mode the issue warns
	against.
	"""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy.orm import Session\n\nsession.delete(record)\n",
	)

	assert gate.check_python_file(path_file) == []


def test_plain_dict_update_in_a_sqlalchemy_file_is_not_flagged(tmp_path: Path) -> None:
	"""A ``dict.update()`` call must not be confused for a SQLAlchemy mutation."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy.orm import Session\n\ndict_config.update(other_dict)\n",
	)

	assert gate.check_python_file(path_file) == []


def test_no_sqlalchemy_import_skips_the_whereless_check(tmp_path: Path) -> None:
	"""A file with no ``sqlalchemy`` import is out of scope entirely."""
	path_file = _python_file(tmp_path, "stmt = delete(comments)\n")

	assert gate.check_python_file(path_file) == []


# --------------------------
# 🔴 WITH (NOLOCK) — flags the hint, never requires it
# --------------------------


def test_nolock_in_python_string_literal_is_reported(tmp_path: Path) -> None:
	"""A ``WITH (NOLOCK)`` hint inside a Python string literal is a violation."""
	path_file = _python_file(
		tmp_path,
		'str_query = "SELECT * FROM comments WITH (NOLOCK)"\n',
	)

	list_problems = gate.check_python_file(path_file)

	assert len(list_problems) == 1
	assert "WITH (NOLOCK)" in list_problems[0]
	assert "dirty read" in list_problems[0].lower()
	assert "sql-guard-ok:" in list_problems[0]


def test_nolock_in_sql_file_is_reported(tmp_path: Path) -> None:
	"""A ``WITH (NOLOCK)`` hint in a raw ``.sql`` file is a violation."""
	path_file = tmp_path / "query.sql"
	path_file.write_text("SELECT * FROM comments WITH (NOLOCK);\n", encoding="utf-8")

	list_problems = gate._nolock_problems_in_sql(path_file)

	assert len(list_problems) == 1
	assert "WITH (NOLOCK)" in list_problems[0]


def test_second_nolock_in_one_literal_is_still_reported(tmp_path: Path) -> None:
	"""A hatch on the first hint must not cover a second, unannotated one in the same literal."""
	path_file = _python_file(
		tmp_path,
		'STR_Q = (\n'
		'\t"SELECT a FROM t1 WITH (NOLOCK) "  # sql-guard-ok: reporting replica\n'
		'\t"UNION ALL SELECT b FROM t2 WITH (NOLOCK)"\n'
		')\n',
	)

	list_problems = gate.check_python_file(path_file)

	assert len(list_problems) == 1
	assert ":3:" in list_problems[0]


def test_nolock_split_across_lines_is_reported(tmp_path: Path) -> None:
	"""A hint broken after ``WITH`` is one hint; a per-line search never spans the break."""
	path_file = tmp_path / "query.sql"
	path_file.write_text(
		"SELECT *\nFROM comments WITH\n(NOLOCK)\nWHERE id = 1;\n", encoding="utf-8"
	)

	list_problems = gate._nolock_problems_in_sql(path_file)

	assert len(list_problems) == 1
	assert ":2:" in list_problems[0]


def test_nolock_split_across_lines_honours_the_hatch(tmp_path: Path) -> None:
	"""The hatch is read on the line the match STARTS on, not on the line it ends."""
	path_file = tmp_path / "query.sql"
	path_file.write_text(
		"SELECT *\nFROM comments WITH  -- sql-guard-ok: reporting replica\n(NOLOCK);\n",
		encoding="utf-8",
	)

	assert gate._nolock_problems_in_sql(path_file) == []


def test_query_without_nolock_passes(tmp_path: Path) -> None:
	"""A plain read with no ``NOLOCK`` hint is clean."""
	path_file = tmp_path / "query.sql"
	path_file.write_text("SELECT * FROM comments;\n", encoding="utf-8")

	assert gate._nolock_problems_in_sql(path_file) == []


# --------------------------
# 🔴 Escape hatch — present with a reason suppresses; empty/blank still fails
# --------------------------


def test_escape_hatch_with_reason_suppresses_the_finding(tmp_path: Path) -> None:
	"""A written reason after the marker is accepted."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy import delete\n\n"
		"stmt = delete(comments)  # sql-guard-ok: full purge, reviewed in PR #123\n",
	)

	assert gate.check_python_file(path_file) == []


def test_escape_hatch_with_empty_reason_still_fails(tmp_path: Path) -> None:
	"""A bare marker with no reason (or whitespace only) is rejected, not accepted."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy import delete\n\nstmt = delete(comments)  # sql-guard-ok:   \n",
	)

	list_problems = gate.check_python_file(path_file)

	assert len(list_problems) == 1


# --------------------------
# 🔴 Zero-discovery guard — a wrong cwd must FAIL, not report success silently
# --------------------------


def test_main_skips_when_src_is_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""No ``src/`` directory at all is a legitimate skip."""
	monkeypatch.chdir(tmp_path)

	assert gate.main() == 0


def test_main_fails_on_zero_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""``src/`` exists but holds no Python files — that must FAIL, not pass silently."""
	(tmp_path / "src").mkdir()
	monkeypatch.chdir(tmp_path)

	assert gate.main() == 1


def test_main_passes_on_a_clean_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""A real file with no violations reports success."""
	path_src = tmp_path / "src"
	path_src.mkdir()
	(path_src / "mod.py").write_text("int_x = 1\n", encoding="utf-8")
	monkeypatch.chdir(tmp_path)

	assert gate.main() == 0
