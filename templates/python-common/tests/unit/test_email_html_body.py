"""Unit tests for the plain-text-to-HTML e-mail body conversion."""

from src.utils.email.html_body import to_html_body


def test_to_html_body_converts_newlines() -> None:
	"""Plain-text newlines become <br>; already-HTML bodies are left untouched."""
	assert "<br>" in to_html_body("line one\nline two")


def test_to_html_body_leaves_html_body_untouched() -> None:
	"""A body already containing a <p> tag is returned unchanged."""
	assert to_html_body("<p>already html</p>") == "<p>already html</p>"


@pytest.mark.parametrize(
	("str_fragment", "bool_present"),
	[("<script>", False), ("&lt;final&gt;", True), ("&amp;", True)],
	ids=["no-live-tag-survives", "angle-brackets-are-escaped", "ampersands-are-escaped"],
)
def test_to_html_body_escapes_plain_text_markup(str_fragment: str, bool_present: bool) -> None:
	"""Plain text carrying '<', '&', or a full tag is escaped, not rendered as markup.

	Without escaping, a value like a filename or a pasted name containing '<'/'>' would be
	interpreted by the mail client as a tag instead of shown as the literal character — and a
	value containing a full tag (e.g. an injected <script>) would render as real markup.

	Parameters
	----------
	str_fragment : str
		A fragment the escaped body must, or must not, contain.
	bool_present : bool
		Which of the two.
	"""
	str_result = to_html_body("report <final>.xlsx & <script>alert(1)</script>")

	assert (str_fragment in str_result) is bool_present
