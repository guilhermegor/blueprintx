"""Shared CI-or-local verdict for the gates that honour a local-only escape hatch."""

import os


TUPLE_LOCAL_SIGNALS = ("PRE_COMMIT",)
STR_CI_VAR = "CI"
TUPLE_PRESENCE_MARKERS = ("GITHUB_ACTIONS",)
TUPLE_FALSY_ENV = ("", "0", "false", "no")


def has_terminal() -> bool:
    """Return whether the process has a controlling terminal (I/O seam).

    Returns
    -------
    bool
        True when ``/dev/tty`` can be opened. A headless runner that invokes ``pre-commit``
        (and so inherits ``PRE_COMMIT``) has none; a developer committing from a shell does.
    """
    try:
        with open("/dev/tty"):
            return True
    except OSError:
        return False


def is_local() -> bool:
    """Return whether positive evidence says this is a local ``pre-commit`` run (I/O seam).

    Returns
    -------
    bool
        True only when a local signal is set, a controlling terminal exists and no CI
        marker contradicts it. An unknown runner carries no such evidence, so it is not local.
    """
    str_ci = os.environ.get(STR_CI_VAR, "").strip().lower()
    return (
        any(str_s in os.environ for str_s in TUPLE_LOCAL_SIGNALS)
        and has_terminal()
        and not any(str_m in os.environ for str_m in TUPLE_PRESENCE_MARKERS)
        and str_ci in TUPLE_FALSY_ENV
    )


def is_ci() -> bool:
    """Return whether the process must be treated as CI (fails closed, blueprintx#981).

    Returns
    -------
    bool
        The negation of ``is_local``.
    """
    return not is_local()
