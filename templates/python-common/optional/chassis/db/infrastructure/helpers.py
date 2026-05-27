"""Utility helpers shared by all storage backends."""

from __future__ import annotations

import uuid

from chassis.db.domain.ports import Record
from chassis.typing.decorators import type_checker


@type_checker
def ensure_id(record: Record, id_field: str = "id") -> Record:
	"""Ensure a record carries a string identifier.

	Parameters
	----------
	record : Record
		Dictionary payload representing the entity.
	id_field : str, optional
		Key used to store the identifier, by default ``"id"``.

	Returns
	-------
	Record
		Record with the identifier guaranteed to be present.
	"""
	value = record.get(id_field)
	if value:
		return {**record, id_field: str(value)}
	return {**record, id_field: uuid.uuid4().hex}
