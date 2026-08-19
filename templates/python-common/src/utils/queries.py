"""Resolve a SQL query file from the engine directory the configuration selects.

Queries live at ``config/queries/<engine>/<table>__<purpose>.sql``. The engine is a
**directory**, not a filename prefix, so the wrong dialect is *unreachable* rather than
merely rejected: no code path can hand T-SQL to a SQLite connection, and nothing has to
notice. A check is always second-best to a structure in which the wrong state cannot be
represented.

The directory names the **engine**, not the database instance — two SQL Server databases
share one ``mssql/`` directory. The day routing has to be per-instance, the directory
becomes a *connection* name and the engine is looked up from that connection's config.

This module reads no environment variable on purpose. ``DB_BACKEND`` lives in a
git-ignored ``.env``, so no pre-commit hook and no CI job can ever see it — a gate over
tracked files is structurally blind to it. The guard therefore has to run at **runtime**,
at the single funnel the value passes through. Keeping the backend an argument leaves the
rule pure and testable on any machine; each skeleton's thin caller supplies it from the
one function that reads the environment.

Resolution happens here, and not where the query is executed, because the executor
receives only the SQL **text** — by then nothing can tell which dialect it holds. That is
precisely why a mismatch used to surface as a ``sqlite3.OperationalError`` from inside
pandas, layers below its cause and after every input had already been read.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). mypy reads the single TYPE_CHECKING
# import (no redefinition); at runtime the try/except picks whichever layout shipped.
if TYPE_CHECKING:
	from utils.typing import type_checker
else:
	try:
		from utils.typing import type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from chassis.typing import type_checker


@type_checker
def _engine_dirs(path_queries_root: Path) -> list[Path]:
	"""List the per-engine directories under the queries root, sorted by name.

	Parameters
	----------
	path_queries_root : pathlib.Path
		The ``config/queries`` directory holding one subdirectory per engine.

	Returns
	-------
	list of pathlib.Path
		Every engine directory, or an empty list when the root does not exist.
	"""
	if not path_queries_root.is_dir():
		return []
	return sorted(
		(path_engine for path_engine in path_queries_root.iterdir() if path_engine.is_dir()),
		key=lambda path_engine: path_engine.name,
	)


@type_checker
def load_query(str_filename: str, str_backend: str, path_queries_root: Path) -> str:
	"""Read the SQL text filed for ``str_backend`` under the queries root.

	Parameters
	----------
	str_filename : str
		Bare query filename, e.g. ``example_entity__select_active.sql``. It must not
		carry a directory component: the engine directory is derived from the configured
		backend, never spelled by the caller.
	str_backend : str
		The active engine, supplied by the single function that reads ``DB_BACKEND``.
	path_queries_root : pathlib.Path
		The ``config/queries`` directory holding one subdirectory per engine.

	Returns
	-------
	str
		The SQL text, read as UTF-8.

	Raises
	------
	ValueError
		If ``str_filename`` carries a directory component, which would bypass the engine
		routing this function exists to enforce.
	FileNotFoundError
		If no file is filed for that engine. The message names the engines that *do* hold
		the query, so a typo and a misconfiguration do not read identically.
	"""
	if Path(str_filename).name != str_filename:
		raise ValueError(
			f"Query name {str_filename!r} must be a bare filename. The engine directory is "
			f"derived from the configured backend, so spelling one here would route around "
			f"the very check this loader exists to make."
		)

	path_query = path_queries_root / str_backend / str_filename
	if path_query.is_file():
		return path_query.read_text(encoding="utf-8")

	list_dirs = _engine_dirs(path_queries_root)
	list_carriers = [
		path_engine.name for path_engine in list_dirs if (path_engine / str_filename).is_file()
	]
	if list_carriers:
		raise FileNotFoundError(
			f"Query {str_filename!r} is not filed for engine {str_backend!r} "
			f"(looked in {path_query}), but it EXISTS for: {', '.join(list_carriers)}. "
			f"Either DB_BACKEND names the wrong engine, or the query was filed under one."
		)

	str_present = ", ".join(path_engine.name for path_engine in list_dirs) or "<none>"
	raise FileNotFoundError(
		f"Query {str_filename!r} exists for no engine under {path_queries_root} "
		f"(engine directories present: {str_present}). Check the filename."
	)
