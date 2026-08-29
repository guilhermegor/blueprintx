"""E-mail dispatch-flag resolution — per-block send/auto-send policy from the environment.

Moved out of ``utils/ms_office/outlook_gateway.py`` (blueprintx#118/#121): dispatch policy is
not Outlook-specific — an SMTP block obeys the same on/off switch — so it lives beside
:mod:`utils.email.html_body` instead of inside the one vendor gateway that happened to write it
first.

E-mail dispatch flags live in the environment (``.env``), one pair per e-mail block, so ops
toggles a notification without editing config. Per-block variables are
``EMAIL_SEND__<BLOCK>`` / ``EMAIL_AUTO_SEND__<BLOCK>`` (the block key upper-cased); an unset
per-block variable falls back to ``EMAIL_SEND__DEFAULTS`` / ``EMAIL_AUTO_SEND__DEFAULTS``, then
to the hard default (send on, auto-send off). Deliberately **not** read from ``emails.yaml``:
that file is tracked, so a flag there needs a branch + merge to flip one send off, while
``.env`` is git-ignored and machine-local.
"""

from __future__ import annotations

from logging import Logger
import os
from typing import TYPE_CHECKING

from utils.logs import log_message


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). mypy reads the single TYPE_CHECKING
# import (no redefinition); at runtime the try/except picks whichever layout shipped.
if TYPE_CHECKING:
	from utils.typing import type_checker
else:
	try:
		from utils.typing import type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from chassis.typing import type_checker


_DISPATCH_DEFAULT_SUFFIX: str = "DEFAULTS"
# One table mapping every recognised token to its value, rather than two sets consulted in
# turn. A token can no longer appear in both by accident, and adding a spelling is adding an
# entry. The frozensets remain as derived views for any caller that wants to ask membership.
_DICT_ENV_BOOL: dict[str, bool] = {
	**dict.fromkeys(("1", "true", "yes", "on", "y", "t"), True),
	**dict.fromkeys(("0", "false", "no", "off", "n", "f"), False),
}
_TRUE_TOKENS: frozenset[str] = frozenset(k for k, v in _DICT_ENV_BOOL.items() if v)
_FALSE_TOKENS: frozenset[str] = frozenset(k for k, v in _DICT_ENV_BOOL.items() if not v)


@type_checker
def _parse_env_bool(str_raw: str | None, bool_default: bool) -> bool:
	"""Parse an environment flag to ``bool``, returning ``bool_default`` when absent/unknown.

	Parameters
	----------
	str_raw : str | None
		The raw environment value (``None`` when the variable is unset).
	bool_default : bool
		The value returned when ``str_raw`` is ``None``, blank, or not a known token.

	Returns
	-------
	bool
		The parsed flag, or ``bool_default``.
	"""
	# An unset value and an unrecognised one mean the same thing here — fall back to the
	# default — so both are one lookup with a default rather than three branches.
	str_norm = (str_raw or "").strip().casefold()
	return _DICT_ENV_BOOL.get(str_norm, bool_default)


@type_checker
def _dispatch_flag(
	str_prefix: str, str_block_key: str, bool_default: bool, logger: Logger | None
) -> bool:
	"""Resolve one dispatch flag from the per-block then the default environment variable.

	⚠️ **Logs every variable name it consults and whether it was set** (blueprintx#121). A flag
	resolved by *deriving* an env-var name from a config key cannot be renamed alone: on a
	machine whose git-ignored ``.env`` still holds the old name, the lookup misses, falls back
	to ``__DEFAULTS``, and the send state flips with no error and no warning — worse than a
	crash, because a silent revert to the default ships instead of failing the run it broke.
	Logging the exact variable name and its set/unset status turns that silent revert into a
	line a run's log always carries, so a stale ``.env`` is diagnosed from the log alone.

	Parameters
	----------
	str_prefix : str
		The variable prefix (``"EMAIL_SEND"`` or ``"EMAIL_AUTO_SEND"``).
	str_block_key : str
		The ``emails.yaml`` block key (e.g. ``"schema_failure"``); upper-cased for the var.
	bool_default : bool
		The hard default when neither the per-block nor the ``__DEFAULTS`` variable is set.
	logger : logging.Logger | None
		Destination for the consulted-variable log lines; ``None`` prints them.

	Returns
	-------
	bool
		The resolved flag.
	"""
	str_block_var_name = f"{str_prefix}__{str_block_key.upper()}"
	str_block_var = os.getenv(str_block_var_name)
	bool_block_set = bool(str_block_var is not None and str_block_var.strip())
	log_message(
		logger,
		f"[email] dispatch: consulted {str_block_var_name} "
		f"({'set' if bool_block_set else 'unset'})",
	)
	if bool_block_set:
		return _parse_env_bool(str_block_var, bool_default)

	str_default_var_name = f"{str_prefix}__{_DISPATCH_DEFAULT_SUFFIX}"
	str_default_var = os.getenv(str_default_var_name)
	bool_default_set = bool(str_default_var is not None and str_default_var.strip())
	log_message(
		logger,
		f"[email] dispatch: consulted {str_default_var_name} "
		f"({'set' if bool_default_set else 'unset'}, hard default={bool_default})",
	)
	return _parse_env_bool(str_default_var, bool_default)


@type_checker
def resolve_dispatch(str_block_key: str, logger: Logger | None = None) -> tuple[bool, bool]:
	"""Resolve an e-mail block's ``(send, auto_send)`` flags from the environment.

	The flags are sourced from ``.env`` (loaded at startup), never from ``emails.yaml``: per
	block ``EMAIL_SEND__<BLOCK>`` / ``EMAIL_AUTO_SEND__<BLOCK>`` (block key upper-cased), with
	``EMAIL_SEND__DEFAULTS`` / ``EMAIL_AUTO_SEND__DEFAULTS`` as the fallback and a hard default
	of send on / auto-send off.

	Parameters
	----------
	str_block_key : str
		The ``emails.yaml`` block key (e.g. ``"schema_failure"``).
	logger : logging.Logger | None, optional
		Run logger for the consulted-variable audit lines (see :func:`_dispatch_flag`); when
		``None`` they print to stdout instead of being dropped.

	Returns
	-------
	tuple of (bool, bool)
		``(bool_send, bool_auto_send)``.
	"""
	bool_send = _dispatch_flag("EMAIL_SEND", str_block_key, True, logger)
	bool_auto_send = _dispatch_flag("EMAIL_AUTO_SEND", str_block_key, False, logger)
	return bool_send, bool_auto_send
