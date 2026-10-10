"""Unit tests for the plain-text-to-HTML e-mail body conversion."""

from html import escape

import pytest

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


def test_to_html_body_tag_lookalike_is_escaped_as_plain_text() -> None:
    """Should-fail witness: ``<bravo>`` merely starts with ``<br`` and is not a tag."""
    assert to_html_body("<bravo>\nnext") == "&lt;bravo&gt;<br>\nnext"


def test_to_html_body_p_tag_with_attributes_is_left_untouched() -> None:
    """Should-fail witness: ``<p class=...>`` is real HTML and must not be escaped."""
    str_html = '<p class="intro">text</p>'

    assert to_html_body(str_html) == str_html


@pytest.mark.parametrize(
    "str_html",
    ["a<br>b", "a<br/>b", "a<BR />b", "a<br\n>b", "<p>x</p>", "<P>x</P>"],
    ids=["br", "br-self-closing", "br-upper-spaced", "br-newline", "p", "p-upper"],
)
def test_to_html_body_real_tag_is_detected_as_html(str_html: str) -> None:
    """A ``<br``/``<p`` tag followed by whitespace, ``/`` or ``>`` is returned unchanged.

    Parameters
    ----------
    str_html : str
            A body containing a real tag.
    """
    assert to_html_body(str_html) == str_html


@pytest.mark.parametrize(
    "str_text",
    [
        "<pre>x</pre>",
        "<param>",
        "<progress>",
        "a <p",
        "risk <p 0.05 & <script>x</script>",
        "a<p/b",
    ],
    ids=["pre", "param", "progress", "trailing-p", "p-space-prose", "p-slash-prose"],
)
def test_to_html_body_p_lookalike_is_escaped_as_plain_text(str_text: str) -> None:
    """Should-fail witness: ``<p`` not shaped like a tag is plain text and gets escaped.

    Parameters
    ----------
    str_text : str
            Plain text that merely contains ``<p``.
    """
    assert to_html_body(str_text) == escape(str_text)
