"""Decimal helpers for precise numeric fields.

Money, percentages and measurements must never round-trip through ``float`` —
IEEE-754 cannot represent most decimal fractions exactly and the error
accumulates silently across thousands of rows. Build every precise value here as
a :class:`~decimal.Decimal` from its string form and quantise it to the number of
decimal places the domain mandates.

The default rounding is ``ROUND_DOWN`` (truncation): deterministic, never inflates
a value, and free of the directional bias that compounds when summing many rows.
Pass ``rounding`` explicitly when the domain demands a different mode — e.g.
``ROUND_HALF_UP`` for tax or regulatory reporting.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal, InvalidOperation
from typing import TYPE_CHECKING

import pandas as pd


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


# Truncation is the safe generic default; override per call when the domain
# explicitly requires commercial / regulatory rounding.
_DEFAULT_ROUNDING = ROUND_DOWN

# ``bool`` is listed explicitly: it is a subclass of ``int`` but the runtime type-checker
# treats it as a distinct type, and ``_parse`` deliberately accepts it (mapping True/False to
# ``default`` rather than 1/0). Omitting it would make the checker reject a tolerated input.
NumericLike = str | int | float | bool | Decimal | None


@type_checker
def to_decimal(
	value: NumericLike,
	int_places: int,
	default: Decimal = Decimal("0"),
	rounding: str = _DEFAULT_ROUNDING,
) -> Decimal:
	"""Coerce ``value`` to a quantised :class:`~decimal.Decimal`.

	Parameters
	----------
	value : NumericLike
		Raw value. Strings may carry Brazilian formatting (``.`` thousands
		separator and ``,`` decimal separator); both are normalised. ``None``,
		empty strings and unparsable values fall back to ``default``.
	int_places : int
		Number of decimal places to quantise to (non-negative).
	default : Decimal, optional
		Value returned when ``value`` is missing or unparsable, by default
		``Decimal("0")``.
	rounding : str, optional
		A :mod:`decimal` rounding mode (e.g. ``ROUND_DOWN``, ``ROUND_HALF_UP``);
		by default ``ROUND_DOWN`` (truncation).

	Returns
	-------
	Decimal
		``value`` quantised to ``int_places`` decimal places using ``rounding``.

	Raises
	------
	ValueError
		If ``int_places`` is negative.
	"""
	if int_places < 0:
		raise ValueError("int_places must be non-negative")
	cls_quantum = Decimal(1).scaleb(-int_places)
	cls_raw = _parse(value, default)
	return cls_raw.quantize(cls_quantum, rounding=rounding)


@type_checker
def _parse(value: NumericLike, default: Decimal) -> Decimal:
	"""Parse ``value`` into an unquantised Decimal, falling back to ``default``.

	Parameters
	----------
	value : NumericLike
		Raw value to parse.
	default : Decimal
		Fallback for missing or unparsable input.

	Returns
	-------
	Decimal
		The parsed value, or ``default``.
	"""
	if value is None:
		return default
	if isinstance(value, Decimal):
		return value
	if isinstance(value, bool):
		# bool is a subclass of int; reject it so True/False never become 1/0.
		return default
	if isinstance(value, int):
		return Decimal(value)
	if isinstance(value, float):
		# Go through ``repr`` so the shortest round-tripping decimal is used
		# instead of the full binary expansion.
		return Decimal(repr(value))
	str_clean = _normalise_br_number(str(value))
	if str_clean == "":
		return default
	try:
		return Decimal(str_clean)
	except InvalidOperation:
		return default


@type_checker
def _normalise_br_number(str_value: str) -> str:
	"""Normalise a Brazilian-formatted numeric string to a Decimal-parseable form.

	Handles ``"2.084.960.022,76"`` -> ``"2084960022.76"`` and trims whitespace.
	A plain ``"1234.56"`` (no comma) is left untouched.

	Parameters
	----------
	str_value : str
		Raw numeric string.

	Returns
	-------
	str
		A string Decimal can parse, or ``""`` when empty.
	"""
	str_stripped = str_value.strip()
	if str_stripped == "":
		return ""
	if "," in str_stripped:
		return str_stripped.replace(".", "").replace(",", ".")
	return str_stripped


@type_checker
def parse_br_number_series(series_value: pd.Series) -> pd.Series:
	"""Vectorised parse of a Brazilian-formatted numeric column to ``float``.

	Handles thousands ``.``, decimal ``,`` and parenthesised negatives ``(x)`` ->
	``-x``; non-numeric cells become ``NaN``. The vectorised sibling of
	:func:`_normalise_br_number` — and it MUST mirror that scalar rule:

	The ``.`` is treated as a **thousands separator only when the cell also carries a
	``,`` decimal separator** (true BR formatting). A cell with no comma is left
	intact, so a value already read as a ``float`` (``5.0``) or a plain decimal
	string (``"1234.56"``) keeps its decimal point instead of being inflated tenfold
	(``5.0`` -> ``50``). pandas reads count columns as ``float64`` when NaNs are
	present, so an unconditional ``.str.replace(".", "")`` would silently corrupt
	them — the two helpers parsing one format must never diverge.

	``pandas`` is imported lazily so this module stays importable in environments
	that ship the Decimal helpers without pandas.

	Parameters
	----------
	series_value : pandas.Series
		The raw string (or mixed) column.

	Returns
	-------
	pandas.Series
		The parsed ``float`` column (``NaN`` where unparsable).
	"""
	import pandas as pd

	series_str = series_value.astype(str)
	series_has_comma = series_str.str.contains(",", regex=False)
	# When a comma is present the cell is Brazilian-formatted, so the thousands dot is
	# removed and the decimal comma becomes a dot.
	series_br = series_str.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
	# When no comma is present the existing dot already marks the decimal place and is kept.
	series_clean = (
		series_str.where(~series_has_comma, series_br)
		.str.replace("(", "-", regex=False)
		.str.replace(")", "", regex=False)
	)
	return pd.to_numeric(series_clean, errors="coerce")
