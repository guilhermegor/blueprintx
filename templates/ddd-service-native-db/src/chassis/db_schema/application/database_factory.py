"""Database handler factory for runtime backend selection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus

from dotenv import load_dotenv

from chassis.db_schema.infrastructure import (
	SQLiteDatabaseHandler,
	PostgresDatabaseHandler,
	MariaDBDatabaseHandler,
	MySQLDatabaseHandler,
	MSSQLDatabaseHandler,
	OracleDatabaseHandler,
	DatabaseHandler,
)


def _compose_dsn(str_backend: str) -> str:
	"""Build a connection DSN from generic environment variables."""
	str_user = os.getenv("DB_USER", "user")
	str_password = os.getenv("DB_PASSWORD", "password")
	str_host = os.getenv("DB_HOST", "localhost")
	dict_default_ports: dict[str, str] = {
		"postgresql": "5432",
		"mariadb": "3306",
		"mysql": "3306",
		"mssql": "1433",
		"oracle": "1521",
	}
	str_port = os.getenv("DB_PORT", dict_default_ports[str_backend])
	str_name = os.getenv("DB_NAME", "app")
	dict_schemes: dict[str, str] = {
		"postgresql": "postgresql",
		"mariadb": "mysql+mysqlconnector",
		"mysql": "mysql+mysqlconnector",
		"mssql": "mssql+pyodbc",
		"oracle": "oracle+oracledb",
	}
	str_scheme = dict_schemes[str_backend]
	if str_backend == "oracle":
		str_service = os.getenv("DB_SERVICE", "XEPDB1")
		return f"{str_scheme}://{str_user}:{str_password}@{str_host}:{str_port}/?service_name={str_service}"
	if str_backend == "mssql":
		str_driver = quote_plus(os.getenv("DB_ODBC_DRIVER", "ODBC Driver 17 for SQL Server"))
		return f"{str_scheme}://{str_user}:{str_password}@{str_host}:{str_port}/{str_name}?driver={str_driver}"
	return f"{str_scheme}://{str_user}:{str_password}@{str_host}:{str_port}/{str_name}"


def _sqlite() -> SQLiteDatabaseHandler:
	"""Open a SQLite handler at ``DB_PATH``, creating the parent directory."""
	path_db = Path(os.getenv("DB_PATH", "./data/app.db"))
	path_db.parent.mkdir(parents=True, exist_ok=True)
	return SQLiteDatabaseHandler(path_db)


# Engine name -> handler builder. Each builder takes the backend name so the map can live at
# MODULE level: as closures over an enclosing `str_backend` these had to be rebuilt inside the
# factory on every call, which also kept the engine NAMES private to that call — and the names
# are exactly what `active_backend()` must validate against and what the
# `config/queries/<engine>/` layout mirrors. One source, three readers.
_DICT_BUILDERS: dict[str, Callable[[str], DatabaseHandler]] = {
	"sqlite": lambda _: _sqlite(),
	"postgresql": lambda b: PostgresDatabaseHandler(os.getenv("DB_DSN") or _compose_dsn(b)),
	"mariadb": lambda b: MariaDBDatabaseHandler(os.getenv("DB_DSN") or _compose_dsn(b)),
	"mysql": lambda b: MySQLDatabaseHandler(os.getenv("DB_DSN") or _compose_dsn(b)),
	"mssql": lambda b: MSSQLDatabaseHandler(os.getenv("DB_DSN") or _compose_dsn(b)),
	"oracle": lambda b: OracleDatabaseHandler(os.getenv("DB_DSN") or _compose_dsn(b)),
}

# The supported engine names, derived from the dispatch map so the two cannot drift.
SET_BACKENDS: frozenset[str] = frozenset(_DICT_BUILDERS)

_STR_DEFAULT_BACKEND = "sqlite"


def active_backend() -> str:
	"""Return the configured engine name — the single reader of ``DB_BACKEND``.

	Returns
	-------
	str
		The lower-cased engine name, defaulting to ``sqlite``.

	Raises
	------
	ValueError
		If ``DB_BACKEND`` does not name a supported engine.

	Notes
	-----
	Everything that needs to know the engine calls this, so the default exists in exactly
	one place and cannot disagree with itself. The query loader resolves
	``config/queries/<engine>/`` from this value, so a second reader with its own default
	would file queries under one engine and connect with another.

	It is validated **here**, not only where a connection is opened, because the value is
	used to build a filesystem path before any handler exists. Rejecting it at the single
	reader means an unsupported engine fails with a message naming the supported ones,
	rather than as a confusing missing-query error somewhere downstream.

	``DB_BACKEND`` lives in a git-ignored ``.env``, which no gate over tracked files can
	validate. Assume every long-lived machine's copy is stale — ``bin/ensure_env.sh``
	deliberately never overwrites an existing ``.env`` — and let the runtime be the guard.
	"""
	load_dotenv()
	str_backend = os.getenv("DB_BACKEND", _STR_DEFAULT_BACKEND).lower()
	if str_backend not in SET_BACKENDS:
		str_supported = ", ".join(sorted(SET_BACKENDS))
		raise ValueError(f"Unsupported DB_BACKEND {str_backend!r}. Supported: {str_supported}")
	return str_backend


def build_database_handler() -> DatabaseHandler:
	"""Build a database handler based on environment configuration.

	Returns
	-------
	DatabaseHandler
		Configured backend handler ready for CRUD operations.

	Notes
	-----
	Reads ``DB_BACKEND`` through :func:`active_backend`, which rejects an unsupported value
	(propagating :class:`ValueError`) before any lookup here. Supported: ``sqlite``,
	``postgresql``, ``mariadb``, ``mysql``, ``mssql``, ``oracle``.

	SQLite uses ``DB_PATH`` (default: ``./data/app.db``).

	All other backends read ``DB_DSN`` first; if unset, they compose a DSN from
	``DB_USER``, ``DB_PASSWORD``, ``DB_HOST``, ``DB_PORT``, and ``DB_NAME``.
	Oracle additionally reads ``DB_SERVICE`` (default: ``XEPDB1``).

	For schema-less backends (JSON, CSV, joblib) use ``build_storage_handler()`` from
	``chassis.db_wschema.application``.
	"""
	str_backend = active_backend()
	return _DICT_BUILDERS[str_backend](str_backend)
