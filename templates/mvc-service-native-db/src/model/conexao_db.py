"""Native database connection factory for the model layer.

Reads ``DB_BACKEND`` from the environment and returns a raw DB-API 2.0
connection. There is no ORM here — the model layer issues SQL directly and
shapes results into pandas DataFrames. Drivers are imported lazily so a project
only needs the driver for the backend it actually uses.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv


def _compose_dsn(str_backend: str) -> str:
	"""Build a connection DSN from generic environment variables.

	Parameters
	----------
	str_backend : str
		Backend key (``postgresql``, ``mariadb``, ``mysql``, ``mssql``, ``oracle``).

	Returns
	-------
	str
		A driver-specific connection string composed from ``DB_*`` env vars.
	"""
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
	if str_backend == "oracle":
		str_service = os.getenv("DB_SERVICE", "XEPDB1")
		return f"{str_host}:{str_port}/{str_service}"
	return f"{str_host}:{str_port}/{str_name}|{str_user}|{str_password}"


def _connect_sqlite() -> Any:
	"""Open a stdlib ``sqlite3`` connection, creating the parent directory."""
	import sqlite3

	path_db = Path(os.getenv("DB_PATH", "./data/app.db"))
	path_db.parent.mkdir(parents=True, exist_ok=True)
	return sqlite3.connect(str(path_db))


def _connect_postgresql() -> Any:
	"""Open a PostgreSQL connection via ``psycopg``."""
	import psycopg

	str_dsn = os.getenv("DB_DSN")
	if str_dsn:
		return psycopg.connect(str_dsn)
	return psycopg.connect(
		host=os.getenv("DB_HOST", "localhost"),
		port=os.getenv("DB_PORT", "5432"),
		dbname=os.getenv("DB_NAME", "app"),
		user=os.getenv("DB_USER", "user"),
		password=os.getenv("DB_PASSWORD", "password"),
	)


def _connect_mysql() -> Any:
	"""Open a MySQL/MariaDB connection via ``mysql.connector``."""
	import mysql.connector

	str_dsn = os.getenv("DB_DSN")
	if str_dsn:
		return mysql.connector.connect(dsn=str_dsn)
	return mysql.connector.connect(
		host=os.getenv("DB_HOST", "localhost"),
		port=int(os.getenv("DB_PORT", "3306")),
		database=os.getenv("DB_NAME", "app"),
		user=os.getenv("DB_USER", "user"),
		password=os.getenv("DB_PASSWORD", "password"),
	)


def _connect_mssql() -> Any:
	"""Open a SQL Server connection via ``pyodbc``."""
	import pyodbc

	str_dsn = os.getenv("DB_DSN")
	if str_dsn:
		return pyodbc.connect(str_dsn)
	str_driver = os.getenv("DB_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
	str_conn = (
		f"DRIVER={{{str_driver}}};"
		f"SERVER={os.getenv('DB_HOST', 'localhost')},{os.getenv('DB_PORT', '1433')};"
		f"DATABASE={os.getenv('DB_NAME', 'app')};"
		f"UID={os.getenv('DB_USER', 'user')};"
		f"PWD={os.getenv('DB_PASSWORD', 'password')}"
	)
	return pyodbc.connect(str_conn)


def _connect_oracle() -> Any:
	"""Open an Oracle connection via ``oracledb``."""
	import oracledb

	str_dsn = os.getenv("DB_DSN") or _compose_dsn("oracle")
	return oracledb.connect(
		user=os.getenv("DB_USER", "user"),
		password=os.getenv("DB_PASSWORD", "password"),
		dsn=str_dsn,
	)


def build_connection() -> Any:
	"""Build a native DB-API connection from environment configuration.

	Returns
	-------
	Any
		An open DB-API 2.0 connection for the configured backend.

	Raises
	------
	ValueError
		If ``DB_BACKEND`` does not match a supported backend.

	Notes
	-----
	Reads ``DB_BACKEND`` (default ``sqlite``). Supported: ``sqlite``,
	``postgresql``, ``mariadb``, ``mysql``, ``mssql``, ``oracle``. SQLite uses
	``DB_PATH``; the rest read ``DB_DSN`` first, then compose from ``DB_*`` vars.
	"""
	load_dotenv()
	str_backend = os.getenv("DB_BACKEND", "sqlite").lower()

	dict_builders: dict[str, Callable[[], Any]] = {
		"sqlite": _connect_sqlite,
		"postgresql": _connect_postgresql,
		"mariadb": _connect_mysql,
		"mysql": _connect_mysql,
		"mssql": _connect_mssql,
		"oracle": _connect_oracle,
	}

	if str_backend not in dict_builders:
		str_supported = ", ".join(dict_builders)
		raise ValueError(f"Unsupported DB_BACKEND {str_backend!r}. Supported: {str_supported}")
	return dict_builders[str_backend]()
