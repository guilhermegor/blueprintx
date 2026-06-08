"""Text normalisation for matching strings across heterogeneous sources.

Labels and names arrive from different sources with inconsistent casing, accents,
tabs and stray or doubled whitespace. :func:`normalize_text` collapses all of that
to a single canonical form so matching is robust: lower-cased (casefold), accents
stripped, internal whitespace collapsed to single spaces, and trimmed.

Typical use is normalising an environment name or a free-text key before an
allow-list membership test (e.g. ``normalize_text(ENV) in {"prod", "production"}``).
"""

from __future__ import annotations

import re
import unicodedata


_RE_WHITESPACE = re.compile(r"\s+")


def normalize_text(str_value: str) -> str:
	"""Return a canonical, accent-free, lower-cased form of ``str_value``.

	Parameters
	----------
	str_value : str
		Raw text (may carry accents, tabs, doubled or edge whitespace).

	Returns
	-------
	str
		Lower-cased, accent-stripped text with whitespace collapsed and trimmed.
	"""
	str_decomposed = unicodedata.normalize("NFKD", str(str_value))
	str_ascii = "".join(ch for ch in str_decomposed if not unicodedata.combining(ch))
	return _RE_WHITESPACE.sub(" ", str_ascii).strip().casefold()
