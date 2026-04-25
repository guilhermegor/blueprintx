"""SQLAlchemy database session factory for runtime backend selection."""

from __future__ import annotations

import os
from typing import Callable

from dotenv import load_dotenv

from chassis.db_schema.infrastructure import DatabaseSession


def _sqlite_url() -> str:
    """Build a SQLite URL from environment variables."""
    path = os.getenv("SQLITE_PATH", "app.db")
    return f"sqlite:///{path}"


def _postgres_url() -> str:
    """Build a PostgreSQL URL from environment variables."""
    if dsn := os.getenv("POSTGRES_DSN"):
        return dsn
    user = os.getenv("POSTGRES_USER", "user")
    password = os.getenv("POSTGRES_PASSWORD", "password")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "app")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def _mysql_url() -> str:
    """Build a MySQL URL from environment variables."""
    if dsn := os.getenv("MYSQL_DSN"):
        return dsn
    user = os.getenv("MYSQL_USER", "user")
    password = os.getenv("MYSQL_PASSWORD", "password")
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    database = os.getenv("MYSQL_DB", "app")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


def _mariadb_url() -> str:
    """Build a MariaDB URL from environment variables."""
    if dsn := os.getenv("MARIADB_DSN"):
        return dsn
    user = os.getenv("MARIADB_USER", "user")
    password = os.getenv("MARIADB_PASSWORD", "password")
    host = os.getenv("MARIADB_HOST", "localhost")
    port = os.getenv("MARIADB_PORT", "3306")
    database = os.getenv("MARIADB_DB", "app")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


def _mssql_url() -> str:
    """Build a MSSQL (SQL Server) URL from environment variables."""
    if dsn := os.getenv("MSSQL_DSN"):
        return dsn
    user = os.getenv("MSSQL_USER", "sa")
    password = os.getenv("MSSQL_PASSWORD", "password")
    host = os.getenv("MSSQL_HOST", "localhost")
    port = os.getenv("MSSQL_PORT", "1433")
    database = os.getenv("MSSQL_DB", "app")
    return f"mssql+pyodbc://{user}:{password}@{host}:{port}/{database}?driver=ODBC+Driver+17+for+SQL+Server"


def _oracle_url() -> str:
    """Build an Oracle URL from environment variables."""
    if dsn := os.getenv("ORACLE_DSN"):
        return dsn
    user = os.getenv("ORACLE_USER", "user")
    password = os.getenv("ORACLE_PASSWORD", "password")
    host = os.getenv("ORACLE_HOST", "localhost")
    port = os.getenv("ORACLE_PORT", "1521")
    service = os.getenv("ORACLE_SERVICE", "XEPDB1")
    return f"oracle+oracledb://{user}:{password}@{host}:{port}/?service_name={service}"


# Supported database backends and their URL builders
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
    backend = os.getenv("DB_BACKEND", "sqlite").lower()

    if backend not in _URL_BUILDERS:
        supported = ", ".join(_URL_BUILDERS)
        raise ValueError(f"Unsupported DB_BACKEND '{backend}'. Supported: {supported}")

    return _URL_BUILDERS[backend]()


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
    url = build_database_url()
    return DatabaseSession(url, echo=echo)
