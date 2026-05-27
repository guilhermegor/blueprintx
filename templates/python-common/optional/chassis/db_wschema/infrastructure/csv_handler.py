"""CSV-backed implementation of the storage handler for small datasets."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Iterable, Optional

from chassis.db.domain.ports import DatabaseHandler, Record
from chassis.db.infrastructure.helpers import ensure_id


class CSVDatabaseHandler(DatabaseHandler):
	"""Lightweight CSV-backed storage for development and testing.

	Parameters
	----------
	file_path : str or Path
		Location of the CSV file.
	id_field : str, optional
		Identifier column name, by default ``"id"``.
	"""

	def __init__(self, file_path: str | Path, id_field: str = "id"):
		self.file_path = Path(file_path)
		self.file_path.parent.mkdir(parents=True, exist_ok=True)
		self.id_field = id_field
		if not self.file_path.exists():
			self.file_path.write_text("", encoding="utf-8")

	def create(self, record: Record) -> str:
		"""Insert a record into the CSV store.

		Parameters
		----------
		record : Record
			Data to persist.

		Returns
		-------
		str
			Identifier assigned to the stored record.
		"""

		record = ensure_id(record, self.id_field)
		list_rows = self._read_all()
		list_rows.append(record)
		self._write_all(list_rows)
		return str(record[self.id_field])

	def read(self, record_id: str) -> Optional[Record]:
		"""Retrieve a record by identifier.

		Parameters
		----------
		record_id : str
			Identifier to look up.

		Returns
		-------
		Record or None
			Matching record when found, otherwise ``None``.
		"""

		for dict_row in self._read_all():
			if str(dict_row.get(self.id_field)) == str(record_id):
				return dict_row
		return None

	def update(self, record_id: str, updates: Record) -> Optional[Record]:
		"""Update a stored record.

		Parameters
		----------
		record_id : str
			Identifier of the record to update.
		updates : Record
			Partial payload to merge.

		Returns
		-------
		Record or None
			Updated record when it exists, otherwise ``None``.
		"""

		dict_updated: Optional[Record] = None
		list_rows: list[Record] = []
		for dict_row in self._read_all():
			if str(dict_row.get(self.id_field)) == str(record_id):
				dict_row = {**dict_row, **updates, self.id_field: record_id}
				dict_updated = dict_row
			list_rows.append(dict_row)
		if dict_updated is not None:
			self._write_all(list_rows)
		return dict_updated

	def delete(self, record_id: str) -> bool:
		"""Remove a record from the CSV file.

		Parameters
		----------
		record_id : str
			Identifier of the record to remove.

		Returns
		-------
		bool
			``True`` when a record was deleted, ``False`` otherwise.
		"""

		list_rows = self._read_all()
		list_remaining = [r for r in list_rows if str(r.get(self.id_field)) != str(record_id)]
		if len(list_remaining) == len(list_rows):
			return False
		self._write_all(list_remaining)
		return True

	def backup(self, target_path: str | Path) -> Path:
		"""Create a file copy as a backup artifact."""

		path_target = Path(target_path)
		path_target.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(self.file_path, path_target)
		return path_target

	def close(self) -> None:
		"""No-op for file-based storage."""

		return None

	def _read_all(self) -> list[Record]:
		"""Load all records from disk.

		Returns
		-------
		list of Record
			All records currently stored.
		"""

		if not self.file_path.exists() or self.file_path.stat().st_size == 0:
			return []
		with self.file_path.open(newline="", encoding="utf-8") as handle:
			reader = csv.DictReader(handle)
			return [dict(row) for row in reader]

	def _write_all(self, rows: Iterable[Record]) -> None:
		"""Write all records to disk, replacing existing data.

		Parameters
		----------
		rows : Iterable[Record]
			Records to persist.
		"""

		list_rows = list(rows)
		if not list_rows:
			self.file_path.write_text("", encoding="utf-8")
			return
		list_fieldnames = sorted({key for dict_row in list_rows for key in dict_row.keys()})
		with self.file_path.open("w", newline="", encoding="utf-8") as handle:
			writer = csv.DictWriter(handle, fieldnames=list_fieldnames)
			writer.writeheader()
			for dict_row in list_rows:
				writer.writerow(dict_row)
