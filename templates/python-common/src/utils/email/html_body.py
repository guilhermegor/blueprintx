"""Plain-text-to-HTML body conversion, shared by every e-mail backend.

Moved out of ``utils/ms_office/outlook_gateway.py`` (blueprintx#118/#121): turning a plain-text
body into HTML so its line breaks survive is not Outlook-specific — an SMTP backend that ever
sends HTML mail needs the exact same conversion, so it belongs beside :mod:`utils.email.dispatch`
rather than inside the one vendor gateway that happened to write it first.
"""

from __future__ import annotations

from html import escape
import re
from typing import TYPE_CHECKING


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). TYPE_CHECKING stubs the decorator's shape
# locally instead of importing: mypy treats a try/except import as executed code and flags
# the redefinition once actually checked, so this branch can't pick either layout
# (blueprintx#360). Runtime still resolves the real engine via try/except below.
if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    _F = TypeVar("_F", bound=Callable[..., object])

    def type_checker(fn: _F) -> _F:
        """Type-only stub — see src/utils/CLAUDE.md."""
else:
    try:
        from utils.typing import type_checker
    except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
        from chassis.typing import type_checker

re_html_tag = re.compile(
    r"""<(?:br|p|div|table|ul|ol|h[1-6])
    (?:[ \t\r\n\f]+[a-z][a-z0-9:_.-]*
        (?:[ \t\r\n\f]*=[ \t\r\n\f]*(?:"[^"]*"|'[^']*'|[^ \t\r\n\f"'=<>`]+))?
    )*
    (?:[ \t\r\n\f]*/)?[ \t\r\n\f]*>""",
    re.IGNORECASE | re.ASCII | re.VERBOSE,
)


@type_checker
def to_html_body(str_body: str) -> str:
    r"""Convert a plain-text e-mail body to HTML so its line breaks survive.

    An HTML-body client (Outlook's ``mail.HTMLBody``, an SMTP message sent as ``text/html``)
    collapses bare newlines and renders the message on a single line. Each newline is turned
    into a ``<br>`` so paragraph breaks are preserved. A body that already looks like HTML
    is left untouched — the caller composed real markup on purpose, and escaping it would
    show the reader literal angle brackets instead of the formatting it asked for.

    "Looks like HTML" means the body contains a complete start tag of ``br``, ``p`` or one
    of the block-level ``div``, ``table``, ``ul``, ``ol``, ``h1``-``h6``: ``<`` and the tag
    name, zero or more attributes, optional whitespace, an optional ``/``,
    optional whitespace, then ``>``. An attribute is whitespace and a name
    (``[a-z][a-z0-9:_.-]*``), optionally ``=`` with a double-quoted, single-quoted or
    unquoted value (no whitespace and none of ``"'=<>```). Matching is ASCII and
    case-insensitive. So ``<p class="x">``, ``<p hidden class='a'>`` and ``<br/ >`` count,
    while ``<bravo>``, ``<tablex>``, ``<h7>``, ``a<br/b`` and prose like ``<p 0.05`` or
    ``a <div 3`` (no closing ``>``) do not.

    Only START tags of that allowlist count: ``<span>``/``<b>`` markup without one of them is
    still escaped, and a body holding only a closing tag (``text</p>``) is not detected either.

    ⚠️ Detection is all-or-nothing: ONE detected tag makes the WHOLE body pass through raw.
    Never concatenate untrusted text into a body that carries such a tag — the untrusted
    part is returned unescaped, ``<script>`` included.

    A body that does NOT already look like HTML is treated as plain text and **HTML-escaped**
    before the newline conversion. Without this, a literal ``<``/``&``/``>`` in ordinary
    content (a filename, a code snippet, a company name pasted from elsewhere) is interpreted
    as markup by the mail client instead of being shown as the character it is — a value like
    ``report <final>.xlsx`` would silently drop the bracketed text, and a value containing a
    full tag would render as if the caller had written HTML on purpose.

    Parameters
    ----------
    str_body : str
            The plain-text body (possibly with ``\n`` / ``\r\n`` line breaks).

    Returns
    -------
    str
            The body with newlines rendered as ``<br>`` (unchanged when already HTML; otherwise
            HTML-escaped first).
    """
    if re_html_tag.search(str_body):
        return str_body
    return escape(str_body).replace("\r\n", "\n").replace("\n", "<br>\n")
