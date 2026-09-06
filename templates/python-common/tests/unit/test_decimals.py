"""Unit tests for the Decimal coercion helper."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

import pytest

from src.utils.decimals import (
	_normalise_br_number,
	parse_br_number_series,
	to_decimal,
	to_decimal_strict,
)


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


@pytest.mark.parametrize("str_raw", ["2.084.960,76", "1234.56", "10,5"])
def test_parse_br_number_series_mirrors_scalar(str_raw: str) -> None:
	"""The vectorised parser agrees with the scalar normaliser on BR input."""
	pd = pytest.importorskip("pandas")
	float_scalar = float(_normalise_br_number(str_raw))
	float_series = parse_br_number_series(pd.Series([str_raw])).iloc[0]
	assert float_series == pytest.approx(float_scalar)


def test_to_decimal_strict_truncates_by_default() -> None:
	"""The strict variant defaults to ROUND_DOWN, delegating to ``to_decimal``.

	Should-fail witness for issue #268 (two ROUND_DOWN implementations, one
	domain apart): 1.999 disagrees between ROUND_DOWN (1.99) and ROUND_HALF_UP
	(2.00) at 2 places, so this fails the moment ``to_decimal_strict`` stops
	delegating and re-derives its own rounding.
	"""
	assert to_decimal_strict("1.999", 2) == Decimal("1.99")


def test_to_decimal_strict_matches_to_decimal_on_valid_input() -> None:
	"""Both doors agree on the same parseable input — the delegation contract."""
	assert to_decimal_strict("2.084.960,76", 2) == to_decimal("2.084.960,76", 2)


def test_to_decimal_strict_honours_explicit_rounding() -> None:
	"""An explicit rounding mode overrides the truncation default, like ``to_decimal``."""
	assert to_decimal_strict("1.999", 2, rounding=ROUND_HALF_UP) == Decimal("2.00")


def test_to_decimal_strict_raises_on_none() -> None:
	"""``None`` raises, unlike ``to_decimal``'s default-fallback contract."""
	with pytest.raises(ValueError, match="cannot coerce"):
		to_decimal_strict(None, 2)


def test_to_decimal_strict_raises_on_unparsable() -> None:
	"""An unparsable string raises rather than silently defaulting to 0."""
	with pytest.raises(ValueError, match="cannot coerce"):
		to_decimal_strict("not a number", 2)


def test_to_decimal_strict_negative_places_raises() -> None:
	"""A negative ``int_places`` fails fast with ``ValueError``, like ``to_decimal``."""
	with pytest.raises(ValueError, match="non-negative"):
		to_decimal_strict("1.0", -1)


def test_to_decimal_returns_the_default_when_the_context_precision_is_too_low() -> None:
	"""A finite value can still blow up in ``quantize`` — and must not leak that.

	⚠️ The trigger is ``decimal.getcontext().prec``, a property of the CALLER's context and
	not of ``value``, so the parse step cannot see it coming: a perfectly parsable number
	reaches ``quantize`` and raises ``InvalidOperation`` there. This function's contract is
	"returns ``default`` when it cannot produce a number", so the exception must not escape.
	"""
	with localcontext() as cls_ctx:
		cls_ctx.prec = 3

		assert to_decimal("123456789.987654321", 2, default=Decimal("0")) == Decimal("0")


def test_to_decimal_strict_raises_value_error_when_quantize_overflows() -> None:
	"""The strict sibling turns the SAME case into ``ValueError``, per its own contract.

	Paired with the test above: identical input and context, opposite promise. A single
	``except`` at the quantise site serves both, which is why neither can be satisfied by
	special-casing one of them.
	"""
	with localcontext() as cls_ctx:
		cls_ctx.prec = 3

		with pytest.raises(ValueError, match="cannot coerce"):
			to_decimal_strict("123456789.987654321", 2)
