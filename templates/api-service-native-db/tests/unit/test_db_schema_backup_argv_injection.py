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

import importlib
from unittest.mock import patch

import pytest


# Target -> a DSN whose database segment is a real mysqldump/pg_dump long option. Each handler's
# ``_parse_dsn`` reads it via ``urlparse(...).path.lstrip("/")``, landing in ``self.dbname``.
DICT_MALICIOUS_DSN = {
    "mysql_handler.MySQLDatabaseHandler": "mysql://user:pass@localhost:3306/--file=/tmp/pwned",
    "mariadb_handler.MariaDBDatabaseHandler": (
        "mariadb://user:pass@localhost:3306/--file=/tmp/pwned"
    ),
    "postgres_handler.PostgresDatabaseHandler": (
        "postgresql://user:pass@localhost:5432/--file=/tmp/pwned"
    ),
}


@pytest.mark.parametrize(("str_target", "str_dsn"), sorted(DICT_MALICIOUS_DSN.items()))
def test_dashed_dbname_rejected_before_subprocess_runs(str_target: str, str_dsn: str) -> None:
    """A dashed database name is rejected at construction, never reaching ``subprocess.run``.

    Parameters
    ----------
    str_target : str
        ``<module stem>.<class name>`` inside ``chassis.db_schema.infrastructure``.
    str_dsn : str
        DSN whose database segment would be read as a dump-tool option flag.
    """
    str_module, str_class = str_target.split(".")
    cls_module = importlib.import_module(f"chassis.db_schema.infrastructure.{str_module}")
    cls_handler_type = getattr(cls_module, str_class)
    with patch("subprocess.run") as mock_run, pytest.raises(ValueError, match="database name"):
        cls_handler_type(str_dsn)
    assert mock_run.call_count == 0
