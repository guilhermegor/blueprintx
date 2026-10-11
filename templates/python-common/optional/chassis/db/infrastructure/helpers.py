"""Utility helpers shared by all storage backends."""

from __future__ import annotations

import re
from typing import TypedDict
import uuid

from chassis.db.domain.ports import Record
from chassis.typing.decorators import type_checker


_RE_SQL_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


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
def validate_not_flag(value: str, label: str) -> None:
    """Reject a value a getopt-based dump tool would parse as an option flag.

    A ``backup()`` implementation passes ``value`` (typically the database
    name) as the trailing bare positional argument to a dump CLI
    (``mysqldump``, ``mariadb-dump``, ``pg_dump``). Those tools use
    getopt-style parsing, where any positional beginning with ``-`` is read
    as an option instead of a database name — a DSN whose database segment
    is e.g. ``--result-file=/etc/passwd`` is silently accepted as a real
    flag, redirecting where the dump is written. Call this once, at handler
    construction, right after the value is parsed out of the DSN.

    Parameters
    ----------
    value : str
        Value about to be placed in a dump-tool argv as a bare positional.
    label : str
        Human-readable name used in the raised error message.

    Raises
    ------
    ValueError
        If ``value`` starts with ``-``.
    """
    if value.startswith("-"):
        raise ValueError(f"{label} must not start with '-' (got {value!r})")


@type_checker
def validate_sql_identifier(value: str, label: str) -> None:
    """Reject a table or column name that is not a plain SQL identifier.

    The handlers interpolate ``table`` and ``id_field`` into SQL text, because a driver cannot
    bind an identifier as a parameter. They come from configuration, so this is not an
    injection path today, but nothing enforced it. Call this once, in the handler constructor,
    before the first statement is built; the ``# noqa: S608`` on those statements is then
    justified rather than assumed.

    Parameters
    ----------
    value : str
        Name about to be placed in SQL text.
    label : str
        Human-readable name used in the raised error message.

    Raises
    ------
    ValueError
        If ``value`` is not ``[A-Za-z_][A-Za-z0-9_]*``.
    """
    if not _RE_SQL_IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must match [A-Za-z_][A-Za-z0-9_]* (got {value!r})")


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
