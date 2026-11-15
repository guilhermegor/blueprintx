"""Regression tests for dump-tool argv injection via the database name (blueprintx#600).

``backup()`` on the mysql/mariadb/postgres handlers builds a ``subprocess`` argv ending with
the database name as a bare positional. ``mysqldump``/``mariadb-dump``/``pg_dump`` use
getopt-style parsing, so a database name starting with ``-`` (e.g. ``--file=/tmp/pwned``) is
read as an OPTION instead of a positional, silently redirecting where the dump is written —
confirmed locally against ``pg_dump (PostgreSQL) 18.6``, where ``--file=/tmp/pwned`` was
accepted as the real ``-f``/``--file`` flag.

The fix rejects such a value at handler CONSTRUCTION (``validate_not_flag`` in
``chassis/db/infrastructure/helpers.py``), before ``backup()`` ever builds an argv — so these
tests assert the value never reaches ``subprocess.run`` at all, not merely that the argv it
would have built is safe.
"""

from __future__ import annotations

import contextlib
import importlib
from unittest.mock import patch

import pytest


DICT_MALICIOUS_DSN = {
    "mysql_handler.MySQLDatabaseHandler": "mysql://user:pass@localhost:3306/--file=/tmp/pwned",
    "mariadb_handler.MariaDBDatabaseHandler": (
        "mariadb://user:pass@localhost:3306/--file=/tmp/pwned"
    ),
    "postgres_handler.PostgresDatabaseHandler": (
        "postgresql://user:pass@localhost:5432/--file=/tmp/pwned"
    ),
}


def _handler_type(str_target: str) -> type:
    """Resolve a ``<module stem>.<class name>`` target to its handler class.

    Parameters
    ----------
    str_target : str
        ``<module stem>.<class name>`` inside ``chassis.db_schema.infrastructure``.

    Returns
    -------
    type
        The handler class.
    """
    str_module, str_class = str_target.split(".")
    cls_module = importlib.import_module(f"chassis.db_schema.infrastructure.{str_module}")
    return getattr(cls_module, str_class)


@pytest.mark.parametrize(("str_target", "str_dsn"), sorted(DICT_MALICIOUS_DSN.items()))
def test_dashed_dbname_rejected_at_construction(str_target: str, *, str_dsn: str) -> None:
    """A dashed database name is rejected when the handler is constructed.

    Parameters
    ----------
    str_target : str
        ``<module stem>.<class name>`` inside ``chassis.db_schema.infrastructure``.
    str_dsn : str
        DSN whose database segment would be read as a dump-tool option flag.
    """
    with pytest.raises(ValueError, match="database name"):
        _handler_type(str_target)(str_dsn)


@pytest.mark.parametrize(("str_target", "str_dsn"), sorted(DICT_MALICIOUS_DSN.items()))
def test_dashed_dbname_never_reaches_subprocess_run(str_target: str, *, str_dsn: str) -> None:
    """A dashed database name never reaches ``subprocess.run``.

    Parameters
    ----------
    str_target : str
        ``<module stem>.<class name>`` inside ``chassis.db_schema.infrastructure``.
    str_dsn : str
        DSN whose database segment would be read as a dump-tool option flag.
    """
    with patch("subprocess.run") as mock_run, contextlib.suppress(ValueError):
        _handler_type(str_target)(str_dsn)
    assert mock_run.call_count == 0
