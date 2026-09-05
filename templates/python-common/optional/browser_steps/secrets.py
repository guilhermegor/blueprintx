"""Secret-placeholder resolution for recorded browser steps.

``data/browser-steps/*.json`` is versioned; a credential is never written into it. A
step value may reference ``${ENV_VAR}`` — the same placeholder syntax this repo's own
``pyproject.toml`` templates already use for ``envsubst`` (reused rather than a second,
competing syntax). :func:`resolve_placeholders` substitutes every such reference from
the process environment and fails fast when one is unset: a literal ``${VAR}`` typed
into a login form is a worse failure than a loud error naming the missing variable.
"""

from __future__ import annotations

import os
from string import Template

from .ports import BrowserStepError


def resolve_placeholders(str_value: str) -> str:
	"""Substitute every ``${ENV_VAR}`` reference in ``str_value`` from the environment.

	Parameters
	----------
	str_value : str
		A single step field value, e.g. ``"${VENDOR_PASSWORD}"``.

	Returns
	-------
	str
		``str_value`` with every ``${ENV_VAR}`` reference replaced.

	Raises
	------
	BrowserStepError
		If ``str_value`` references an environment variable that is not set.
	"""
	try:
		return Template(str_value).substitute(os.environ)
	except KeyError as exc:
		raise BrowserStepError(
			f"Browser step references unset environment variable {exc.args[0]!r}; "
			"set it before running this browser-steps flow."
		) from exc
