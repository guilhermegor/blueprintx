"""Behaviour of the per-engine SQL query resolver.

The defect this loader exists to prevent is a *late, misattributed* error: a T-SQL
statement reaching a SQLite connection and surfacing as an ``OperationalError`` thrown by
pandas, several layers below the cause and after every input file had been read. Nothing
in the repository was wrong — the query was correct, the contract was correct, the tests
were green. The whole defect was one line in a git-ignored ``.env``.

So the tests below are named for the *failure class* each one pins, and the decisive pair
is routing (a query is read from the engine's directory, never from a sibling's) and
diagnosis (the error distinguishes a wrong backend from a misspelled filename).
"""

from pathlib import Path

import pytest

from utils.queries import load_query


# --------------------------
# Module Utilities
# --------------------------


def _seed_query(path_root: Path, str_engine: str, str_filename: str, str_sql: str) -> Path:
	"""Write one query file under an engine directory, creating the tree.

	Parameters
	----------
	path_root : pathlib.Path
		The queries root standing in for ``config/queries``.
	str_engine : str
		Engine directory name, e.g. ``sqlite``.
	str_filename : str
		Bare query filename.
	str_sql : str
		SQL text to write.

	Returns
	-------
	pathlib.Path
		The path written.
	"""
	path_engine = path_root / str_engine
	path_engine.mkdir(parents=True, exist_ok=True)
	path_query = path_engine / str_filename
	path_query.write_text(str_sql, encoding="utf-8")
	return path_query


# --------------------------
# Routing
# --------------------------


def test_load_query_reads_the_file_filed_for_the_active_engine(tmp_path: Path) -> None:
	"""The query filed under the active engine is the one returned."""
	_seed_query(tmp_path, "sqlite", "example__select.sql", "SELECT 1;")

	assert load_query("example__select.sql", "sqlite", tmp_path) == "SELECT 1;"


def test_load_query_routes_by_engine_when_two_engines_carry_the_same_name(
	tmp_path: Path,
) -> None:
	"""Same filename, two engines: each backend gets its own dialect, never the sibling's.

	This is the negative control for the routing itself. Drop the ``/ str_backend`` segment
	and this is the test that fails — the others would still pass by reading *a* file.
	"""
	_seed_query(tmp_path, "sqlite", "example__select.sql", "SELECT 1;")
	_seed_query(tmp_path, "mssql", "example__select.sql", "DECLARE @x INT;")

	assert load_query("example__select.sql", "sqlite", tmp_path) == "SELECT 1;"
	assert load_query("example__select.sql", "mssql", tmp_path) == "DECLARE @x INT;"


def test_load_query_rejects_a_filename_carrying_an_engine_directory(tmp_path: Path) -> None:
	"""Spelling the engine in the name would route around the loader — so it is refused."""
	_seed_query(tmp_path, "mssql", "example__select.sql", "DECLARE @x INT;")

	with pytest.raises(ValueError, match="bare filename"):
		load_query("mssql/example__select.sql", "sqlite", tmp_path)


# --------------------------
# Diagnosis
# --------------------------


def test_load_query_names_the_engines_that_do_carry_the_query(tmp_path: Path) -> None:
	"""A misconfigured backend is told which engines hold the file it asked for."""
	_seed_query(tmp_path, "mssql", "example__select.sql", "DECLARE @x INT;")
	_seed_query(tmp_path, "oracle", "example__select.sql", "SELECT 1 FROM dual;")
	(tmp_path / "sqlite").mkdir()

	with pytest.raises(FileNotFoundError) as cls_excinfo:
		load_query("example__select.sql", "sqlite", tmp_path)

	str_message = str(cls_excinfo.value)
	assert "EXISTS for: mssql, oracle" in str_message
	assert "sqlite" in str_message


def test_load_query_says_no_engine_carries_a_misspelled_name(tmp_path: Path) -> None:
	"""A typo reads differently from a misconfiguration — otherwise both look the same."""
	_seed_query(tmp_path, "sqlite", "example__select.sql", "SELECT 1;")

	with pytest.raises(FileNotFoundError) as cls_excinfo:
		load_query("exmaple__select.sql", "sqlite", tmp_path)

	str_message = str(cls_excinfo.value)
	assert "exists for no engine" in str_message
	assert "engine directories present: sqlite" in str_message
	assert "EXISTS for" not in str_message


def test_load_query_reports_an_absent_queries_root_rather_than_crashing(tmp_path: Path) -> None:
	"""A missing root is a configuration answer, not an unhandled traceback."""
	path_missing = tmp_path / "nowhere"

	with pytest.raises(FileNotFoundError) as cls_excinfo:
		load_query("example__select.sql", "sqlite", path_missing)

	assert "engine directories present: <none>" in str(cls_excinfo.value)
