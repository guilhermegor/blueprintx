"""Unit tests for the plain-text-to-HTML e-mail body conversion."""

from src.utils.email.html_body import to_html_body


def test_to_html_body_converts_newlines() -> None:
    """Plain-text newlines become <br>; already-HTML bodies are left untouched."""
    assert "<br>" in to_html_body("line one\nline two")


def test_to_html_body_leaves_html_body_untouched() -> None:
    """A body already containing a <p> tag is returned unchanged."""
    assert to_html_body("<p>already html</p>") == "<p>already html</p>"


def test_to_html_body_escapes_plain_text_markup() -> None:
    """Plain text carrying '<', '&', or a full tag is escaped, not rendered as markup.

    Without escaping, a value like a filename or a pasted name containing '<'/'>' would be
    interpreted by the mail client as a tag instead of shown as the literal character — and a
    value containing a full tag (e.g. an injected <script>) would render as real markup.
    """
    str_result = to_html_body("report <final>.xlsx & <script>alert(1)</script>")
    assert "<script>" not in str_result
    assert "&lt;final&gt;" in str_result
    assert "&amp;" in str_result
