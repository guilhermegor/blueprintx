"""SQLAlchemy database session factory for runtime backend selection."""

from __future__ import annotations

import os
from typing import Callable

from dotenv import load_dotenv

from chassis.db_schema.infrastructure import DatabaseSession
from chassis.typing.decorators import type_checker


def _compose_url(str_backend: str) -> str:
	"""Build a SQLAlchemy URL from generic environment variables."""
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
		"postgresql": "postgresql+psycopg2",
		"mariadb": "mysql+pymysql",
		"mysql": "mysql+pymysql",
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


def build_database_url() -> str:
	"""Build a SQLAlchemy database URL from environment configuration.

	Returns
	-------
	str
		SQLAlchemy-compatible database URL.

	Raises
	------
	ValueError
		If ``DB_BACKEND`` does not match a supported backend.

	Notes
	-----
	Reads ``DB_BACKEND`` to select the database type. Supported: ``sqlite``,
	``postgresql``, ``mariadb``, ``mysql``, ``mssql``, ``oracle``.

	SQLite uses ``DB_PATH`` (default: ``./data/app.db``).

	All other backends read ``DB_DSN`` first; if unset, they compose a URL from
	``DB_USER``, ``DB_PASSWORD``, ``DB_HOST``, ``DB_PORT``, and ``DB_NAME``.
	Oracle additionally reads ``DB_SERVICE`` (default: ``XEPDB1``).
	"""
	load_dotenv()
	str_backend = os.getenv("DB_BACKEND", "sqlite").lower()

	dict_builders: dict[str, Callable[[], str]] = {
		"sqlite": lambda: f"sqlite:///{os.getenv('DB_PATH', './data/app.db')}",
		"postgresql": lambda: os.getenv("DB_DSN") or _compose_url(str_backend),
		"mariadb": lambda: os.getenv("DB_DSN") or _compose_url(str_backend),
		"mysql": lambda: os.getenv("DB_DSN") or _compose_url(str_backend),
		"mssql": lambda: os.getenv("DB_DSN") or _compose_url(str_backend),
		"oracle": lambda: os.getenv("DB_DSN") or _compose_url(str_backend),
	}

	if str_backend not in dict_builders:
		str_supported = ", ".join(dict_builders)
		raise ValueError(f"Unsupported DB_BACKEND {str_backend!r}. Supported: {str_supported}")

	return dict_builders[str_backend]()


@type_checker
def build_database_session(echo: bool = False) -> DatabaseSession:
	"""Build a DatabaseSession based on environment configuration.

	Parameters
	----------
	echo : bool, optional
		If ``True``, log all SQL statements, by default ``False``.

	Returns
	-------
	DatabaseSession
		Configured SQLAlchemy session manager.

	Examples
	--------
	>>> db = build_database_session()
	>>> db.create_tables()
	>>> with db.session() as session:
	...     repo = SQLAlchemyRecordRepository(session)
	...     repo.add({"title": "Hello"})
	...     session.commit()
	"""
	str_url = build_database_url()
	return DatabaseSession(str_url, echo=echo)
