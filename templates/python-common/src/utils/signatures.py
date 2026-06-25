"""Resolve a sender's HTML e-mail signature.

The signature for a sending account lives at
``src/config/signatures/<sender>.html``; when that file is absent the shared
``default.html`` is used. Any e-mail notifier resolves it the same way, so the
logic lives here once.
"""

from __future__ import annotations

from pathlib import Path
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
def resolve_signature(path_signatures_dir: Path, str_sender_email: str) -> str:
	"""Return the sender's signature HTML, falling back to the default.

	Parameters
	----------
	path_signatures_dir : pathlib.Path
		Directory holding ``<sender>.html`` / ``default.html``.
	str_sender_email : str
		Sender account; selects ``<sender>.html``.

	Returns
	-------
	str
		Signature HTML (``<sender>.html``, else ``default.html``, else empty).
	"""
	for str_name in (f"{str_sender_email}.html", "default.html"):
		path_sig = path_signatures_dir / str_name
		if path_sig.exists():
			return path_sig.read_text(encoding="utf-8")
	return ""


@type_checker
def to_html(str_body: str) -> str:
	"""Convert a plain-text body to minimal HTML (newlines to ``<br>``).

	Parameters
	----------
	str_body : str
		Plain-text body.

	Returns
	-------
	str
		HTML body.
	"""
	return str_body.replace("\n", "<br>\n")
