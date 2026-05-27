"""Example service-style model.

Demonstrates the MVC model pattern with native drivers: take a DB-API
connection, issue raw SQL, and shape the result into a pandas DataFrame. Copy
this file per domain entity and adapt the table name and columns.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


class ExampleEntity:
	"""Read/write access to a single example table.

	Parameters
	----------
	cls_connection : Any
		An open DB-API 2.0 connection (see :func:`model.conexao_db.build_connection`).
	str_table : str, optional
		Table name to operate on, by default ``"example"``.
	"""

	def __init__(self, cls_connection: Any, str_table: str = "example") -> None:
		self.cls_connection = cls_connection
		self.str_table = str_table

	def ensure_table(self) -> None:
		"""Create the example table if it does not already exist."""
		cls_cursor = self.cls_connection.cursor()
		# noqa justified: str_table is a developer-controlled identifier, never user input.
		cls_cursor.execute(  # noqa: S608
			f"CREATE TABLE IF NOT EXISTS {self.str_table} "
			"(id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
		)
		self.cls_connection.commit()
		cls_cursor.close()

	def insert(self, str_title: str) -> None:
		"""Insert one row into the example table.

		Parameters
		----------
		str_title : str
			Value for the ``title`` column.
		"""
		cls_cursor = self.cls_connection.cursor()
		# noqa justified: str_table is a developer-controlled identifier, never user input.
		cls_cursor.execute(
			f"INSERT INTO {self.str_table} (title) VALUES (?)",  # noqa: S608
			(str_title,),
		)
		self.cls_connection.commit()
		cls_cursor.close()

	def fetch_all(self) -> pd.DataFrame:
		"""Read every row from the example table into a DataFrame.

		Returns
		-------
		pd.DataFrame
			One row per record, columns taken from the cursor description.
		"""
		cls_cursor = self.cls_connection.cursor()
		cls_cursor.execute(f"SELECT * FROM {self.str_table}")  # noqa: S608
		if cls_cursor.description is None:
			cls_cursor.close()
			return pd.DataFrame()
		list_cols = [col[0] for col in cls_cursor.description]
		list_rows = cls_cursor.fetchall()
		cls_cursor.close()
		return pd.DataFrame.from_records(list_rows, columns=list_cols)
