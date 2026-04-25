"""SQL-backed database handler implementations."""

from chassis.db.domain.ports import DatabaseHandler, Record
from .sqlite_handler import SQLiteDatabaseHandler
from .postgres_handler import PostgresDatabaseHandler
from .mariadb_handler import MariaDBDatabaseHandler
from .mysql_handler import MySQLDatabaseHandler
from .mssql_handler import MSSQLDatabaseHandler
from .oracle_handler import OracleDatabaseHandler


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
