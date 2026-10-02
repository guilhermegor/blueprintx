"""Utility helpers shared by all storage backends."""

from __future__ import annotations

from typing import TypedDict
import uuid

from chassis.db.domain.ports import Record
from chassis.typing.decorators import type_checker


class DsnParts(TypedDict):
    """Connection parts parsed out of a DSN, shared by every SQL handler.

    Exists because ``dict[str, object]`` — the obvious annotation for "a bag of
    connection settings" — erases the one thing callers need. Every field read back
    out of such a dict is an ``object``, so ``int(parts["port"])`` has no matching
    overload, ``env["PGPASSWORD"] = parts["password"]`` is an incompatible
    assignment, and an argv list built from those fields is a ``list[object]`` that
    ``subprocess.run`` rejects. One lossy return type produced 14 of the 20 type
    errors that had accumulated unseen in these handlers (blueprintx#190).

    ``port`` is the only non-string field: ``urlparse`` already returns it as an
    ``int``, and the handlers pass it to drivers that expect one.

    Attributes
    ----------
    user : str or None
            Database user, when the DSN carries one.
    password : str or None
            Database password, when the DSN carries one.
    host : str or None
            Hostname, when the DSN carries one.
    port : int or None
            TCP port, already coerced by ``urlparse``.
    database : str or None
            Database (schema) name, when the DSN carries one.
    """

    user: str | None
    password: str | None
    host: str | None
    port: int | None
    database: str | None


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
