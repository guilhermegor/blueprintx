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


# Truncation is the safe generic default; override per call when the domain
# explicitly requires commercial / regulatory rounding.
_DEFAULT_ROUNDING = ROUND_DOWN

NumericLike = str | int | float | Decimal | None


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
