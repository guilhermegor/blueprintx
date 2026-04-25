"""Shared database contract for all storage backends.

Named ``ports.py`` to signal its role as a contract definition.
Uses ``ABCTypeCheckerMeta`` instead of ``Protocol`` because chassis implementations
are internal and must be complete — ``@abstractmethod`` provides runtime enforcement
and ``TypeChecker`` validates argument types on every call.
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Any, Optional

from chassis.typing import ABCTypeCheckerMeta


Record = dict[str, Any]


class DatabaseHandler(metaclass=ABCTypeCheckerMeta):
	"""Abstract handler exposing CRUD operations for any storage backend.

	Attributes
	----------
	id_field : str
		Name of the identifier field used across backends.
	"""

	id_field: str = "id"

	@abstractmethod
	def create(self, record: Record) -> str:
		"""Persist a record and return its identifier.

		Parameters
		----------
		record : Record
			Data to store.

		Returns
		-------
		str
			Identifier assigned to the stored record.
		"""

	@abstractmethod
	def read(self, record_id: str) -> Optional[Record]:
		"""Fetch a record by identifier.

		Parameters
		----------
		record_id : str
			Identifier to look up.

		Returns
		-------
		Record or None
			Stored record when found, otherwise ``None``.
		"""

	@abstractmethod
	def update(self, record_id: str, updates: Record) -> Optional[Record]:
		"""Update a record and return the new value if it exists.

		Parameters
		----------
		record_id : str
			Identifier of the record to update.
		updates : Record
			Partial payload containing fields to override.

		Returns
		-------
		Record or None
			Updated record when it exists, otherwise ``None``.
		"""

	@abstractmethod
	def delete(self, record_id: str) -> bool:
		"""Remove a record by identifier.

		Parameters
		----------
		record_id : str
			Identifier of the record to remove.

		Returns
		-------
		bool
			``True`` when a row was deleted, ``False`` otherwise.
		"""

	@abstractmethod
	def backup(self, target_path: str | Path) -> Path:
		"""Create a backup of all stored data.

		Parameters
		----------
		target_path : str or Path
			Destination file path for the backup artifact.

		Returns
		-------
		Path
			Path to the created backup artifact.
		"""

	@abstractmethod
	def close(self) -> None:
		"""Release any resources held by the handler."""
