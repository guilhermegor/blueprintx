"""Database handler factory for runtime backend selection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

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
		str_driver = "ODBC+Driver+17+for+SQL+Server"
		return f"{str_scheme}://{str_user}:{str_password}@{str_host}:{str_port}/{str_name}?driver={str_driver}"
	return f"{str_scheme}://{str_user}:{str_password}@{str_host}:{str_port}/{str_name}"


def build_database_handler() -> DatabaseHandler:
	"""Build a database handler based on environment configuration.

	Returns
	-------
	DatabaseHandler
		Configured backend handler ready for CRUD operations.

	Raises
	------
	ValueError
		If ``DB_BACKEND`` does not match a supported backend.

	Notes
	-----
	Reads ``DB_BACKEND`` to pick the SQL backend. Supported: ``sqlite``, ``postgresql``,
	``mariadb``, ``mysql``, ``mssql``, ``oracle``.

	SQLite uses ``DB_PATH`` (default: ``./data/app.db``).

	All other backends read ``DB_DSN`` first; if unset, they compose a DSN from
	``DB_USER``, ``DB_PASSWORD``, ``DB_HOST``, ``DB_PORT``, and ``DB_NAME``.
	Oracle additionally reads ``DB_SERVICE`` (default: ``XEPDB1``).

	For schema-less backends (JSON, CSV, joblib) use ``build_storage_handler()`` from
	``chassis.db_wschema.application``.
	"""
	load_dotenv()
	str_backend = os.getenv("DB_BACKEND", "sqlite").lower()

	def _sqlite() -> SQLiteDatabaseHandler:
		path_db = Path(os.getenv("DB_PATH", "./data/app.db"))
		path_db.parent.mkdir(parents=True, exist_ok=True)
		return SQLiteDatabaseHandler(path_db)

	dict_builders: dict[str, Callable[[], DatabaseHandler]] = {
		"sqlite": _sqlite,
		"postgresql": lambda: PostgresDatabaseHandler(os.getenv("DB_DSN") or _compose_dsn(str_backend)),
		"mariadb": lambda: MariaDBDatabaseHandler(os.getenv("DB_DSN") or _compose_dsn(str_backend)),
		"mysql": lambda: MySQLDatabaseHandler(os.getenv("DB_DSN") or _compose_dsn(str_backend)),
		"mssql": lambda: MSSQLDatabaseHandler(os.getenv("DB_DSN") or _compose_dsn(str_backend)),
		"oracle": lambda: OracleDatabaseHandler(os.getenv("DB_DSN") or _compose_dsn(str_backend)),
	}

	if str_backend not in dict_builders:
		str_supported = ", ".join(dict_builders)
		raise ValueError(f"Unsupported DB_BACKEND {str_backend!r}. Supported: {str_supported}")
	return dict_builders[str_backend]()
