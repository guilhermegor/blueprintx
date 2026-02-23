"""Database abstractions and concrete handler implementations."""

from .base import DatabaseHandler
from .dto import Record
from .csv_handler import CSVDatabaseHandler
from .json_handler import JSONDatabaseHandler
from .sqlite_handler import SQLiteDatabaseHandler
from .postgres_handler import PostgresDatabaseHandler
from .mariadb_handler import MariaDBDatabaseHandler
from .mysql_handler import MySQLDatabaseHandler
from .mssql_handler import MSSQLDatabaseHandler
from .oracle_handler import OracleDatabaseHandler

__all__ = [
    "DatabaseHandler",
    "Record",
    "CSVDatabaseHandler",
    "JSONDatabaseHandler",
    "SQLiteDatabaseHandler",
    "PostgresDatabaseHandler",
    "MariaDBDatabaseHandler",
    "MySQLDatabaseHandler",
    "MSSQLDatabaseHandler",
    "OracleDatabaseHandler",
]
