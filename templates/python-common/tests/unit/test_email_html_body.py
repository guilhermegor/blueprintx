"""Unit tests for the plain-text-to-HTML e-mail body conversion."""

import time

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
    [
        "a<br>b",
        "a<br/>b",
        "a<BR />b",
        "a<br\n>b",
        "<p>x</p>",
        "<P>x</P>",
        "<p hidden>x</p>",
        '<p hidden class="intro">x</p>',
        "a<br/ >b",
        "a<br / >b",
        "<p class='a' id=b>x</p>",
    ],
    ids=[
        "br",
        "br-self-closing",
        "br-upper-spaced",
        "br-newline",
        "p",
        "p-upper",
        "p-boolean-attribute",
        "p-two-attributes",
        "br-slash-space",
        "br-space-slash-space",
        "p-mixed-quotes",
    ],
)
def test_to_html_body_real_tag_is_detected_as_html(str_html: str) -> None:
    """A well-formed ``<br>``/``<p>`` start tag, with any attributes, is returned unchanged.

    Parameters
    ----------
    str_html : str
            A body containing a real tag.
    """
    assert to_html_body(str_html) == str_html


@pytest.mark.parametrize(
    ("str_text", "str_expected"),
    [
        ("<pre>x</pre>", "&lt;pre&gt;x&lt;/pre&gt;"),
        ("<param>", "&lt;param&gt;"),
        ("<progress>", "&lt;progress&gt;"),
        ("a <p", "a &lt;p"),
        ("a<br", "a&lt;br"),
        (
            "risk <p 0.05 & <script>x</script>",
            "risk &lt;p 0.05 &amp; &lt;script&gt;x&lt;/script&gt;",
        ),
        ("x <br 5 & <script>", "x &lt;br 5 &amp; &lt;script&gt;"),
        ("risk <p n=30 & <script>", "risk &lt;p n=30 &amp; &lt;script&gt;"),
        ("a<p/b", "a&lt;p/b"),
        ("a<br/b", "a&lt;br/b"),
        ("<p \u212a=1>", "&lt;p \u212a=1&gt;"),
    ],
    ids=[
        "pre",
        "param",
        "progress",
        "trailing-p",
        "trailing-br",
        "p-space-prose",
        "br-space-prose",
        "p-name-value-prose",
        "p-slash-prose",
        "br-slash-prose",
        "kelvin-sign",
    ],
)
def test_to_html_body_tag_lookalike_is_escaped_as_plain_text_literal(
    str_text: str, str_expected: str
) -> None:
    """Should-fail witness: ``<br``/``<p`` not shaped like a tag is plain text, escaped.

    Parameters
    ----------
    str_text : str
            Plain text that merely contains ``<br`` or ``<p``.
    str_expected : str
            The exact escaped output.
    """
    assert to_html_body(str_text) == str_expected


@pytest.mark.parametrize(
    "str_body",
    ["<p" + " " * 50000 + "x", "<p" + " a=b" * 20000, "<p a" + " " * 50000 + "/" + " " * 50000],
    ids=["whitespace-run", "attribute-run", "slash-between-runs"],
)
def test_to_html_body_long_whitespace_input_completes_quickly(str_body: str) -> None:
    """Should-fail witness: the tag grammar is linear, not quadratic, on long runs.

    Measured before the linear tail: 8.1 s for 50k spaces; after, milliseconds. The bound is
    generous so a slow CI runner does not flake.

    Parameters
    ----------
    str_body : str
            A pathological body that never closes its tag.
    """
    float_start = time.perf_counter()
    to_html_body(str_body)

    assert time.perf_counter() - float_start < 0.5
