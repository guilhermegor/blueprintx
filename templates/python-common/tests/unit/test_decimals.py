"""Unit tests for the Decimal coercion helper."""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from src.utils.decimals import to_decimal


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


def test_to_decimal_negative_places_raises() -> None:
	"""A negative ``int_places`` fails fast with ``ValueError``."""
	with pytest.raises(ValueError, match="non-negative"):
		to_decimal("1.0", -1)
