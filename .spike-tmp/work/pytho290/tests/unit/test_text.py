"""Unit tests for the text normalisation helper."""

from src.utils.text import normalize_text, safe_str


def test_normalize_text_strips_accents_and_casefolds() -> None:
	"""Accents are removed and the result is lower-cased (casefold)."""
	assert normalize_text("PRODUÇÃO") == "producao"


def test_normalize_text_collapses_and_trims_whitespace() -> None:
	"""Tabs, doubled and edge whitespace collapse to single spaces and trim."""
	assert normalize_text("  Banco   do \t Brasil  ") == "banco do brasil"


def test_normalize_text_enables_allow_list_membership() -> None:
	"""Mixed-case accented input matches a normalised allow-list."""
	set_production = {"prod", "production", "producao"}
	assert normalize_text("Produção") in set_production


def test_normalize_text_empty_string_returns_empty() -> None:
	"""An empty string normalises to an empty string."""
	assert normalize_text("") == ""


def test_safe_str_nan_returns_default() -> None:
	"""A float NaN never becomes the literal string 'nan'."""
	assert safe_str(float("nan")) == ""
	assert safe_str(float("nan"), default="-") == "-"


def test_safe_str_none_returns_default() -> None:
	"""``None`` returns the default, not the string 'None'."""
	assert safe_str(None) == ""


def test_safe_str_normal_values_stringify_and_strip() -> None:
	"""Real values are stringified and trimmed."""
	assert safe_str("  hi  ") == "hi"
	assert safe_str(42) == "42"
