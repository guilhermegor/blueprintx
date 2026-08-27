"""Verify the target venv can actually import what pip claims it installed.

Used by ``bin/lib/pip_fallback.sh`` right after a pip-fallback install. "``.venv``
exists" and "``pip install`` returned 0" both stop short of the question that actually
matters: can this interpreter import what was just declared? Neither probe catches a
blocked corporate index that leaves an empty ``.venv`` behind while still reporting
success, nor a batch install pip calls "already satisfied" without ever touching the
index (blueprintx#127 — "two probes that lie"). Left unguarded, the failure surfaces
layers away, as a bare ``ModuleNotFoundError`` the first time the project actually runs.

Must run under the TARGET venv's own interpreter, not the bootstrap one — only that
interpreter's ``importlib.metadata`` sees the venv's site-packages.

Interface: a requirements file path as ``argv[1]``, one requirement per line (as written
by ``pip_requirements.py``). Exits non-zero, naming every requirement whose distribution
is missing or whose recorded top-level module fails to import; exits 0 (nothing to
verify) when the file has no requirement lines — an intentionally dependency-free group
is not a failure.
"""

from __future__ import annotations

import importlib.metadata
import re
import sys


_RE_LEADING_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


def requirement_name(str_line: str) -> str | None:
	"""Extract the bare distribution name from one requirement line.

	Parameters
	----------
	str_line : str
		A requirement line, e.g. ``"httpx[http2]>=0.27 ; python_version >= '3.10'"``.

	Returns
	-------
	str or None
		The distribution name, or ``None`` for a blank/comment line.
	"""
	str_line = str_line.split(";", 1)[0].split("#", 1)[0].strip()
	if not str_line:
		return None
	cls_match = _RE_LEADING_NAME.match(str_line)
	return cls_match.group(0) if cls_match else None


def top_level_imports(str_name: str) -> list[str]:
	"""Resolve the import name(s) a distribution actually installs.

	Reads the distribution's own ``top_level.txt`` rather than guessing from the
	PyPI name — ``PyYAML`` imports as ``yaml``, ``python-dotenv`` as ``dotenv``, and no
	naming convention predicts either.

	Parameters
	----------
	str_name : str
		The distribution name as pip knows it.

	Returns
	-------
	list of str
		One or more top-level module names to import.
	"""
	cls_dist = importlib.metadata.distribution(str_name)
	str_text = cls_dist.read_text("top_level.txt")
	if str_text:
		return [str_line.strip() for str_line in str_text.splitlines() if str_line.strip()]
	# No top_level.txt (some wheel-built dists omit it) — the normalised name is the
	# best available guess and is right for the common single-module case.
	return [str_name.replace("-", "_")]


def check_requirement(str_req: str) -> str | None:
	"""Verify one requirement line is actually importable in THIS interpreter.

	Parameters
	----------
	str_req : str
		A requirement line.

	Returns
	-------
	str or None
		A one-line failure message, or ``None`` when the requirement imports fine.
	"""
	str_name = requirement_name(str_req)
	if str_name is None:
		return None

	try:
		list_modules = top_level_imports(str_name)
	except importlib.metadata.PackageNotFoundError:
		return f"{str_name}: not installed in the target venv"

	for str_module in list_modules:
		try:
			__import__(str_module)
		except Exception as exc:  # noqa: BLE001 - report every distinct import failure by name
			return f"{str_name}: import {str_module!r} failed ({exc})"
	return None


def main() -> int:
	"""Verify every requirement in the file argv[1] actually imports.

	Returns
	-------
	int
		0 when every requirement imports (or the file has none); 1 otherwise.
	"""
	if len(sys.argv) != 2:
		print("usage: verify_venv_imports.py <requirements-file>", file=sys.stderr)
		return 2

	with open(sys.argv[1], encoding="utf-8") as file_req:
		list_lines = [str_line for str_line in file_req if requirement_name(str_line)]

	list_problems = [
		str_problem for str_line in list_lines if (str_problem := check_requirement(str_line))
	]

	if list_problems:
		print(
			"The target venv reports installed packages it cannot actually import "
			"(blueprintx#127 — a blocked index can report success with nothing usable):",
			file=sys.stderr,
		)
		for str_problem in list_problems:
			print(f"  - {str_problem}", file=sys.stderr)
		return 1

	return 0


if __name__ == "__main__":
	sys.exit(main())
