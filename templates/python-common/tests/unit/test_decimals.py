"""Unit tests for the Decimal coercion helper."""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from src.utils.decimals import _normalise_br_number, parse_br_number_series, to_decimal


def test_to_decimal_truncates_by_default() -> None:
	"""The default rounding mode is ROUND_DOWN (truncation)."""
	assert to_decimal("1.999", 2) == Decimal("1.99")


def test_to_decimal_honours_explicit_rounding() -> None:
	"""An explicit rounding mode overrides the truncation default."""
	assert to_decimal("1.999", 2, rounding=ROUND_HALF_UP) == Decimal("2.00")


def test_to_decimal_parses_brazilian_formatted_string() -> None:
	"""A BR-formatted string (dot thousands, comma decimal) is normalised."""
	assert to_decimal("2.084.960,76", 2) == Decimal("2084960.76")


def test_to_decimal_float_uses_shortest_repr() -> None:
	"""A float is parsed via repr, avoiding binary-expansion noise."""
	assert to_decimal(0.1, 2) == Decimal("0.10")


def test_to_decimal_none_returns_default() -> None:
	"""``None`` falls back to the supplied default."""
	assert to_decimal(None, 2, default=Decimal("-1")) == Decimal("-1.00")


def test_to_decimal_unparsable_returns_default() -> None:
	"""An unparsable string falls back to the default."""
	assert to_decimal("not a number", 2) == Decimal("0.00")


def test_to_decimal_rejects_bool() -> None:
	"""``bool`` is rejected (never coerced to 1/0) and returns the default."""
	assert to_decimal(True, 2) == Decimal("0.00")


@pytest.mark.parametrize(
	"value",
	[
		float("nan"),
		float("inf"),
		float("-inf"),
		Decimal("NaN"),
		Decimal("Infinity"),
		Decimal("-Infinity"),
		"nan",
		"inf",
		"NaN",
	],
)
def test_to_decimal_non_finite_returns_default(value: float | Decimal | str) -> None:
	"""Non-finite input (NaN/±Inf from float, Decimal, or string) falls back to default.

	Parameters
	----------
	value : float or Decimal or str
		A non-finite value the coercion contract must map to ``default`` rather than
		leak (a leaked ``Decimal('NaN')`` raises ``InvalidOperation`` downstream).
	"""
	cls_result = to_decimal(value, 2, default=Decimal("-1"))
	assert cls_result == Decimal("-1.00")
	assert cls_result.is_finite()


def test_to_decimal_negative_places_raises() -> None:
	"""A negative ``int_places`` fails fast with ``ValueError``."""
	with pytest.raises(ValueError, match="non-negative"):
		to_decimal("1.0", -1)


def test_parse_br_number_series_handles_br_and_plain() -> None:
	"""BR-formatted cells normalise; plain decimals/floats keep their point."""
	pd = pytest.importorskip("pandas")
	series_in = pd.Series(["2.084.960,76", "1234.56", "5.0", "(3,5)", "x"])
	series_out = parse_br_number_series(series_in)
	assert series_out.iloc[0] == pytest.approx(2084960.76)
	assert series_out.iloc[1] == pytest.approx(1234.56)
	# A plain float-repr cell keeps its value and is never inflated tenfold.
	assert series_out.iloc[2] == pytest.approx(5.0)
	assert series_out.iloc[3] == pytest.approx(-3.5)
	assert pd.isna(series_out.iloc[4])


def test_parse_br_number_series_mirrors_scalar() -> None:
	"""The vectorised parser agrees with the scalar normaliser on BR input."""
	pd = pytest.importorskip("pandas")
	for str_raw in ("2.084.960,76", "1234.56", "10,5"):
		float_scalar = float(_normalise_br_number(str_raw))
		float_series = parse_br_number_series(pd.Series([str_raw])).iloc[0]
		assert float_series == pytest.approx(float_scalar)
