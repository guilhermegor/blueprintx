"""Service entrypoint and database handler selection for the ddd-service template."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

from core.infrastructure.database import (
    CSVDatabaseHandler,
    JSONDatabaseHandler,
    SQLiteDatabaseHandler,
    PostgresDatabaseHandler,
    MariaDBDatabaseHandler,
    MySQLDatabaseHandler,
    MSSQLDatabaseHandler,
    OracleDatabaseHandler,
    DatabaseHandler,
)


def _postgres_dsn() -> str:
    """Build a PostgreSQL DSN from environment variables."""

    user = os.getenv("POSTGRES_USER", "user")
    password = os.getenv("POSTGRES_PASSWORD", "password")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "app")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def _mariadb_dsn() -> str:
    """Build a MariaDB DSN from environment variables."""

    user = os.getenv("MARIADB_USER", "user")
    password = os.getenv("MARIADB_PASSWORD", "password")
    host = os.getenv("MARIADB_HOST", "localhost")
    port = os.getenv("MARIADB_PORT", "3306")
    database = os.getenv("MARIADB_DB", "app")
    return f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"


def _mysql_dsn() -> str:
    """Build a MySQL DSN from environment variables."""

    user = os.getenv("MYSQL_USER", "user")
    password = os.getenv("MYSQL_PASSWORD", "password")
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    database = os.getenv("MYSQL_DB", "app")
    return f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"


def _mssql_dsn() -> str:
    """Build a MSSQL (SQL Server) DSN from environment variables."""

    user = os.getenv("MSSQL_USER", "sa")
    password = os.getenv("MSSQL_PASSWORD", "password")
    host = os.getenv("MSSQL_HOST", "localhost")
    port = os.getenv("MSSQL_PORT", "1433")
    database = os.getenv("MSSQL_DB", "app")
    return f"mssql+pyodbc://{user}:{password}@{host}:{port}/{database}?driver=ODBC+Driver+17+for+SQL+Server"


def _oracle_dsn() -> str:
    """Build an Oracle DSN from environment variables."""

    user = os.getenv("ORACLE_USER", "user")
    password = os.getenv("ORACLE_PASSWORD", "password")
    host = os.getenv("ORACLE_HOST", "localhost")
    port = os.getenv("ORACLE_PORT", "1521")
    service = os.getenv("ORACLE_SERVICE", "XEPDB1")
    return f"oracle+oracledb://{user}:{password}@{host}:{port}/?service_name={service}"


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
    Reads ``DB_BACKEND`` to pick the backend and uses related variables such as
    ``DATA_DIR``, ``DB_FILE_JSON``, ``DB_FILE_CSV``, ``SQLITE_PATH``,
    and per-backend credentials in the ``.env`` file to construct the handler.
    """

    load_dotenv()
    backend = os.getenv("DB_BACKEND", "json").lower()
    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    builders: dict[str, Callable[[], DatabaseHandler]] = {
        "csv": lambda: CSVDatabaseHandler(data_dir / os.getenv("DB_FILE_CSV", "records.csv")),
        "json": lambda: JSONDatabaseHandler(data_dir / os.getenv("DB_FILE_JSON", "records.json")),
        "sqlite": lambda: SQLiteDatabaseHandler(data_dir / os.getenv("SQLITE_PATH", "app.db")),
        "postgresql": lambda: PostgresDatabaseHandler(
            os.getenv("POSTGRES_DSN", _postgres_dsn())
        ),
        "mariadb": lambda: MariaDBDatabaseHandler(
            os.getenv("MARIADB_DSN", _mariadb_dsn())
        ),
        "mysql": lambda: MySQLDatabaseHandler(
            os.getenv("MYSQL_DSN", _mysql_dsn())
        ),
        "mssql": lambda: MSSQLDatabaseHandler(
            os.getenv("MSSQL_DSN", _mssql_dsn())
        ),
        "oracle": lambda: OracleDatabaseHandler(
            os.getenv("ORACLE_DSN", _oracle_dsn())
        ),
    }

    if backend not in builders:
        supported = ", ".join(builders)
        raise ValueError(f"Unsupported DB_BACKEND '{backend}'. Supported: {supported}")
    return builders[backend]()


def run_demo(handler: DatabaseHandler) -> None:
    """Execute a minimal CRUD demo against the provided handler.

    Parameters
    ----------
    handler : DatabaseHandler
        The backend implementation to exercise.
    """

    record_id = handler.create({"name": "demo", "status": "created"})
    print(f"Created record with id={record_id}")
    record = handler.read(record_id)
    print(f"Fetched record: {record}")
    updated = handler.update(record_id, {"status": "updated"})
    print(f"Updated record: {updated}")
    deleted = handler.delete(record_id)
    print(f"Deleted: {deleted}")


def main() -> None:
    """Run the service entrypoint and optionally the CRUD demo.

    Notes
    -----
    When the ``RUN_DEMO`` environment variable is set to true, a basic CRUD
    cycle is executed to validate backend wiring.
    """

    handler = build_database_handler()
    print(f"Using backend: {handler.__class__.__name__}")
    if os.getenv("RUN_DEMO", "false").lower() == "true":
        run_demo(handler)


if __name__ == "__main__":
    main()
