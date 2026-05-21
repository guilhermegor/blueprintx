"""SQLAlchemy connection factory for the model layer.

Reads ``DB_BACKEND`` from the environment and returns a SQLAlchemy ``Engine``
plus a bound ``sessionmaker``. The model layer uses these to run ORM queries or
``pd.read_sql`` reads. Any SQLAlchemy-compatible backend is supported.
"""

from __future__ import annotations

import os
from typing import Callable

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def _compose_url(str_backend: str) -> str:
	"""Build a SQLAlchemy URL from generic environment variables.

	Parameters
	----------
	str_backend : str
		Backend key (``postgresql``, ``mariadb``, ``mysql``, ``mssql``, ``oracle``).

	Returns
	-------
	str
		A SQLAlchemy-compatible connection URL composed from ``DB_*`` env vars.
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
	dict_schemes: dict[str, str] = {
		"postgresql": "postgresql+psycopg",
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
	Reads ``DB_BACKEND`` (default ``sqlite``). Supported: ``sqlite``,
	``postgresql``, ``mariadb``, ``mysql``, ``mssql``, ``oracle``. SQLite uses
	``DB_PATH``; the rest read ``DB_DSN`` first, then compose from ``DB_*`` vars.
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


def build_engine() -> Engine:
	"""Build a SQLAlchemy engine from environment configuration.

	Returns
	-------
	sqlalchemy.Engine
		Engine bound to the configured backend. Reads ``SQL_ECHO`` (default
		``false``) to toggle SQL statement logging.
	"""
	bool_echo = os.getenv("SQL_ECHO", "false").lower() == "true"
	return create_engine(build_database_url(), echo=bool_echo)


def build_session_factory(cls_engine: Engine | None = None) -> Callable[[], Session]:
	"""Build a ``sessionmaker`` bound to the configured engine.

	Parameters
	----------
	cls_engine : sqlalchemy.Engine, optional
		Engine to bind. If ``None``, one is built from the environment.

	Returns
	-------
	Callable[[], Session]
		A factory that returns new ``Session`` instances.
	"""
	cls_engine = cls_engine or build_engine()
	return sessionmaker(bind=cls_engine, expire_on_commit=False)
