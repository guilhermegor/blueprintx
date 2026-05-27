"""JSON-file implementation of the storage handler for local storage."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from chassis.db.domain.ports import DatabaseHandler, Record
from chassis.db.infrastructure.helpers import ensure_id


class JSONDatabaseHandler(DatabaseHandler):
	"""Simple JSON-file storage for development and demos.

	Parameters
	----------
	file_path : str or Path
		Location of the JSON file.
	id_field : str, optional
		Identifier field name, by default ``"id"``.
	"""

	def __init__(self, file_path: str | Path, id_field: str = "id"):
		self.file_path = Path(file_path)
		self.file_path.parent.mkdir(parents=True, exist_ok=True)
		self.id_field = id_field
		if not self.file_path.exists():
			self.file_path.write_text("[]", encoding="utf-8")

	def create(self, record: Record) -> str:
		"""Persist a record to the JSON store.

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
		"""Fetch a record by its identifier.

		Parameters
		----------
		record_id : str
			Identifier to look up.

		Returns
		-------
		Record or None
			Stored record when present, otherwise ``None``.
		"""

		for dict_row in self._read_all():
			if str(dict_row.get(self.id_field)) == str(record_id):
				return dict_row
		return None

	def update(self, record_id: str, updates: Record) -> Optional[Record]:
		"""Update an existing record.

		Parameters
		----------
		record_id : str
			Identifier of the record to update.
		updates : Record
			Partial payload containing fields to merge.

		Returns
		-------
		Record or None
			Updated record when found, otherwise ``None``.
		"""

		list_rows: list[Record] = []
		dict_updated: Optional[Record] = None
		for dict_row in self._read_all():
			if str(dict_row.get(self.id_field)) == str(record_id):
				dict_row = {**dict_row, **updates, self.id_field: record_id}
				dict_updated = dict_row
			list_rows.append(dict_row)
		if dict_updated is not None:
			self._write_all(list_rows)
		return dict_updated

	def delete(self, record_id: str) -> bool:
		"""Delete a record from the JSON file.

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
			Records contained in the JSON file.
		"""

		if not self.file_path.exists():
			return []
		str_content = self.file_path.read_text(encoding="utf-8")
		if not str_content.strip():
			return []
		return list(json.loads(str_content))

	def _write_all(self, rows: list[Record]) -> None:
		"""Write all records to disk, replacing existing content.

		Parameters
		----------
		rows : list of Record
			Records to persist.
		"""

		self.file_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
