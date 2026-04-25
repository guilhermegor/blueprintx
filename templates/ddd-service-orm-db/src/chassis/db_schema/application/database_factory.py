"""SQLAlchemy database session factory for runtime backend selection."""

from __future__ import annotations

import os
from typing import Callable

from dotenv import load_dotenv

from chassis.db_schema.infrastructure import DatabaseSession
from chassis.typing.decorators import type_checker


def _sqlite_url() -> str:
    """Build a SQLite URL from environment variables."""
    str_path = os.getenv("SQLITE_PATH", "app.db")
    return f"sqlite:///{str_path}"


def _postgres_url() -> str:
    """Build a PostgreSQL URL from environment variables."""
    if str_dsn := os.getenv("POSTGRES_DSN"):
        return str_dsn
    str_user = os.getenv("POSTGRES_USER", "user")
    str_password = os.getenv("POSTGRES_PASSWORD", "password")
    str_host = os.getenv("POSTGRES_HOST", "localhost")
    str_port = os.getenv("POSTGRES_PORT", "5432")
    str_database = os.getenv("POSTGRES_DB", "app")
    return f"postgresql+psycopg2://{str_user}:{str_password}@{str_host}:{str_port}/{str_database}"


def _mysql_url() -> str:
    """Build a MySQL URL from environment variables."""
    if str_dsn := os.getenv("MYSQL_DSN"):
        return str_dsn
    str_user = os.getenv("MYSQL_USER", "user")
    str_password = os.getenv("MYSQL_PASSWORD", "password")
    str_host = os.getenv("MYSQL_HOST", "localhost")
    str_port = os.getenv("MYSQL_PORT", "3306")
    str_database = os.getenv("MYSQL_DB", "app")
    return f"mysql+pymysql://{str_user}:{str_password}@{str_host}:{str_port}/{str_database}"


def _mariadb_url() -> str:
    """Build a MariaDB URL from environment variables."""
    if str_dsn := os.getenv("MARIADB_DSN"):
        return str_dsn
    str_user = os.getenv("MARIADB_USER", "user")
    str_password = os.getenv("MARIADB_PASSWORD", "password")
    str_host = os.getenv("MARIADB_HOST", "localhost")
    str_port = os.getenv("MARIADB_PORT", "3306")
    str_database = os.getenv("MARIADB_DB", "app")
    return f"mysql+pymysql://{str_user}:{str_password}@{str_host}:{str_port}/{str_database}"


def _mssql_url() -> str:
    """Build a MSSQL (SQL Server) URL from environment variables."""
    if str_dsn := os.getenv("MSSQL_DSN"):
        return str_dsn
    str_user = os.getenv("MSSQL_USER", "sa")
    str_password = os.getenv("MSSQL_PASSWORD", "password")
    str_host = os.getenv("MSSQL_HOST", "localhost")
    str_port = os.getenv("MSSQL_PORT", "1433")
    str_database = os.getenv("MSSQL_DB", "app")
    str_driver = "ODBC+Driver+17+for+SQL+Server"
    return f"mssql+pyodbc://{str_user}:{str_password}@{str_host}:{str_port}/{str_database}?driver={str_driver}"


def _oracle_url() -> str:
    """Build an Oracle URL from environment variables."""
    if str_dsn := os.getenv("ORACLE_DSN"):
        return str_dsn
    str_user = os.getenv("ORACLE_USER", "user")
    str_password = os.getenv("ORACLE_PASSWORD", "password")
    str_host = os.getenv("ORACLE_HOST", "localhost")
    str_port = os.getenv("ORACLE_PORT", "1521")
    str_service = os.getenv("ORACLE_SERVICE", "XEPDB1")
    return f"oracle+oracledb://{str_user}:{str_password}@{str_host}:{str_port}/?service_name={str_service}"


_URL_BUILDERS: dict[str, Callable[[], str]] = {
    "sqlite": _sqlite_url,
    "postgresql": _postgres_url,
    "mysql": _mysql_url,
    "mariadb": _mariadb_url,
    "mssql": _mssql_url,
    "oracle": _oracle_url,
}


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
    Reads ``DB_BACKEND`` to select the database type and uses related
    environment variables to construct the connection URL.

    Supported backends:
    - sqlite: Local file-based database
    - postgresql: PostgreSQL with psycopg2 driver
    - mysql: MySQL with PyMySQL driver
    - mariadb: MariaDB with PyMySQL driver
    - mssql: SQL Server with pyodbc driver
    - oracle: Oracle with oracledb driver
    """
    load_dotenv()
    str_backend = os.getenv("DB_BACKEND", "sqlite").lower()

    if str_backend not in _URL_BUILDERS:
        str_supported = ", ".join(_URL_BUILDERS)
        raise ValueError(f"Unsupported DB_BACKEND {str_backend!r}. Supported: {str_supported}")

    return _URL_BUILDERS[str_backend]()


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
