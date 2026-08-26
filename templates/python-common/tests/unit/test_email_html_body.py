"""Unit tests for the plain-text-to-HTML e-mail body conversion."""

from src.utils.email.html_body import to_html_body


def test_to_html_body_converts_newlines() -> None:
	"""Plain-text newlines become <br>; already-HTML bodies are left untouched."""
	assert "<br>" in to_html_body("line one\nline two")


def test_to_html_body_leaves_html_body_untouched() -> None:
	"""A body already containing a <p> tag is returned unchanged."""
	assert to_html_body("<p>already html</p>") == "<p>already html</p>"
