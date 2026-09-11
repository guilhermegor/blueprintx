r"""Bound comment volume, with quality-assurance suppression pragmas exempt.

Owner's ruling (2026-08-28): a comment worth keeping is short enough to sit at its
call site; an explanation longer than that was always documentation wearing comment
syntax and belongs in ``docs/``, ``README.md`` or ``CONTRIBUTING.md``, with **one**
line left behind naming the decision and pointing at where the reasoning lives —
e.g. ``# ROUND_DOWN by contract; see docs/decisions/money.md``.

Two independent, differently-decidable defects (blueprintx#303), never conflated:

1. **The essay block** — a long run of consecutive comment lines. Bounded by
   RUN LENGTH, not by ratio: a config file explaining every setting on its own
   line is good and scores badly on density; one 80-line block above a single
   ``on:`` is bad and can score the same. The metric the owner is actually
   describing is the block, not how dense the file reads overall.
2. **The decorative banner** — a comment whose content is only punctuation
   (``# -------``), or a one-line comment sandwiched between two such rules
   (``# ----`` / ``# LINTING`` / ``# ----``). Trivially decidable by regex, and
   always a defect: the rule adds nothing and the middle line restates what the
   code directly beneath it already says.

A third shape — a comment paraphrasing the identifier on the next line — is real
noise but is NOT decidable by a machine, so it is deliberately absent here; per
this repo's own routing rule (a decidable question is a gate, a judgment call is a
review skill), that shape belongs to a review skill, never to this file.

QUALITY-ASSURANCE SUPPRESSIONS ARE NOT COMMENTS IN THE SENSE BEING BOUNDED. A
``# noqa``, a ``# type: ignore``, a ``# complexity-ok: <reason>`` is machine-read
configuration that happens to live in comment syntax — it must never count toward
a run, never be flagged as a banner, and never be stripped. Read from a DATA FILE
(``comment_budget_allowlist.txt``, beside this script) rather than a literal in the
parser, so adding a newly-adopted tool's pragma is a one-line data change that
needs no review of this file. The allowlist is ANTICIPATORY — built from every
pragma form the toolchain can emit, not from what the tree happens to contain
today (see the data file's own header for the ``codespell:ignore`` worked example).

Structural exemptions — shebang and PEP 263 encoding declarations — are handled
here directly, because they are positional (line 1 or 2), not textual; SPDX
headers and generated-file banners are textual and live in the same allowlist.

THE CEILING IS A STATED RATCHET, not a zero-violation number (blueprintx#168/PR
#295: a threshold must name which criterion set it). Measured on this tree
2026-08-28: the worst block was 80 lines (a workflow's header comment); ``INT_MAX_RUN``
is set just above that, so today's tree has zero run-length violations and the
number is honest about being lenient rather than quietly permissive. Tightening it
is the follow-up sweep, blueprintx#304 — deliberately out of scope here, since it
touches ~90% of the tree's comment lines and would collide with everything else
open. The DECORATIVE BANNER check carries no such ratchet: it is unconditionally a
defect, and this PR fixes the ones it finds in BlueprintX's own tree rather than
deferring them, because removing a banner is a strict subtraction with nothing to
move to ``docs/``.

Escape hatch: ``# comment-budget-ok: <reason>`` anywhere in a flagged block, reason
required — a bare marker does not exempt it, exactly like ``# complexity-ok:``.

⚠️ **The calibration IS the deliverable.** ``check_comment_language.py``'s first
draft reported 19 findings, 18 false. Every rule here — pragma lines break a run
rather than extending it; python comments come from ``tokenize`` so a ``#`` inside
a string is never mistaken for one; docstrings are excluded from the python count,
matching the issue's own measured table — is pinned by a named test in
``tests/unit/test_comment_budget_gate.py``. Do not "simplify" one away without
re-running it.
"""

import pathlib
import re
import sys
import tokenize


# The ratchet. See the module docstring for the criterion: just above the worst
# block measured on this tree (80 lines), so today's tree has zero run-length
# violations and #304 is what tightens it, not this gate.
INT_MAX_RUN = 85

STR_ESCAPE = "comment-budget-ok:"

# A structural line (shebang, PEP 263 encoding declaration) only ever appears
# on line 1 or 2 — never deeper, so this is not a magic number to tune.
INT_STRUCTURAL_LINE_LIMIT = 2

# A decorative banner "sandwich" is exactly rule / title / rule — three lines.
INT_BANNER_TRIPLE = 3

# `#`-comment file types, by suffix. `.py` is handled separately via `tokenize`
# because a `#` inside a string literal is not a comment and only the tokenizer
# knows the difference. `Makefile` (no suffix) and `.mk` are matched by name in
# `audit_paths`/`marker_for`, not here — the issue's own table missed Makefile
# for exactly this reason.
DICT_HASH_SUFFIXES = (".sh", ".yaml", ".yml", ".toml", ".ini", ".mk")

# `//`-comment file types. Block comments (`/* */`) are a known ceiling, not a
# gap: every measured violation in the issue's table is a line-comment block,
# and adding a second comment grammar for zero measured evidence is exactly the
# unrequested generality this repo's own philosophy argues against.
DICT_SLASH_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

# Directories that hold code we did not write or that is generated, mirroring
# check_function_length.py's list (`.claude` matters for the same reason: this
# gate's `--root` is overridable to the real repo root, which commonly sits
# under a `.claude/worktrees/<agent>/` copy of itself).
TUPLE_SKIP_DIRS = (
	".git",
	".claude",
	".mypy_cache",
	".pytest_cache",
	".ruff_cache",
	".venv",
	"__pycache__",
	"htmlcov",
	"node_modules",
	"site",
)

PATH_ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH_ALLOWLIST = pathlib.Path(__file__).resolve().parent / "comment_budget_allowlist.txt"

# PEP 263 — a `# -*- coding: utf-8 -*-` line is metadata, not prose, and only
# ever appears on line 1 or 2.
RE_ENCODING_DECL = re.compile(r"coding[:=]\s*[-\w.]+")

# A comment whose stripped content is nothing but rule punctuation — the
# decorative banner the issue names by example (`# -------`).
RE_BANNER_LINE = re.compile(r"^[-=*#~_\s]{3,}$")


def load_allowlist() -> tuple:
	"""Read the QA-suppression allowlist data file.

	Returns
	-------
	tuple of str
		Every non-blank, non-``#``-prefixed line, in file order. A missing file
		is a configuration error worth a loud failure, not a silent empty list —
		see ``main``'s zero-discovery guard for the same principle applied here.
	"""
	str_text = PATH_ALLOWLIST.read_text(encoding="utf-8")
	return tuple(
		str_line.strip()
		for str_line in str_text.splitlines()
		if str_line.strip() and not str_line.lstrip().startswith("#")
	)


def is_pragma_line(str_content: str, tuple_allowlist: tuple) -> bool:
	"""Return whether a comment line is machine-read configuration, not prose.

	Parameters
	----------
	str_content : str
		The comment's text, marker already stripped.
	tuple_allowlist : tuple of str
		Suppression substrings from ``load_allowlist``.

	Returns
	-------
	bool
		True when the line carries a QA suppression pragma or a structural
		exemption (SPDX header, generated-file banner) and must break — never
		extend — a comment run.
	"""
	return any(str_pragma in str_content for str_pragma in tuple_allowlist)


def line_breaks_run(int_line: int, str_raw: str, str_content: str, tuple_allowlist: tuple) -> bool:
	"""Return whether a comment line BREAKS a run rather than extending it.

	Shared by ``marker_blocks`` and ``python_blocks`` so the structural/pragma
	test has one body — the same reason ``check_codespell_sync.sh`` exists.

	Parameters
	----------
	int_line : int
		The line's 1-indexed position in the file.
	str_raw : str
		The comment token including its marker (``#!/usr/bin/env python`` or
		the raw tokenize string) — only the shebang form needs the marker.
	str_content : str
		The comment's text, marker already stripped.
	tuple_allowlist : tuple of str
		Suppression substrings from ``load_allowlist``.

	Returns
	-------
	bool
		True for a shebang, an encoding declaration, or a QA suppression pragma.
	"""
	bool_structural = int_line <= INT_STRUCTURAL_LINE_LIMIT and (
		str_raw.startswith("#!") or bool(RE_ENCODING_DECL.search(str_content))
	)
	return bool_structural or is_pragma_line(str_content, tuple_allowlist)


def _flush_block(list_out: list, int_start: int, list_block: list) -> list:
	"""Append a non-empty block to ``list_out`` and return a fresh empty block.

	Parameters
	----------
	list_out : list
		The accumulator both ``marker_blocks`` and ``python_blocks`` build.
	int_start : int
		The block's first line number.
	list_block : list
		The block's content lines so far.

	Returns
	-------
	list
		Always ``[]`` — the caller reassigns its running block to this.
	"""
	if list_block:
		list_out.append((int_start, list_block))
	return []


def marker_for(path_file: pathlib.Path) -> str:
	"""Return the comment marker for a file, or "" when the type is unsupported.

	Parameters
	----------
	path_file : pathlib.Path
		The file being checked.

	Returns
	-------
	str
		``"#"`` or ``"//"``; empty when nothing here budgets this file's type.
	"""
	if path_file.name == "Makefile" or path_file.suffix in DICT_HASH_SUFFIXES:
		return "#"
	if path_file.suffix in DICT_SLASH_SUFFIXES:
		return "//"
	return ""


def marker_blocks(str_source: str, str_marker: str) -> list:
	"""Return consecutive comment-line runs, pragma and structural lines excluded.

	⚠️ A pragma or structural line does not just fail to COUNT — it BREAKS the
	run, the same way a blank or code line would. Two five-line rationale blocks
	separated by one ``# noqa`` are two five-line findings, never one eleven-line
	finding, because the pragma line is not prose the owner would ever move to
	``docs/``.

	Parameters
	----------
	str_source : str
		The file's text.
	str_marker : str
		``"#"`` or ``"//"``.

	Returns
	-------
	list of tuple
		``(int_start_line, list_of_content_lines)`` per block, 1-indexed.
	"""
	tuple_allowlist = load_allowlist()
	list_out: list = []
	list_block: list = []
	int_start = 0
	for int_line, str_line in enumerate(str_source.splitlines(), 1):
		str_stripped = str_line.lstrip()
		if not str_stripped.startswith(str_marker):
			list_block = _flush_block(list_out, int_start, list_block)
			continue
		str_content = str_stripped[len(str_marker) :]
		if line_breaks_run(int_line, str_stripped, str_content, tuple_allowlist):
			list_block = _flush_block(list_out, int_start, list_block)
			continue
		if not list_block:
			int_start = int_line
		list_block.append(str_content)
	if list_block:
		list_out.append((int_start, list_block))
	return list_out


def python_blocks(str_source: str) -> list:
	"""Return Python ``#`` comment blocks via ``tokenize``, docstrings excluded.

	Docstrings are documentation, not the comment volume this gate bounds — the
	issue's own measured table excludes them from the ``.py`` figure for the same
	reason. A pragma line (``# noqa`` et al.) breaks a block exactly as in
	``marker_blocks``.

	Parameters
	----------
	str_source : str
		Python source text.

	Returns
	-------
	list of tuple
		``(int_start_line, list_of_content_lines)`` per block; empty when the
		source cannot be tokenised — a syntax error is ruff's finding, not this
		gate's.
	"""
	tuple_allowlist = load_allowlist()
	list_out: list = []
	list_block: list = []
	int_start = 0
	int_previous = -2
	try:
		for cls_token in tokenize.generate_tokens(iter(str_source.splitlines(True)).__next__):
			if cls_token.type != tokenize.COMMENT:
				continue
			int_line = cls_token.start[0]
			str_content = cls_token.string.lstrip("#")
			if line_breaks_run(int_line, cls_token.string, str_content, tuple_allowlist):
				list_block = _flush_block(list_out, int_start, list_block)
				int_previous = int_line
				continue
			if int_line != int_previous + 1 and list_block:
				list_block = _flush_block(list_out, int_start, list_block)
			if not list_block:
				int_start = int_line
			list_block.append(str_content)
			int_previous = int_line
	except (tokenize.TokenError, IndentationError, SyntaxError):
		return []
	if list_block:
		list_out.append((int_start, list_block))
	return list_out


def has_valid_escape(list_lines: list) -> bool:
	"""Return whether a block carries ``# comment-budget-ok: <reason>``.

	Mirrors ``check_complexity.sh``'s ``STR_ALLOW_MARKER`` handling exactly: a
	bare marker with no text after the colon does not exempt anything.

	Parameters
	----------
	list_lines : list of str
		A block's content lines.

	Returns
	-------
	bool
		True when the marker is present and followed by a non-empty reason.
	"""
	str_joined = "\n".join(list_lines)
	if STR_ESCAPE not in str_joined:
		return False
	str_reason = str_joined.split(STR_ESCAPE, 1)[1].splitlines()[0].strip()
	return bool(str_reason)


def banner_findings(int_start: int, list_lines: list) -> list:
	"""Return the decorative-banner defects inside one comment block.

	A punctuation-only line is a banner on its own; one flanked by two banner
	lines is the ``rule / SECTION NAME / rule`` triple the issue names by
	example, reported as a single three-line finding.

	Parameters
	----------
	int_start : int
		The block's first line number.
	list_lines : list of str
		The block's content lines.

	Returns
	-------
	list of tuple
		``(int_line, int_span)`` per decorative banner found.
	"""
	list_out = []
	int_index = 0
	while int_index < len(list_lines):
		bool_this = bool(RE_BANNER_LINE.match(list_lines[int_index]))
		bool_triple = (
			int_index + 2 < len(list_lines)
			and bool_this
			and not RE_BANNER_LINE.match(list_lines[int_index + 1])
			and list_lines[int_index + 1].strip()
			and bool(RE_BANNER_LINE.match(list_lines[int_index + 2]))
		)
		if bool_triple:
			list_out.append((int_start + int_index, INT_BANNER_TRIPLE))
			int_index += INT_BANNER_TRIPLE
			continue
		if bool_this:
			list_out.append((int_start + int_index, 1))
		int_index += 1
	return list_out


def file_problems(path_file: pathlib.Path) -> list:
	"""Return every finding for one file: long runs and decorative banners.

	Parameters
	----------
	path_file : pathlib.Path
		The file to check. An unsupported type yields nothing.

	Returns
	-------
	list of str
		Human-readable findings; empty when the file is clean.
	"""
	str_marker = marker_for(path_file)
	if not str_marker:
		return []
	try:
		str_source = path_file.read_text(encoding="utf-8")
	except (OSError, UnicodeDecodeError):
		return []

	try:
		str_shown = str(path_file.relative_to(PATH_ROOT))
	except ValueError:
		str_shown = str(path_file)

	list_blocks = (
		python_blocks(str_source)
		if path_file.suffix == ".py"
		else marker_blocks(str_source, str_marker)
	)

	list_problems = []
	for int_start, list_lines in list_blocks:
		int_length = len(list_lines)
		bool_hatched = has_valid_escape(list_lines)
		if int_length > INT_MAX_RUN and not bool_hatched:
			list_problems.append(
				f"{str_shown}:{int_start}: comment block is {int_length} lines "
				f"(max {INT_MAX_RUN}) — move the explanation to docs/, README.md or "
				f"CONTRIBUTING.md, leave one line pointing at it; escape hatch: "
				f"# {STR_ESCAPE} <reason>"
			)
		if not bool_hatched:
			for int_line, int_span in banner_findings(int_start, list_lines):
				str_shape = (
					"rule/title/rule" if int_span == INT_BANNER_TRIPLE else "punctuation-only line"
				)
				list_problems.append(
					f"{str_shown}:{int_line}: decorative banner ({str_shape}) — delete it, "
					f"the code beneath it already says this"
				)
	return list_problems


def audit_paths() -> list:
	"""Discover every checkable file under the repository root.

	Returns
	-------
	list of pathlib.Path
		Sorted paths across every supported extension plus extensionless
		``Makefile``, skipping vendored and generated trees. Compares path parts
		RELATIVE TO ``PATH_ROOT`` — see ``check_function_length.py`` for why an
		ancestor-based match would self-defeat under a `.claude/worktrees/` copy.
	"""
	tuple_suffixes = (".py", *DICT_HASH_SUFFIXES, *DICT_SLASH_SUFFIXES)
	list_paths = []
	for str_suffix in tuple_suffixes:
		for path_file in PATH_ROOT.rglob(f"*{str_suffix}"):
			if not any(
				str_part in TUPLE_SKIP_DIRS for str_part in path_file.relative_to(PATH_ROOT).parts
			):
				list_paths.append(path_file)
	for path_file in PATH_ROOT.rglob("Makefile"):
		if not any(
			str_part in TUPLE_SKIP_DIRS for str_part in path_file.relative_to(PATH_ROOT).parts
		):
			list_paths.append(path_file)
	return sorted(set(list_paths))


# `--root <dir>` is a flag plus its value, so argv must hold at least two entries.
_INT_FLAG_WITH_VALUE = 2


def main(list_argv: list) -> int:
	"""Check every named file for an over-long comment run or a decorative banner.

	Parameters
	----------
	list_argv : list of str
		Filenames, as pre-commit passes them. Empty means audit the whole
		repository; ``--root <dir>`` (first, like the other `--root`-enabled
		gates) repoints the audit and every relative-path display.

	Returns
	-------
	int
		0 when every file is clean, 1 on a violation.
	"""
	global PATH_ROOT  # noqa: PLW0603 -- see check_function_length.py for the same accepted pattern
	if list_argv[:1] == ["--root"]:
		if len(list_argv) < _INT_FLAG_WITH_VALUE:
			print("❌ --root needs a directory")
			return 1
		PATH_ROOT = pathlib.Path(list_argv[1]).resolve()
		list_argv = list_argv[2:]

	bool_audit = not list_argv
	list_paths = (
		[pathlib.Path(str_name).resolve() for str_name in list_argv]
		if list_argv
		else audit_paths()
	)

	# Zero discovered files in audit mode is a failure, not a pass, matching every
	# sibling gate in this family.
	if bool_audit and not list_paths:
		print(
			f"❌ no supported file found under {PATH_ROOT} — this gate would pass vacuously. "
			f"Check DICT_HASH_SUFFIXES/DICT_SLASH_SUFFIXES and TUPLE_SKIP_DIRS against the layout."
		)
		return 1

	list_problems = []
	for path_file in list_paths:
		list_problems.extend(file_problems(path_file))
	for str_problem in list_problems:
		print(str_problem)

	if not list_problems:
		print(f"✅ comment budget OK ({len(list_paths)} file(s) checked)")
		return 0

	print(
		f"\n{len(list_problems)} finding(s). A long block: move it to docs/, README.md or "
		f"CONTRIBUTING.md and leave one line pointing at it. A decorative banner: delete it. "
		f"Never touch a QA suppression — noqa, type: ignore, complexity-ok and friends are exempt "
		f"by design (see comment_budget_allowlist.txt)."
	)
	return 1


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
