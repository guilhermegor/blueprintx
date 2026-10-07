"""Resolve a SQL query file from the engine directory the configuration selects.

Queries live at ``config/queries/<engine>/<table>__<purpose>.sql``. The engine is a
**directory**, not a filename prefix, so the wrong dialect is *unreachable* rather than
merely rejected: no code path can hand T-SQL to a SQLite connection, and nothing has to
notice. A check is always second-best to a structure in which the wrong state cannot be
represented.

The directory names the **engine**, not the database instance — two SQL Server databases
share one ``mssql/`` directory. The day routing has to be per-instance, the directory
becomes a *connection* name and the engine is looked up from that connection's config.

This module reads no environment variable on purpose. ``DB_BACKEND`` lives in a
git-ignored ``.env``, so a repository-only check cannot validate the backend a local or
deployed environment actually selects — the file is never committed and CI never has one.
The guard therefore has to run at **runtime**, at the single funnel the value passes
through. Keeping the backend an argument leaves the rule pure and testable on any machine;
each skeleton's thin caller supplies it from the one function that reads the environment.

Because that value arrives from outside the repository, it is **untrusted input**, not a
trusted constant: both it and the filename are validated as single path segments before
being joined. See :func:`_require_bare_name`.

Resolution happens here, and not where the query is executed, because the executor
receives only the SQL **text** — by then nothing can tell which dialect it holds. That is
precisely why a mismatch used to surface as a ``sqlite3.OperationalError`` from inside
pandas, layers below its cause and after every input had already been read.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). TYPE_CHECKING stubs the decorator's shape
# locally instead of importing: mypy treats a try/except import as executed code and flags
# the redefinition once actually checked, so this branch can't pick either layout
# (blueprintx#360). Runtime still resolves the real engine via try/except below.
if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    _F = TypeVar("_F", bound=Callable[..., object])

    def type_checker(fn: _F) -> _F:
        """Type-only stub — see src/utils/CLAUDE.md."""
else:
    try:
        from utils.typing import type_checker
    except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
        from chassis.typing import type_checker


@type_checker
def _require_bare_name(str_value: str, str_label: str, str_why: str) -> None:
    """Reject a value that is anything other than a single path segment.

    Parameters
    ----------
    str_value : str
            The candidate segment.
    str_label : str
            What the value is, for the error message (e.g. ``"Query name"``).
    str_why : str
            The consequence of accepting it, appended to the error message.

    Raises
    ------
    ValueError
            If the value is empty, is a relative-navigation segment, or carries a
            separator of either flavour.

    Notes
    -----
    Both segments of ``queries/<engine>/<filename>`` come from outside this module —
    the filename from a caller, the engine from a git-ignored ``.env`` — so both are
    untrusted and get the same rule. ``pathlib``'s ``/`` operator **replaces** the left
    side when the right is absolute, so an unvalidated ``DB_BACKEND=/tmp`` would silently
    relocate the whole lookup; ``..`` would walk out of the queries tree.

    Backslash is rejected explicitly because it is not a separator on POSIX: a Windows-shaped
    value would otherwise pass here and behave differently on the machine it was written for.
    """
    if (
        not str_value
        or str_value in {".", ".."}
        or "/" in str_value
        or "\\" in str_value
        or Path(str_value).name != str_value
    ):
        raise ValueError(f"{str_label} {str_value!r} must be a single path segment — {str_why}")


@type_checker
def _engine_dirs(path_queries_root: Path) -> list[Path]:
    """List the per-engine directories under the queries root, sorted by name.

    Parameters
    ----------
    path_queries_root : pathlib.Path
            The ``config/queries`` directory holding one subdirectory per engine.

    Returns
    -------
    list of pathlib.Path
            Every engine directory, or an empty list when the root does not exist.
    """
    if not path_queries_root.is_dir():
        return []
    return sorted(
        (path_engine for path_engine in path_queries_root.iterdir() if path_engine.is_dir()),
        key=lambda path_engine: path_engine.name,
    )


@type_checker
def load_query(  # complexity-ok: each branch is a documented lookup failure with its own remedy
    str_filename: str, str_backend: str, path_queries_root: Path
) -> str:
    """Read the SQL text filed for ``str_backend`` under the queries root.

    Parameters
    ----------
    str_filename : str
            Bare query filename, e.g. ``example_entity__select_active.sql``. It must not
            carry a directory component: the engine directory is derived from the configured
            backend, never spelled by the caller.
    str_backend : str
            The active engine, supplied by the single function that reads ``DB_BACKEND``. It
            must also be a single path segment — it comes from a git-ignored ``.env``, which
            makes it untrusted input, not a trusted constant.
    path_queries_root : pathlib.Path
            The ``config/queries`` directory holding one subdirectory per engine.

    Returns
    -------
    str
            The SQL text, read as UTF-8.

    Raises
    ------
    ValueError
            If ``str_filename`` or ``str_backend`` is anything other than a single path
            segment, which would bypass the engine routing this function exists to enforce.
    FileNotFoundError
            If no file is filed for that engine. The message names the engines that *do* hold
            the query, so a typo and a misconfiguration do not read identically.
    """
    _require_bare_name(
        str_filename,
        "Query name",
        "the engine directory is derived from the configured backend, so spelling one here "
        "would route around the very check this loader exists to make.",
    )
    _require_bare_name(
        str_backend,
        "Backend",
        "it names one directory under the queries root. It arrives from a git-ignored .env, "
        "so it is untrusted input: an absolute value would relocate the lookup entirely and "
        "'..' would escape the queries tree.",
    )

    path_query = path_queries_root / str_backend / str_filename
    if path_query.is_file():
        return path_query.read_text(encoding="utf-8")

    list_dirs = _engine_dirs(path_queries_root)
    list_carriers = [
        path_engine.name for path_engine in list_dirs if (path_engine / str_filename).is_file()
    ]
    if list_carriers:
        raise FileNotFoundError(
            f"Query {str_filename!r} is not filed for engine {str_backend!r} "
            f"(looked in {path_query}), but it EXISTS for: {', '.join(list_carriers)}. "
            f"Either DB_BACKEND names the wrong engine, or the query was filed under one."
        )

    str_present = ", ".join(path_engine.name for path_engine in list_dirs) or "<none>"
    raise FileNotFoundError(
        f"Query {str_filename!r} exists for no engine under {path_queries_root} "
        f"(engine directories present: {str_present}). Check the filename."
    )
