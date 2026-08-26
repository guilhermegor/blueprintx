"""Plain-text-to-HTML body conversion, shared by every e-mail backend.

Moved out of ``utils/ms_office/outlook_gateway.py`` (blueprintx#118/#121): turning a plain-text
body into HTML so its line breaks survive is not Outlook-specific — an SMTP backend that ever
sends HTML mail needs the exact same conversion, so it belongs beside :mod:`utils.email.dispatch`
rather than inside the one vendor gateway that happened to write it first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). mypy reads the single TYPE_CHECKING
# import (no redefinition); at runtime the try/except picks whichever layout shipped.
if TYPE_CHECKING:
	from utils.typing import type_checker
else:
	try:
		from utils.typing import type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from chassis.typing import type_checker


@type_checker
def to_html_body(str_body: str) -> str:
	r"""Convert a plain-text e-mail body to HTML so its line breaks survive.

	An HTML-body client (Outlook's ``mail.HTMLBody``, an SMTP message sent as ``text/html``)
	collapses bare newlines and renders the message on a single line. Each newline is turned
	into a ``<br>`` so paragraph breaks are preserved. A body that already looks like HTML
	(contains a ``<br`` or ``<p>`` tag) is left untouched.

	Parameters
	----------
	str_body : str
		The plain-text body (possibly with ``\n`` / ``\r\n`` line breaks).

	Returns
	-------
	str
		The body with newlines rendered as ``<br>`` (unchanged when already HTML).
	"""
	str_low = str_body.casefold()
	if "<br" in str_low or "<p>" in str_low:
		return str_body
	return str_body.replace("\r\n", "\n").replace("\n", "<br>\n")
