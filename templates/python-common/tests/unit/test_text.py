"""Unit tests for the text normalisation helper."""

from src.utils.text import normalize_text


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
