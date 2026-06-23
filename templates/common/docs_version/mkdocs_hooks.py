"""MkDocs build hook: inject the code version into the site config.

Reads the project version from ``pyproject.toml`` (``[tool.poetry] version``) and exposes it
as ``config.extra.code_version`` so the theme can show a static ``v<version>`` label in the
header — sourced from the code, never hand-edited, rendered by plain ``mkdocs serve`` (no
``mike``, no ``gh-pages`` branch). A missing file/key (or a Python without ``tomllib``)
degrades to ``"?"`` and never fails the build.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


try:
	import tomllib  # Python >= 3.11
except ModuleNotFoundError:  # pragma: no cover - 3.10 fallback
	tomllib = None  # type: ignore[assignment]


def on_config(config: Any, **kwargs: Any) -> Any:  # noqa: ANN401 - MkDocs passes its config object
	"""Set ``config.extra["code_version"]`` from ``pyproject.toml``.

	Parameters
	----------
	config : Any
		The MkDocs config object (mutated in place and returned).
	**kwargs : Any
		Extra keyword arguments MkDocs may pass (ignored).

	Returns
	-------
	Any
		The same config object, with ``extra["code_version"]`` set.
	"""
	path_pyproject = Path(config["config_file_path"]).parent / "pyproject.toml"
	str_version = "?"
	if tomllib is not None and path_pyproject.exists():
		dict_pyproject = tomllib.loads(path_pyproject.read_text(encoding="utf-8"))
		str_version = str(dict_pyproject.get("tool", {}).get("poetry", {}).get("version", "?"))
	dict_extra = config.setdefault("extra", {}) or {}
	dict_extra["code_version"] = str_version
	config["extra"] = dict_extra
	return config
