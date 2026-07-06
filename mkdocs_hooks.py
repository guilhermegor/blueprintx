"""MkDocs build hook: inject the code version into the site config.

Derives the project version from the **git tag** (the source of truth under
poetry-dynamic-versioning) via ``git describe`` and exposes it as ``config.extra.code_version``,
so the theme shows a static version label in the header — sourced from the code, never
hand-edited, rendered by plain ``mkdocs serve`` (no ``mike``, no ``gh-pages`` branch). When a tier
hand-bumps its ``[tool.poetry] version`` (no dynamic versioning) or ships a ``0.0.0`` placeholder,
that pyproject version is the fallback for a non-git tree (e.g. an exported zip); a final fallback
of ``"?"`` keeps a build from ever failing on version discovery.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any


try:
	import tomllib  # Python >= 3.11
except ModuleNotFoundError:  # pragma: no cover - 3.10 fallback
	tomllib = None  # type: ignore[assignment]


def _git_version(repo_dir: Path) -> str | None:
	"""Return the version from ``git describe``, or ``None`` off a git tree.

	Mirrors poetry-dynamic-versioning: the version is the latest ``v*`` tag, with a
	``-<n>-g<hash>`` suffix between releases and a bare short hash before the first tag. The
	leading ``v`` is stripped because the theme template prepends its own.

	Parameters
	----------
	repo_dir : Path
		Directory to run ``git`` in (the repository root).

	Returns
	-------
	str | None
		The described version without a leading ``v``, or ``None`` when git is unavailable or
		the directory is not a repository.
	"""
	# The argv is a fixed literal with no untrusted input, and git is intentionally resolved from
	# PATH for portability across machines where its absolute path differs. Bandit checks are
	# suppressed inline on the two lines below.
	cmd = ["git", "describe", "--tags", "--always"]  # noqa: S607
	try:
		result = subprocess.run(  # noqa: S603
			cmd,
			cwd=repo_dir,
			capture_output=True,
			text=True,
			check=True,
			timeout=5,
		)
	except (OSError, subprocess.SubprocessError):
		return None
	described = result.stdout.strip()
	if not described:
		return None
	return described[1:] if described.startswith("v") else described


def _pyproject_version(path_pyproject: Path) -> str | None:
	"""Return ``[tool.poetry] version`` from ``pyproject.toml``, or ``None`` if unavailable.

	Parameters
	----------
	path_pyproject : Path
		Path to the ``pyproject.toml`` file.

	Returns
	-------
	str | None
		The declared version, or ``None`` when the file/key is missing or ``tomllib`` is absent.
	"""
	if tomllib is None or not path_pyproject.exists():
		return None
	dict_pyproject = tomllib.loads(path_pyproject.read_text(encoding="utf-8"))
	version = dict_pyproject.get("tool", {}).get("poetry", {}).get("version")
	return str(version) if version else None


def on_config(config: Any, **kwargs: Any) -> Any:  # noqa: ANN401 - MkDocs passes its config object
	"""Set ``config.extra["code_version"]`` from the git tag (pyproject/``"?"`` fallback).

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
	repo_dir = Path(config["config_file_path"]).parent
	str_version = _git_version(repo_dir) or _pyproject_version(repo_dir / "pyproject.toml") or "?"
	dict_extra = config.setdefault("extra", {}) or {}
	dict_extra["code_version"] = str_version
	config["extra"] = dict_extra
	return config
