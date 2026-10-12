"""Native database connection factory for the model layer.

Reads ``DB_BACKEND`` from the environment and returns a raw DB-API 2.0
connection. There is no ORM here — the model layer issues SQL directly and
shapes results into pandas DataFrames. Drivers are imported lazily so a project
only needs the driver for the backend it actually uses.
"""

from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from utils.typing import type_checker


@type_checker
def _compose_dsn(str_backend: str) -> str:
    """Build a connection DSN from generic environment variables.

    Parameters
    ----------
    str_backend : str
            Backend key (``postgresql``, ``mariadb``, ``mysql``, ``mssql``, ``oracle``).

    Returns
    -------
    str
            A driver-specific connection string composed from ``DB_*`` env vars.
    """
    str_user = os.getenv("DB_USER", "user")
    str_password = os.getenv("DB_PASSWORD", "password")
    str_host = os.getenv("DB_HOST", "localhost")
    dict_default_ports: dict[str, str] = {
        "postgresql": "5432",
        "mariadb": "3306",
        "mysql": "3306",
        "mssql": "1433",
        "oracle": "1521",
    }
    str_port = os.getenv("DB_PORT", dict_default_ports[str_backend])
    str_name = os.getenv("DB_NAME", "app")
    if str_backend == "oracle":
        str_service = os.getenv("DB_SERVICE", "XEPDB1")
        return f"{str_host}:{str_port}/{str_service}"
    return f"{str_host}:{str_port}/{str_name}|{str_user}|{str_password}"


@type_checker
def _connect_sqlite() -> Any:
    """Open a stdlib ``sqlite3`` connection, creating the parent directory."""
    import sqlite3

    path_db = Path(os.getenv("DB_PATH", "./data/app.db"))
    path_db.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(path_db))


@type_checker
def _connect_postgresql() -> Any:
    """Open a PostgreSQL connection via ``psycopg``."""
    import psycopg

    str_dsn = os.getenv("DB_DSN")
    if str_dsn:
        return psycopg.connect(str_dsn)
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "app"),
        user=os.getenv("DB_USER", "user"),
        password=os.getenv("DB_PASSWORD", "password"),
    )


@type_checker
def _connect_mysql() -> Any:
    """Open a MySQL/MariaDB connection via ``mysql.connector``."""
    import mysql.connector

    str_dsn = os.getenv("DB_DSN")
    if str_dsn:
        return mysql.connector.connect(dsn=str_dsn)
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "app"),
        user=os.getenv("DB_USER", "user"),
        password=os.getenv("DB_PASSWORD", "password"),
    )


@type_checker
# ⚠️ The two helpers below carry the complexity hatch. Each branch is one documented
# backend/auth option in a DSN, and the branching IS the assembly: collapsing it would
# hide which option produced which connection string.
def _normalize_odbc_bool(str_value: str) -> str:  # complexity-ok: DSN option mapping
    """Map a ``.env`` boolean to the ``yes``/``no`` an ODBC keyword expects.

    ODBC keywords like ``Encrypt`` / ``TrustServerCertificate`` accept ``yes``/``no`` —
    **not** ``true``/``false`` — so a ``.env`` value of ``true`` would otherwise be passed
    verbatim and rejected. Common boolean spellings (``true``/``false``, ``1``/``0``,
    ``yes``/``no``, ``y``/``n``, ``on``/``off``, any case) are normalised; any other token is
    returned stripped-but-verbatim so driver-specific values (``strict``/``mandatory``/
    ``optional``) still pass through.

    Parameters
    ----------
    str_value : str
            The raw value read from the environment.

    Returns
    -------
    str
            ``"yes"`` / ``"no"`` for a recognised boolean, else the stripped original.
    """
    str_norm = str_value.strip().casefold()
    if str_norm in {"true", "1", "yes", "y", "on", "t"}:
        return "yes"
    if str_norm in {"false", "0", "no", "n", "off", "f"}:
        return "no"
    return str_value.strip()


@type_checker
def _connect_mssql() -> Any:  # complexity-ok: DSN assembly per auth mode
    """Open a SQL Server connection via ``pyodbc`` (SQL auth or Azure AD).

    ``DB_MSSQL_AUTH`` selects the auth mode: the default ``sql`` uses ``UID``/``PWD``;
    ``aad`` (Azure AD Interactive) prompts the browser flow and sends ``UID`` only when set.
    ``DB_ENCRYPT`` / ``DB_TRUST_SERVER_CERTIFICATE`` are appended when set (normalised to
    ``yes``/``no``) — needed for ODBC Driver 18 (which defaults ``Encrypt=yes``) against a
    server with a self-signed certificate.
    """
    import pyodbc

    str_dsn = os.getenv("DB_DSN")
    if str_dsn:
        return pyodbc.connect(str_dsn)
    str_driver = os.getenv("DB_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    str_auth = os.getenv("DB_MSSQL_AUTH", "sql").lower()
    list_parts = [
        f"DRIVER={{{str_driver}}}",
        f"SERVER={os.getenv('DB_HOST', 'localhost')},{os.getenv('DB_PORT', '1433')}",
        f"DATABASE={os.getenv('DB_NAME', 'app')}",
    ]
    if str_auth in {"aad", "ad", "azure", "activedirectoryinteractive"}:
        list_parts.append("Authentication=ActiveDirectoryInteractive")
        str_user = os.getenv("DB_USER")
        if str_user:
            list_parts.append(f"UID={str_user}")
    else:
        list_parts.append(f"UID={os.getenv('DB_USER', 'user')}")
        list_parts.append(f"PWD={os.getenv('DB_PASSWORD', 'password')}")
    str_encrypt = os.getenv("DB_ENCRYPT")
    if str_encrypt:
        list_parts.append(f"Encrypt={_normalize_odbc_bool(str_encrypt)}")
    str_trust = os.getenv("DB_TRUST_SERVER_CERTIFICATE")
    if str_trust:
        list_parts.append(f"TrustServerCertificate={_normalize_odbc_bool(str_trust)}")
    return pyodbc.connect(";".join(list_parts) + ";")


@type_checker
def _connect_oracle() -> Any:
    """Open an Oracle connection via ``oracledb``."""
    import oracledb

    str_dsn = os.getenv("DB_DSN") or _compose_dsn("oracle")
    return oracledb.connect(
        user=os.getenv("DB_USER", "user"),
        password=os.getenv("DB_PASSWORD", "password"),
        dsn=str_dsn,
    )


# Engine name -> connection builder. Module-level so the engine NAMES have exactly ONE
# source — the factory below and the `config/queries/<engine>/` directory layout both read
# these names instead of re-spelling the list.
#
# ⚠️ It must FOLLOW the `_connect_*` functions it maps to — the dict is evaluated at import,
# so those names have to exist by then. The placement is a language constraint, not
# disorganisation; signposted here so nobody "tidies" it to the top of the file.
_DICT_BUILDERS: dict[str, Callable[[], Any]] = {
    "sqlite": _connect_sqlite,
    "postgresql": _connect_postgresql,
    "mariadb": _connect_mysql,
    "mysql": _connect_mysql,
    "mssql": _connect_mssql,
    "oracle": _connect_oracle,
}

# The supported engine names, derived from the dispatch map so the two cannot drift.
SET_BACKENDS: frozenset[str] = frozenset(_DICT_BUILDERS)

_STR_DEFAULT_BACKEND = "sqlite"


@type_checker
def active_backend() -> str:
    """Return the configured engine name — the single reader of ``DB_BACKEND``.

    Returns
    -------
    str
            The lower-cased engine name, defaulting to ``sqlite``.

    Raises
    ------
    ValueError
            If ``DB_BACKEND`` does not name a supported engine.

    Notes
    -----
    Everything that needs to know the engine calls this, so the default exists in exactly
    one place and cannot disagree with itself. That matters more than it looks: the query
    loader resolves ``config/queries/<engine>/`` from this value, so a second reader with
    its own default would file queries under one engine and connect with another.

    It is validated **here**, not only where the connection is opened, because the value is
    used to build a filesystem path before any connection exists. Rejecting it at the single
    reader means an unsupported engine fails with a message naming the supported ones,
    rather than as a confusing missing-query error somewhere downstream.

    ``DB_BACKEND`` lives in a git-ignored ``.env``, which no gate over tracked files can
    validate. Assume every long-lived machine's copy is stale — ``bin/ensure_env.sh``
    deliberately never overwrites an existing ``.env`` — and let the runtime be the guard.
    """
    load_dotenv()
    str_backend = os.getenv("DB_BACKEND", _STR_DEFAULT_BACKEND).lower()
    if str_backend not in SET_BACKENDS:
        str_supported = ", ".join(sorted(SET_BACKENDS))
        raise ValueError(f"Unsupported DB_BACKEND {str_backend!r}. Supported: {str_supported}")
    return str_backend


@type_checker
def build_connection() -> Any:
    """Build a native DB-API connection from environment configuration.

    Returns
    -------
    Any
            An open DB-API 2.0 connection for the configured backend.

    Notes
    -----
    Reads ``DB_BACKEND`` via :func:`active_backend`, which rejects an unsupported value
    (propagating :class:`ValueError`) before any lookup here. Supported: ``sqlite``,
    ``postgresql``, ``mariadb``, ``mysql``, ``mssql``, ``oracle``. SQLite uses ``DB_PATH``;
    the rest read ``DB_DSN`` first, then compose from ``DB_*`` vars.
    """
    return _DICT_BUILDERS[active_backend()]()
