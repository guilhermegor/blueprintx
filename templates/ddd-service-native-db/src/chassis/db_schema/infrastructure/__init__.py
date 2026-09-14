"""SQL-backed database handler implementations."""

from chassis.db.domain.ports import DatabaseHandler, Record

from .mariadb_handler import MariaDBDatabaseHandler
from .mssql_handler import MSSQLDatabaseHandler
from .mysql_handler import MySQLDatabaseHandler
from .oracle_handler import OracleDatabaseHandler
from .postgres_handler import PostgresDatabaseHandler
from .sqlite_handler import SQLiteDatabaseHandler


__all__ = [
    "DatabaseHandler",
    "Record",
    "SQLiteDatabaseHandler",
    "PostgresDatabaseHandler",
    "MariaDBDatabaseHandler",
    "MySQLDatabaseHandler",
    "MSSQLDatabaseHandler",
    "OracleDatabaseHandler",
]
