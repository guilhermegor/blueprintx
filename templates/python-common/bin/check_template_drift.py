"""Report files this project's template tier ships that this project never received.

Scaffolding is a one-shot copy (blueprintx#109): adding a file to ``templates/<tier>/`` (or
the shared ``templates/python-common/``) protects only projects generated AFTER that commit.
No existing project is ever compared against the template it came from, so a fix landing in
the template silently never reaches a project scaffolded before it — forever, unless someone
remembers to backfill it by hand. Two independent real cases motivated this: a network-block
``conftest.py`` guard and a ``.codespellrc`` skip pattern, both missing from a downstream
project scaffolded before either was added to ``templates/python-common/``.

Shape: PRESENCE-ONLY, deliberately, not a content diff. A project's own legitimate local
changes are not drift — only a file/tool the template ships that the project simply does not
have. This is the cheap, high-signal, low-false-positive half of the drift question; the two
real cases above are both absence. A content-diff check on files a project should never
customise (the shared ``bin/check_*.py`` gates, ``.pre-commit-config.yaml`` hook ids) is a
real follow-on but needs a notion of "not meant to be edited locally" this module does not
attempt — a check that fires on legitimate local edits gets disabled the first week it is
noisy, the same "a number nobody pays is a gate nobody keeps" reasoning that set the ``bin/``
complexity ceiling.

Reporter, not a gate — like ``check_contract_drift.py`` in this same directory (read its
header first; the reasoning is identical). Drift in a downstream project is not that
project's fault on the day it is detected: a template gaining a fix after a project was
scaffolded and a source dropping a column are the same shape, something changed on a
DIFFERENT clock than the one CI is checking. So this always exits 0.

What it needs to run: a BLUEPRINTX CHECKOUT (``--blueprintx-root``, or
``BLUEPRINTX_TEMPLATE_ROOT`` in the environment) — nothing here vendors a second copy of the
template tree. Absent one, it self-skips LOUDLY (prints why, never a silent pass) — the same
contract ``check_actions.sh`` documents for its own missing tool. Absent a provenance stamp
(``.blueprintx-provenance.yaml``, written at scaffold time by
``bin/lib/scaffold_python_templates.sh::scaffold_stamp_provenance``) it also self-skips
loudly: that is the path BlueprintX's OWN tree always takes (not a scaffolded project, no
tier — ``--root .`` here never falls through to a comparison), and the path any project
scaffolded before this feature shipped takes too.

The required-path set is DERIVED, not a hand-maintained second list: parsed straight out of
``bin/lib/scaffold_python_templates.sh`` — the one shared step every service tier's scaffold
calls to copy ``templates/python-common/`` in — rather than duplicated here, so this check
cannot drift from what the scaffold actually copies. That is exactly the failure mode
``check_codespell_sync.sh`` already exists in this repo to police, applied to a new pair.
Deliberately scoped to ``templates/python-common/`` only, not the tier-specific
``templates/<tier>/src/`` (each ``bin/scaffold/python_*.sh`` copies that with its own logic,
currently in flight across several PRs) — a narrower, honest MVP over a wider check that
would risk false positives on conditional tier files it cannot see.
"""

import os
import pathlib
import re
import sys


_PROVENANCE_FILENAME = ".blueprintx-provenance.yaml"
_SCAFFOLD_LIB_RELPATH = pathlib.Path("bin/lib/scaffold_python_templates.sh")
_COMMON_TEMPLATE_RELPATH = pathlib.Path("templates/python-common")

# Mirrors the two `cp` shapes scaffold_python_templates.sh actually uses: a single file, and
# the one wholesale `cp -r DIR/. DEST` directory copy (`bin/`). Both destinations are relative
# to `$str_project_path`, i.e. the scaffolded project's own root.
_RE_CP_FILE = re.compile(r'cp\s+"\$COMMON_TEMPLATE_ROOT/([^"]+)"\s+"\$str_project_path/([^"]+)"')
_RE_CP_DIR = re.compile(
	r'cp\s+-r\s+"\$COMMON_TEMPLATE_ROOT/([^"]+)/\."\s+"\$str_project_path/([^"]+)"'
)


def read_tier(path_root: pathlib.Path) -> str | None:
	"""Return the ``tier:`` value stamped in the project's provenance file, or ``None``.

	Parameters
	----------
	path_root : pathlib.Path
		The project root to inspect.

	Returns
	-------
	str or None
		The stamped tier name, or ``None`` when there is no provenance stamp at all.
	"""
	path_stamp = path_root / _PROVENANCE_FILENAME
	if not path_stamp.exists():
		return None
	for str_line in path_stamp.read_text(encoding="utf-8").splitlines():
		str_stripped = str_line.strip()
		if str_stripped.startswith("tier:"):
			return str_stripped.split(":", 1)[1].strip()
	return None


def required_relpaths(path_blueprintx_root: pathlib.Path) -> set[str]:
	"""Derive every python-common-sourced path a scaffold copies UNCONDITIONALLY.

	Parsed straight out of ``bin/lib/scaffold_python_templates.sh`` rather than hand-listed,
	so this set cannot drift from what actually gets copied. Deliberately excludes anything
	conditional (the docker-compose choice, webhook/storage opt-ins) — those live OUTSIDE the
	shared step this parses, in each individual ``bin/scaffold/python_*.sh``.

	Parameters
	----------
	path_blueprintx_root : pathlib.Path
		Root of a BlueprintX checkout.

	Returns
	-------
	set of str
		Project-relative paths (POSIX separators) the shared scaffold step always copies.
		Empty when the shared lib file cannot be found — the caller treats that as SKIPPED,
		never as "nothing is required".
	"""
	path_lib = path_blueprintx_root / _SCAFFOLD_LIB_RELPATH
	if not path_lib.exists():
		return set()
	str_lib = path_lib.read_text(encoding="utf-8")
	path_common = path_blueprintx_root / _COMMON_TEMPLATE_RELPATH

	set_required = {str_dst for _, str_dst in _RE_CP_FILE.findall(str_lib)}
	for str_src_dir, str_dst_dir in _RE_CP_DIR.findall(str_lib):
		path_src_dir = path_common / str_src_dir
		for path_file in sorted(path_src_dir.rglob("*")):
			if path_file.is_file():
				str_rel = path_file.relative_to(path_src_dir).as_posix()
				set_required.add(f"{str_dst_dir}/{str_rel}")
	return set_required


def missing_relpaths(path_root: pathlib.Path, set_required: set[str]) -> list[str]:
	"""Return the required paths that do not exist under the project root, sorted.

	Parameters
	----------
	path_root : pathlib.Path
		The project root to check.
	set_required : set of str
		Project-relative paths the template ships.

	Returns
	-------
	list of str
		Sorted relative paths present in the template but absent from the project.
	"""
	return sorted(str_rel for str_rel in set_required if not (path_root / str_rel).exists())


def _parse_args(list_argv: list) -> tuple[pathlib.Path, pathlib.Path | None]:
	"""Parse ``--root`` and ``--blueprintx-root`` out of argv, with env-var fallbacks.

	Parameters
	----------
	list_argv : list of str
		Raw CLI arguments (``sys.argv[1:]``).

	Returns
	-------
	tuple of (pathlib.Path, pathlib.Path or None)
		The project root (defaults to cwd) and the BlueprintX checkout root (defaults to
		``BLUEPRINTX_TEMPLATE_ROOT`` in the environment, or ``None`` when unset).
	"""
	path_root = pathlib.Path.cwd()
	str_env_bx = os.environ.get("BLUEPRINTX_TEMPLATE_ROOT")
	path_blueprintx = pathlib.Path(str_env_bx).resolve() if str_env_bx else None

	list_rest = list(list_argv)
	while list_rest:
		str_flag = list_rest.pop(0)
		if str_flag == "--root" and list_rest:
			path_root = pathlib.Path(list_rest.pop(0)).resolve()
		elif str_flag == "--blueprintx-root" and list_rest:
			path_blueprintx = pathlib.Path(list_rest.pop(0)).resolve()
	return path_root, path_blueprintx


def _report_missing(str_tier: str, list_missing: list, int_total: int) -> None:
	"""Print the drift report body for a non-empty ``list_missing``.

	Parameters
	----------
	str_tier : str
		The project's stamped tier name.
	list_missing : list of str
		Sorted relative paths the template ships that the project lacks.
	int_total : int
		How many paths were required in total (for the trailing summary line).

	Returns
	-------
	None
	"""
	print(
		f"Template drift detected for tier '{str_tier}' — the template ships these paths and "
		f"this project does not have them:\n"
	)
	for str_rel in list_missing:
		print(f"➖ {str_rel}")
	print(
		f"\n{len(list_missing)} of {int_total} required path(s) missing. This is a REPORT, not "
		f"a gate — a project may have removed one of these on purpose; a human decides whether "
		f"to backfill it."
	)


def main(list_argv: list) -> int:
	"""Report template drift for the project at ``--root``. Always returns 0 (a reporter).

	Parameters
	----------
	list_argv : list of str
		CLI arguments (``sys.argv[1:]``).

	Returns
	-------
	int
		Always 0 — see the module docstring for why this never gates.
	"""
	path_root, path_blueprintx = _parse_args(list_argv)

	str_tier = read_tier(path_root)
	if str_tier is None:
		print(
			f"SKIPPED: no {_PROVENANCE_FILENAME} at {path_root} — nothing to check. Either this "
			f"tree was not scaffolded by BlueprintX (this repo, run over itself, always takes "
			f"this path), or it predates provenance stamping (blueprintx#109). This run proves "
			f"nothing about drift."
		)
		return 0

	if path_blueprintx is None or not path_blueprintx.exists():
		print(
			f"SKIPPED: tier is '{str_tier}' but no BlueprintX checkout is available to compare "
			f"against — pass --blueprintx-root or set BLUEPRINTX_TEMPLATE_ROOT. This run proves "
			f"nothing about drift."
		)
		return 0

	set_required = required_relpaths(path_blueprintx)
	if not set_required:
		print(
			f"SKIPPED: found no required paths under {path_blueprintx} — "
			f"{_SCAFFOLD_LIB_RELPATH} is missing or unparsable there. This run proves nothing "
			f"about drift, and is NOT the same as a clean comparison."
		)
		return 0

	list_missing = missing_relpaths(path_root, set_required)
	if not list_missing:
		print(f"No template drift detected — {len(set_required)} required path(s) present.")
		return 0

	_report_missing(str_tier, list_missing, len(set_required))
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
