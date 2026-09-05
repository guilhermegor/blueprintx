"""Reference pattern: a filter that REMOVES entregável records needs a kill switch.

Rationale, the incident that produced it (a hard-coded filter dropped whole fund classes
from a regulatory delivery with no flag and no measured price), and the "one categorical
field is not a fact" corollary all live in this leaf's ``CLAUDE.md`` (blueprintx#161) — this
module is only the runnable shape of that convention: a kill switch that resolves to the
SAFE side on both an unset variable and a typo'd one, plus a filter call that always returns
the measured price (rows before/after/dropped) instead of only the filtered frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from logging import Logger
import os

import pandas as pd

from utils.logs import log_message
from utils.typing import TypeChecker, type_checker


# ``pandas`` is imported for real (not TYPE_CHECKING-only) because beartype's runtime check
# resolves ``pd.DataFrame`` against this module's globals at call time — a TYPE_CHECKING-only
# alias leaves ``pd`` unbound at runtime and the check fails. Still annotation-only per
# .layer-policy.yaml: ``pd`` is never called, only used as a type.


# One table mapping every recognised env token to bool, mirroring
# utils/email/dispatch.py's _DICT_ENV_BOOL. Kept local (not imported from utils/) because a
# model-layer convention file must stay self-contained — utils/ is a seam for vendors, not a
# place model/ borrows business rules from.
_DICT_ENV_BOOL: dict[str, bool] = {
	**dict.fromkeys(("1", "true", "yes", "on", "y", "t"), True),
	**dict.fromkeys(("0", "false", "no", "off", "n", "f"), False),
}


@dataclass(frozen=True)
class ScopeFilterPrice(metaclass=TypeChecker):
	"""The measured price of one scope-filter run.

	Returned by every call to :func:`apply_scope_filter`, active or not, so the cost of the
	rule is visible at every run instead of only in a test that happens to cover it.

	Parameters
	----------
	int_rows_before : int
		Row count before the filter.
	int_rows_after : int
		Row count after the filter (equals ``int_rows_before`` when inactive).
	int_rows_dropped : int
		Rows removed by the filter (``0`` when inactive).
	bool_filter_active : bool
		Whether the kill switch resolved on for this run.
	"""

	int_rows_before: int
	int_rows_after: int
	int_rows_dropped: int
	bool_filter_active: bool


@type_checker
def resolve_kill_switch(
	str_env_var: str, bool_default: bool, logger: Logger | None = None
) -> bool:
	"""Resolve a scope-filter kill switch from the environment, safe-side on unset/unknown.

	An unset variable and an unrecognised token (a typo) resolve to the SAME value —
	``bool_default`` — so a mistyped ``.env`` cannot silently flip production back to the
	expensive side. ``bool_default`` must be the cheap-to-fail side for the business (see
	this leaf's ``CLAUDE.md``): sub-delivering a regulatory class costs money per fund per
	day, over-delivering costs nothing, so a scope-narrowing filter should default OFF.

	Parameters
	----------
	str_env_var : str
		The environment variable naming this kill switch (e.g.
		``"SCOPE_FILTER_EXCLUDE_FII"``).
	bool_default : bool
		Returned when the variable is unset, blank, or an unrecognised token.
	logger : logging.Logger | None, optional
		Destination for the consulted-variable log line; ``None`` prints it.

	Returns
	-------
	bool
		Whether the exclusion is active for this run.
	"""
	str_raw = os.getenv(str_env_var)
	bool_set = bool(str_raw is not None and str_raw.strip())
	str_norm = (str_raw or "").strip().casefold()
	bool_resolved = _DICT_ENV_BOOL.get(str_norm, bool_default)
	log_message(
		logger,
		f"[scope_filter] consulted {str_env_var} "
		f"({'set' if bool_set else 'unset'}, resolved={bool_resolved})",
	)
	return bool_resolved


@type_checker
def apply_scope_filter(
	df_input: pd.DataFrame,
	str_column: str,
	set_excluded_values: frozenset[str],
	str_env_var: str,
	bool_default_exclude: bool,
	logger: Logger | None = None,
) -> tuple[pd.DataFrame, ScopeFilterPrice]:
	"""Apply (or skip) a record-removing filter, and MEASURE the price.

	Parameters
	----------
	df_input : pandas.DataFrame
		The frame to filter, returned unmodified when the kill switch resolves off.
	str_column : str
		Column whose values decide exclusion.
	set_excluded_values : frozenset of str
		Values in ``str_column`` that mark a row for exclusion when the switch is on.
	str_env_var : str
		Kill-switch environment variable (see :func:`resolve_kill_switch`).
	bool_default_exclude : bool
		Safe-side default forwarded to :func:`resolve_kill_switch` — see that function for
		why this must be the cheap-to-fail side, never "whatever the code already did".
	logger : logging.Logger | None, optional
		Forwarded to :func:`resolve_kill_switch`.

	Returns
	-------
	tuple of (pandas.DataFrame, ScopeFilterPrice)
		The (possibly filtered) frame, and the measured price of this run.
	"""
	int_rows_before = len(df_input)
	bool_active = resolve_kill_switch(str_env_var, bool_default_exclude, logger)
	if not bool_active:
		return df_input, ScopeFilterPrice(
			int_rows_before=int_rows_before,
			int_rows_after=int_rows_before,
			int_rows_dropped=0,
			bool_filter_active=False,
		)
	df_output = df_input[~df_input[str_column].isin(set_excluded_values)]
	int_rows_after = len(df_output)
	return df_output, ScopeFilterPrice(
		int_rows_before=int_rows_before,
		int_rows_after=int_rows_after,
		int_rows_dropped=int_rows_before - int_rows_after,
		bool_filter_active=True,
	)
