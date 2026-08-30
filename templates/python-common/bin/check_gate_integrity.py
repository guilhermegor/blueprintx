"""Detect a PR that weakens a quality gate without an explicit justification.

THE DEFECT (blueprintx#309). Nothing today distinguishes "fixed the code" from "deleted the
check that failed" — both produce a green PR, and this is the one failure that survives every
other control, because it disarms them. With ``required_approving_review_count`` pinned at 0
(a solo maintainer cannot self-approve, so any human gate is unsatisfiable — see
``enable_repo_rules.sh``), this has to be a deterministic gate, not a reviewer's judgement call.

WHY DIFF-SCOPED, NOT WHOLE-TREE — the one deliberate departure from this file's siblings.
``check_function_length.py`` / ``check_complexity.sh`` audit a PROPERTY of the current tree, so
whole-tree is the right shape for them. This gate audits a DELTA — a hook that was never added
is not a violation, but one that WAS there and got REMOVED is — so it has to compare against
something. It diffs the index (staged content locally; equal to HEAD on a clean CI checkout)
against ``merge-base(HEAD, <default-branch>)``, the same shape as ``check_backlog_ledger.py``.

WHAT COUNTS AS WEAKENING (every one of these is a delta, read straight off the five config
files a change touches — never off arbitrary source):

- a pre-commit hook (``- id: <x>``) removed from a changed ``.pre-commit-config.yaml``
- a rule removed from a changed ``ruff.toml``'s ``[lint] select``
- a rule ADDED to ``ignore`` or ``per-file-ignores`` — RULE level, in either config file
- a path ADDED to ``ruff.toml``'s ``exclude`` or ``mypy.ini``'s ``[mypy] exclude``
- a ``[mypy-<module>] ignore_errors = True`` section ADDED, or an EXISTING section flipped
  from ``False``/absent to ``True`` — compared by effective value, not by section presence
- an ``error:``-escalated ``filterwarnings`` entry removed from ``pytest.ini``
- a ``bin/ci/*`` file, or a ``bin/check_*``/``bin/lint_*`` gate script, DELETED
- any watched config (``.pre-commit-config.yaml``, ``ruff.toml``, ``mypy.ini``, ``pytest.ini``)
  or workflow file DELETED outright — the most complete form of every weakening above
- a job key removed from a changed workflow's ``jobs:`` block
- a required status-check context removed from ``enable_repo_rules.sh``'s
  ``REQUIRED_CHECKS`` array (the single reviewable source that WRITES the ruleset — this gate
  reads its diff rather than calling the GitHub API, the same "one implementation" reasoning
  the script itself is built on)

THE ESCAPE HATCH mirrors the precedent already in this file family (``# complexity-ok:
<reason>``): a ``gate-change-ok: <reason>`` line, with a non-empty reason, in the PR body (read
from ``GITHUB_EVENT_PATH``) or as a trailer on any commit since the merge-base — the latter
covers a local run before a PR exists, and a squash-merge that drops the PR body. A bare marker
with no reason does not count, matching ``check_complexity.sh``'s "the reason is required" rule.

⚠️ LINE-LEVEL SUPPRESSIONS (``# noqa: X``, ``# complexity-ok: <reason>``, ``# type: ignore``,
``# pragma: no cover``, ``# shellcheck disable`` — ~250 in this tree) MUST NEVER TRIP THIS GATE,
and structurally cannot: it only ever reads the config files named above, never a ``.py``/``.sh``
source file. PR #306 suppressed S608 per LINE for exactly this reason — a rule-level ignore
would have silenced every future S608 finding, not just the one reviewed. A gate that blocked
line-level suppressions would be worse than no gate: it teaches people to route around it, and
then they route around it for the real findings too.

CI must check out with ``fetch-depth: 0`` — a shallow clone has no common ancestor to resolve.
"""

import configparser
import json
import os
import pathlib
import re
import subprocess
import sys


PATH_ROOT = pathlib.Path(__file__).resolve().parent.parent

# The reason is REQUIRED — a bare marker does not satisfy the gate, matching
# `# complexity-ok: <reason>` elsewhere in this file family.
RE_JUSTIFICATION = re.compile(r"^\s*gate-change-ok:\s*(\S.*)$", re.I | re.M)
RE_HOOK_ID = re.compile(r"^\s*-\s*id:\s*(\S+)\s*$", re.M)
RE_REQUIRED_CHECKS = re.compile(r"REQUIRED_CHECKS=\((.*?)\)", re.S)
RE_CI_SCRIPT = re.compile(r"(^|/)bin/ci/[^/]+$")
RE_GATE_SCRIPT = re.compile(r"(^|/)bin/(check|lint)_[^/]+\.(py|sh)$")
RE_WORKFLOW_PATH = re.compile(r"\.github/workflows/.*\.ya?ml$")

# `git show :<path>` (empty ref) reads the INDEX blob — equal to HEAD on a clean CI checkout,
# and the staged content in a local pre-commit run. Using it for BOTH sides is what lets one
# code path serve pre-commit and CI without branching on which one is running.
STR_INDEX_REF = ""


def _git(list_args: list) -> str:
	"""Run a read-only git command and return stdout (empty string on failure).

	Parameters
	----------
	list_args : list of str
		Arguments after ``git``.

	Returns
	-------
	str
		Captured stdout, stripped.
	"""
	try:
		# Constant, trusted argv built in-process; no shell involved. S607 (partial path) is
		# resolution BY DESIGN — see check_backlog_ledger.py's identical helper.
		cls_proc = subprocess.run(  # noqa: S603
			["git", *list_args],  # noqa: S607
			capture_output=True,
			text=True,
			check=False,
		)
	except OSError:
		return ""
	return cls_proc.stdout


def default_branch() -> str:
	"""Return a resolvable ref for the repository's default branch.

	Returns
	-------
	str
		``origin/<name>`` when only the remote-tracking branch exists — the common CI shape,
		a checkout with no local ``main`` — else a local ``<name>``. Previously this stripped
		the remote prefix (``origin/main`` -> ``main``), which is unresolvable by itself when
		no local branch backs it; ``git merge-base`` then failed silently and ``resolve_base``
		read that as "nothing to diff" instead of "could not check" (blueprintx#313). Falls
		back to the literal ``"main"`` only when nothing resolves at all, so ``resolve_base``
		can tell a real skip apart from an unresolvable baseline.
	"""
	str_ref = _git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"]).strip()
	if str_ref:
		return str_ref
	for str_candidate in ("main", "master"):
		for str_full in (f"origin/{str_candidate}", str_candidate):
			if _git(["rev-parse", "--verify", "--quiet", str_full]).strip():
				return str_full
	return "main"


def show(str_ref: str, str_path: str) -> str | None:
	"""Return a blob's text content at a git ref/path, or ``None`` when it does not exist there.

	Parameters
	----------
	str_ref : str
		A commit-ish, or ``""`` for the index (``STR_INDEX_REF``).
	str_path : str
		Repository-relative path.

	Returns
	-------
	str or None
		The blob's content, ``None`` when the path does not exist at that ref, and ``None``
		when the blob is not valid UTF-8 — a binary cannot define a gate, so there is nothing
		here to assert about it.
	"""
	# ⚠️ BYTES, NOT text=True. `text=True` decodes whatever git emits, so ONE binary path in the
	# diff raised UnicodeDecodeError and took the whole gate down — not a finding, a crash, and
	# a crash reports as the check's NAME ("a PR must not weaken a check without saying why"),
	# accusing a PR that had merely added a logo. Measured on #337: `docs/assets/logo.png`,
	# 0xff at position 0, a JPEG SOI marker.
	#
	# Worse than a wrong message: the traceback stopped collection at the FIRST binary path, so
	# every later file went unexamined. The gate blocked the PR while having checked almost
	# nothing — its own blindness reported as a rejection.
	#
	# ⚠️ Skipping by EXTENSION is not the fix, and this repo holds the counter-example: that
	# `.png` contains JPEG bytes. A decode attempt asks the blob itself.
	cls_proc = subprocess.run(  # noqa: S603
		["git", "show", f"{str_ref}:{str_path}"],  # noqa: S607
		capture_output=True,
		check=False,
	)
	if cls_proc.returncode != 0:
		return None
	try:
		return cls_proc.stdout.decode("utf-8")
	except UnicodeDecodeError:
		return None


def changed_paths(str_base: str) -> list:
	"""Return the branch's cumulative changed paths with their status, INDEX included.

	Parameters
	----------
	str_base : str
		The merge-base commit to diff against.

	Returns
	-------
	list of tuple
		``(status_letter, path)``, e.g. ``("D", "bin/ci/check_actions.sh")``.
	"""
	# A `git diff --name-status` row is always "<status>\t<path>" (or, for a rename,
	# "<status>\t<old>\t<new>") — never fewer than 2 tab-separated fields.
	_INT_MIN_FIELDS = 2

	str_out = _git(["diff", "--cached", "--name-status", str_base])
	list_rows = []
	for str_line in str_out.splitlines():
		list_parts = str_line.split("\t")
		if len(list_parts) >= _INT_MIN_FIELDS:
			list_rows.append((list_parts[0][0], list_parts[-1]))
	return list_rows


def strip_toml_comments(str_text: str) -> str:
	"""Remove ``# ...`` end-of-line comments, leaving quoted string content untouched.

	⚠️ Measured necessary, not defensive: ``ruff.toml``'s own ``[lint.per-file-ignores]``
	section carries a prose comment that itself quotes a phrase (documenting an ``ERA001``
	false positive), and a naive quoted-string scan over the raw text read that phrase as a
	rule code. A ``#`` is only treated as a comment start when reached with an EVEN number of
	``"`` already seen on the line — i.e. outside any quoted span — which is enough for this
	repo's TOML, where a value never itself contains a bare ``#``.

	Parameters
	----------
	str_text : str
		Raw file content.

	Returns
	-------
	str
		The same text with every comment's tail removed.
	"""
	list_out = []
	for str_line in str_text.splitlines():
		int_quotes = 0
		int_cut = len(str_line)
		for int_i, str_ch in enumerate(str_line):
			if str_ch == '"':
				int_quotes += 1
			elif str_ch == "#" and int_quotes % 2 == 0:
				int_cut = int_i
				break
		list_out.append(str_line[:int_cut])
	return "\n".join(list_out)


def toml_top_array(str_text: str, str_key: str) -> set:
	"""Return the quoted string entries of a top-level ``key = [ ... ]`` TOML array.

	Parameters
	----------
	str_text : str
		Full file content.
	str_key : str
		The array's key, e.g. ``"select"``.

	Returns
	-------
	set of str
		Every quoted entry inside the array.
	"""
	str_text = strip_toml_comments(str_text)
	cls_match = re.search(rf"(?m)^{re.escape(str_key)}\s*=\s*\[", str_text)
	if not cls_match:
		return set()
	int_close = str_text.find("]", cls_match.end())
	if int_close == -1:
		return set()
	return set(re.findall(r'"([^"]*)"', str_text[cls_match.end() : int_close]))


def toml_per_file_ignores(str_text: str) -> dict:
	"""Return ``{glob: {rule, ...}}`` from a ``[lint.per-file-ignores]`` section.

	Parameters
	----------
	str_text : str
		Full ``ruff.toml`` content.

	Returns
	-------
	dict
		Glob key to its set of rule codes; empty when the section is absent.
	"""
	str_text = strip_toml_comments(str_text)
	cls_section = re.search(r"(?m)^\[lint\.per-file-ignores\]\s*$(.*?)(?=^\[|\Z)", str_text, re.S)
	if not cls_section:
		return {}
	dict_out = {}
	for cls_entry in re.finditer(r'"([^"]+)"\s*=\s*\[(.*?)\]', cls_section.group(1), re.S):
		dict_out[cls_entry.group(1)] = set(re.findall(r'"([^"]*)"', cls_entry.group(2)))
	return dict_out


def ruff_toml_problems(str_old: str, str_new: str, str_shown: str) -> list:
	"""Return weakening findings between two versions of a ``ruff.toml``.

	Parameters
	----------
	str_old : str
		Content at the merge-base.
	str_new : str
		Content in this change.
	str_shown : str
		Path to show in messages.

	Returns
	-------
	list of str
		One message per weakening found.
	"""
	list_problems = []
	for str_rule in sorted(toml_top_array(str_old, "select") - toml_top_array(str_new, "select")):
		list_problems.append(f"{str_shown}: rule {str_rule!r} removed from [lint] select")
	set_old_ignore, set_new_ignore = (
		toml_top_array(str_old, "ignore"),
		toml_top_array(str_new, "ignore"),
	)
	for str_rule in sorted(set_new_ignore - set_old_ignore):
		list_problems.append(f"{str_shown}: rule {str_rule!r} added to [lint] ignore")
	set_old_exclude = toml_top_array(str_old, "exclude")
	set_new_exclude = toml_top_array(str_new, "exclude")
	for str_path in sorted(set_new_exclude - set_old_exclude):
		list_problems.append(f"{str_shown}: path {str_path!r} added to exclude")

	dict_old_pfi = toml_per_file_ignores(str_old)
	dict_new_pfi = toml_per_file_ignores(str_new)
	for str_glob, set_new_codes in dict_new_pfi.items():
		for str_rule in sorted(set_new_codes - dict_old_pfi.get(str_glob, set())):
			list_problems.append(
				f"{str_shown}: rule {str_rule!r} added to per-file-ignores[{str_glob!r}]"
			)
	return list_problems


def parsed_ini(str_text: str) -> configparser.ConfigParser | None:
	"""Parse INI-style text, returning ``None`` when it does not parse.

	Parameters
	----------
	str_text : str
		Raw file content (``mypy.ini`` or ``pytest.ini`` shape).

	Returns
	-------
	configparser.ConfigParser or None
		The parsed config, or ``None`` on a syntax error — this gate is not the place to
		validate a config file's syntax, only to compare two versions of a valid one.
	"""
	cls_parser = configparser.ConfigParser()
	try:
		cls_parser.read_string(str_text)
	except configparser.Error:
		return None
	return cls_parser


def mypy_ini_problems(str_old: str, str_new: str, str_shown: str) -> list:
	"""Return weakening findings between two versions of a ``mypy.ini``.

	Parameters
	----------
	str_old : str
		Content at the merge-base.
	str_new : str
		Content in this change.
	str_shown : str
		Path to show in messages.

	Returns
	-------
	list of str
		One message per weakening found.
	"""
	cls_old = parsed_ini(str_old)
	cls_new = parsed_ini(str_new)
	if cls_old is None or cls_new is None:
		return []

	list_problems = []
	set_old_alts = {
		s.strip() for s in cls_old.get("mypy", "exclude", fallback="").split("|") if s.strip()
	}
	set_new_alts = {
		s.strip() for s in cls_new.get("mypy", "exclude", fallback="").split("|") if s.strip()
	}
	for str_alt in sorted(set_new_alts - set_old_alts):
		list_problems.append(f"{str_shown}: path {str_alt!r} added to [mypy] exclude")

	# Effective value, not section presence — a pre-existing `[mypy-<module>]` section that
	# flips `ignore_errors` from False/absent to True is exactly as much a weakening as a
	# brand new section carrying `ignore_errors = True` (blueprintx#313).
	for str_section in sorted(cls_new.sections()):
		bool_old = cls_old.getboolean(str_section, "ignore_errors", fallback=False)
		bool_new = cls_new.getboolean(str_section, "ignore_errors", fallback=False)
		if bool_new and not bool_old:
			list_problems.append(f"{str_shown}: [{str_section}] ignore_errors = True added")
	return list_problems


def pytest_ini_problems(str_old: str, str_new: str, str_shown: str) -> list:
	"""Return weakening findings between two versions of a ``pytest.ini``.

	Parameters
	----------
	str_old : str
		Content at the merge-base.
	str_new : str
		Content in this change.
	str_shown : str
		Path to show in messages.

	Returns
	-------
	list of str
		One message per ``error:``-escalated ``filterwarnings`` entry that was removed.
	"""
	cls_old = parsed_ini(str_old)
	cls_new = parsed_ini(str_new)
	if cls_old is None or cls_new is None:
		return []

	def escalations(cls_parser: configparser.ConfigParser) -> set:
		str_raw = cls_parser.get("pytest", "filterwarnings", fallback="")
		return {
			str_line.strip()
			for str_line in str_raw.splitlines()
			if str_line.strip().startswith("error:")
		}

	return [
		f"{str_shown}: filterwarnings escalation {str_entry!r} removed"
		for str_entry in sorted(escalations(cls_old) - escalations(cls_new))
	]


def precommit_problems(str_old: str, str_new: str, str_shown: str) -> list:
	"""Return hooks present at the merge-base and missing now.

	Parameters
	----------
	str_old : str
		Content at the merge-base.
	str_new : str
		Content in this change.
	str_shown : str
		Path to show in messages.

	Returns
	-------
	list of str
		One message per removed hook id.
	"""
	set_removed = set(RE_HOOK_ID.findall(str_old)) - set(RE_HOOK_ID.findall(str_new))
	return [f"{str_shown}: pre-commit hook {str_id!r} removed" for str_id in sorted(set_removed)]


def workflow_jobs(str_text: str) -> set:
	"""Return the top-level job ids under a workflow's ``jobs:`` block.

	Parameters
	----------
	str_text : str
		Full workflow YAML content.

	Returns
	-------
	set of str
		Job ids, read as 2-space-indented ``name:`` keys directly under ``jobs:`` — the
		indentation this repo's workflows consistently use (avoids a YAML dependency these
		scripts otherwise have no reason to carry; see the module docstring).
	"""
	cls_match = re.search(r"(?m)^jobs:\s*$", str_text)
	if not cls_match:
		return set()
	set_jobs = set()
	for str_line in str_text[cls_match.end() :].splitlines():
		if not str_line.strip():
			continue
		if not str_line.startswith(" "):
			break
		cls_job = re.match(r"^ {2}([A-Za-z0-9_-]+):", str_line)
		if cls_job:
			set_jobs.add(cls_job.group(1))
	return set_jobs


def workflow_problems(str_old: str, str_new: str, str_shown: str) -> list:
	"""Return job ids present at the merge-base and missing now.

	Parameters
	----------
	str_old : str
		Content at the merge-base.
	str_new : str
		Content in this change.
	str_shown : str
		Path to show in messages.

	Returns
	-------
	list of str
		One message per removed job.
	"""
	set_removed = workflow_jobs(str_old) - workflow_jobs(str_new)
	return [f"{str_shown}: workflow job {str_id!r} removed" for str_id in sorted(set_removed)]


def required_checks_problems(str_old: str, str_new: str, str_shown: str) -> list:
	"""Return required status-check contexts removed from ``enable_repo_rules.sh``.

	Parameters
	----------
	str_old : str
		Content at the merge-base.
	str_new : str
		Content in this change.
	str_shown : str
		Path to show in messages.

	Returns
	-------
	list of str
		One message per removed context.
	"""

	def contexts(str_text: str) -> set:
		cls_match = RE_REQUIRED_CHECKS.search(str_text)
		return set(re.findall(r'"([^"]*)"', cls_match.group(1))) if cls_match else set()

	set_removed = contexts(str_old) - contexts(str_new)
	return [
		f"{str_shown}: required status check {str_check!r} removed"
		for str_check in sorted(set_removed)
	]


# Dispatch by basename/path shape — the whole reason each analyzer above takes plain
# (old_text, new_text, shown_path) rather than reaching for git itself.
_DICT_DISPATCH = {
	".pre-commit-config.yaml": precommit_problems,
	"ruff.toml": ruff_toml_problems,
	"mypy.ini": mypy_ini_problems,
	"pytest.ini": pytest_ini_problems,
	"enable_repo_rules.sh": required_checks_problems,
}


def file_problems(str_path: str, str_base: str) -> list:
	"""Return weakening findings for one changed, still-existing path.

	Parameters
	----------
	str_path : str
		Repository-relative path, as reported by ``changed_paths``.
	str_base : str
		The merge-base commit.

	Returns
	-------
	list of str
		Findings for this path; empty when it is not a watched config file, is newly
		added (nothing to weaken), or carries no weakening.
	"""
	str_new = show(STR_INDEX_REF, str_path)
	str_old = show(str_base, str_path)
	if str_new is None or str_old is None:
		return []

	fn_analyzer = _DICT_DISPATCH.get(pathlib.Path(str_path).name)
	if fn_analyzer is None and RE_WORKFLOW_PATH.search(str_path):
		fn_analyzer = workflow_problems
	if fn_analyzer is None:
		return []
	return fn_analyzer(str_old, str_new, str_path)


def deletion_problems(list_changed: list) -> list:
	"""Return findings for a deleted gate script, or a deleted watched config/workflow file.

	Deleting the whole file is the bluntest form of every weakening ``file_problems`` reads
	line-by-line inside it — a ``ruff.toml`` deleted outright removes every rule at once, and
	that must be at least as loud as removing one rule from it (blueprintx#313).

	Parameters
	----------
	list_changed : list of tuple
		``(status_letter, path)`` rows from ``changed_paths``.

	Returns
	-------
	list of str
		One message per deleted quality-check script or deleted watched config file.
	"""
	list_problems = []
	for str_status, str_path in list_changed:
		if str_status != "D":
			continue
		if RE_CI_SCRIPT.search(str_path) or RE_GATE_SCRIPT.search(str_path):
			list_problems.append(f"{str_path}: quality-check script deleted")
		elif pathlib.Path(str_path).name in _DICT_DISPATCH or RE_WORKFLOW_PATH.search(str_path):
			list_problems.append(f"{str_path}: watched gate configuration deleted")
	return list_problems


def pr_body_text() -> str:
	"""Return the current PR's body from the GitHub Actions event payload (I/O seam).

	Returns
	-------
	str
		The PR body, or ``""`` outside a ``pull_request`` workflow run.
	"""
	str_event_path = os.environ.get("GITHUB_EVENT_PATH", "")
	if not str_event_path:
		return ""
	try:
		dict_event = json.loads(pathlib.Path(str_event_path).read_text(encoding="utf-8"))
	except (OSError, ValueError):
		return ""
	dict_pr = dict_event.get("pull_request") or {}
	return str(dict_pr.get("body") or "")


def justification_reason(str_base: str) -> str:
	"""Return the ``gate-change-ok`` reason from the PR body or a commit trailer, or ``""``.

	Parameters
	----------
	str_base : str
		The merge-base commit — commit messages since it are searched for a trailer.

	Returns
	-------
	str
		The non-empty reason text, or ``""`` when no valid justification is present.
	"""
	str_trailers = _git(["log", f"{str_base}..HEAD", "--format=%B"])
	for str_text in (pr_body_text(), str_trailers):
		cls_match = RE_JUSTIFICATION.search(str_text)
		if cls_match and cls_match.group(1).strip():
			return cls_match.group(1).strip()
	return ""


def apply_root_flag(list_argv: list) -> bool:
	"""Parse a leading ``--root <dir>`` flag, updating ``PATH_ROOT`` in place.

	Parameters
	----------
	list_argv : list of str
		The raw argv tail.

	Returns
	-------
	bool
		``False`` on bad usage (already reported to stdout); ``True`` otherwise, including
		when no ``--root`` flag was given at all.
	"""
	global PATH_ROOT  # noqa: PLW0603
	if list_argv[:1] != ["--root"]:
		return True
	if len(list_argv) < 2:  # noqa: PLR2004
		print("❌ --root needs a directory")
		return False
	PATH_ROOT = pathlib.Path(list_argv[1]).resolve()
	return True


def resolve_base() -> str | None:
	"""Resolve the merge-base to diff against.

	Returns
	-------
	str or None
		The merge-base commit to diff against. ``None`` means a real skip: a ref resolved
		and HEAD already IS that commit, so there is genuinely nothing to diff. An empty
		string means the OPPOSITE — no ref could be resolved at all — and is deliberately
		never treated as a skip: an absent baseline is not proof of no weakening
		(blueprintx#313); ``main()`` fails the run on it instead of passing it silently.
	"""
	str_ref = default_branch()
	str_base = _git(["merge-base", "HEAD", str_ref]).strip()
	if not str_base:
		print(f"❌ could not resolve a merge-base against {str_ref!r} — refusing to pass blind.")
		return ""
	str_head = _git(["rev-parse", "HEAD"]).strip()
	if str_base == str_head:
		print("✅ gate-integrity check skipped — on the default branch (nothing to diff).")
		return None
	return str_base


def collect_problems(list_changed: list, str_base: str) -> list:
	"""Return every weakening finding across the branch's changed paths.

	Parameters
	----------
	list_changed : list of tuple
		``(status_letter, path)`` rows from ``changed_paths``.
	str_base : str
		The merge-base commit.

	Returns
	-------
	list of str
		Combined findings from deletions and from modified watched config files.
	"""
	list_problems = deletion_problems(list_changed)
	for str_status, str_path in list_changed:
		if str_status != "D":
			list_problems.extend(file_problems(str_path, str_base))
	return list_problems


def report(list_problems: list, str_base: str, int_changed_count: int) -> int:
	"""Print findings and the verdict, resolving the justification escape hatch.

	Parameters
	----------
	list_problems : list of str
		Findings from ``collect_problems``.
	str_base : str
		The merge-base commit — passed through to ``justification_reason``.
	int_changed_count : int
		Total changed-path count, shown on a clean pass.

	Returns
	-------
	int
		0 when clean or justified, 1 on an unjustified weakening.
	"""
	if not list_problems:
		print(f"✅ gate integrity OK ({int_changed_count} changed file(s) checked)")
		return 0

	for str_problem in list_problems:
		print(f"⚠️  {str_problem}")

	str_reason = justification_reason(str_base)
	if str_reason:
		print(f"\n✅ justified: gate-change-ok: {str_reason}")
		return 0

	print(
		f"\n❌ {len(list_problems)} gate-weakening change(s) with no justification. Add a "
		f"'gate-change-ok: <reason>' line to the PR body or as a commit trailer — the reason "
		f"is required, matching '# complexity-ok: <reason>' elsewhere in this repo."
	)
	return 1


def main(list_argv: list) -> int:
	"""Check the branch's cumulative diff for an unjustified gate weakening.

	Parameters
	----------
	list_argv : list of str
		``["--root", <dir>]`` or empty. ``--root`` is accepted for interface parity with
		``check_function_length.py`` / ``check_complexity.sh`` (this repo runs every shared
		gate over BlueprintX via ``--root .``); the diff itself is always repo-wide, since
		``git diff`` paths are already repository-relative regardless of cwd.

	Returns
	-------
	int
		0 when clean or justified, 1 on an unjustified weakening.
	"""
	if not apply_root_flag(list_argv):
		return 1

	str_base = resolve_base()
	if str_base is None:
		return 0
	if not str_base:
		return 1

	list_changed = changed_paths(str_base)
	list_problems = collect_problems(list_changed, str_base)
	return report(list_problems, str_base, len(list_changed))


if __name__ == "__main__":
	# Windows' stdout defaults to cp1252, which cannot encode the status glyphs this script
	# prints — see check_backlog_ledger.py's identical guard.
	for cls_stream in (sys.stdout, sys.stderr):
		if hasattr(cls_stream, "reconfigure"):
			cls_stream.reconfigure(encoding="utf-8", errors="replace")

	sys.exit(main(sys.argv[1:]))
