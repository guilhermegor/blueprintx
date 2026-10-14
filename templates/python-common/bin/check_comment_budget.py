"""Refuse comments: zero tolerance outside an allowlist, enforced as a ratchet.

Owner's ruling (blueprintx#304, 2026-10-11): comments rot, so the tree carries none
except machine-read forms (``noqa``, ``type: ignore``, ``*-ok: <reason>`` markers,
shebangs, linter directives; the full list is ``comment_budget_allowlist.txt``). An
explanation worth keeping lives in ``docs/``, ``README.md`` or ``CONTRIBUTING.md``
and leaves **nothing** at the code site, not even a pointer.

Three independent checks, never conflated:

1. **The ratchet** (``comment_budget_baseline.txt`` at the root, ``<count> <path>``).
   Every non-allowlisted comment line counts. A file above its baseline fails; a file
   absent from the baseline has a baseline of 0, so a new file carries no comments; a
   file BELOW its baseline fails too ("lower it"), so the number only ever goes down
   and each sweep PR must record its win. ``--write-baseline`` regenerates the file.
   Without a baseline file the ratchet is off and only checks 2 and 3 run, which is
   how a generated project behaves until the shipped templates are themselves swept.
2. **The essay block**: a run of consecutive comment lines longer than ``INT_MAX_RUN``.
3. **The decorative banner**: a comment of only punctuation (``# -------``), or a
   one-line comment between two such rules.

Comments come from ``tokenize`` for Python (a ``#`` inside a string is never one, and
docstrings are not comments) and from a string-aware scan for ``#`` and ``//`` file
types, which counts trailing comments and ``/* */`` / JSDoc blocks line by line. The
run-length and banner checks still look only at full-line runs. Markdown is not
scanned at all, so the ``<!-- -->`` template instructions are out of scope by
construction. Allowlist entries match the START of a comment; ``~text`` entries
(generated-file banners) match anywhere but only in a file's first lines.

A pragma or structural line (shebang, coding cookie) is never counted and BREAKS a
run rather than extending it. The allowlist is a data file of substrings, anticipatory
rather than a census. Escape hatch for checks 2 and 3 only:
``# comment-budget-ok: <reason>``; it never exempts a comment from the ratchet.

Every rule is pinned by a named test in ``tests/unit/test_comment_budget_gate.py``.
"""

import os
import pathlib
import re
import subprocess
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

# `#`-comment file types, by suffix. `.py` is deliberately NOT in this tuple —
# its BLOCKS are extracted separately via `tokenize` (a `#` inside a string
# literal is not a comment and only the tokenizer knows the difference) — but
# `marker_for` below still must recognize `.py` explicitly, or `file_problems`
# short-circuits on its `not str_marker` guard before ever reaching the
# `.py`-specific branch, and every Python file goes unchecked while `audit_paths`
# reports it "checked" (blueprintx#466 — measured: 228/499 files "checked", 0
# findings, discovery non-zero and looking like coverage while checking nothing).
# `Makefile` (no suffix) and `.mk` are matched by name in `audit_paths`/
# `marker_for`, not here — the issue's own table missed Makefile for exactly
# this reason.
TUPLE_SCOPE1_HASH_SUFFIXES = (".sh", ".yaml", ".yml", ".toml", ".ini", ".mk")
TUPLE_SCOPE1_SLASH_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
TUPLE_YAML_SUFFIXES = (".yaml", ".yml")
TUPLE_SCOPE1_NAMES = ("Makefile",)

DICT_HASH_SUFFIXES = (
    *TUPLE_SCOPE1_HASH_SUFFIXES,
    ".conf",
    ".cfg",
    ".fragment",
    ".bats",
    ".rb",
    ".ps1",
    ".answers",
    ".sqlfluffignore",
)

TUPLE_HASH_NAMES = (
    "Makefile",
    ".gitignore",
    ".dockerignore",
    ".gitattributes",
    ".codespellrc",
    ".editorconfig",
    ".gitlint",
    ".sqlfluff",
    ".yamllint",
    ".pydocstyle",
    ".coveragerc",
    ".shellcheckrc",
    ".env.example",
    "requirements.txt",
    "required-checks.txt",
    "precommit_ci_parity_exemptions.txt",
    "comment_budget_allowlist.txt",
)

DICT_DASH_SUFFIXES = (".sql",)

# `//`-comment file types. Block comments (`/* */`) are a known ceiling, not a
# gap: every measured violation in the issue's table is a line-comment block,
# and adding a second comment grammar for zero measured evidence is exactly the
# unrequested generality this repo's own philosophy argues against.
DICT_SLASH_SUFFIXES = (*TUPLE_SCOPE1_SLASH_SUFFIXES, ".css")

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
STR_BASELINE_NAME = "comment_budget_baseline.txt"
STR_SCOPE_ROW = "scope "
INT_SCOPE = 2
STR_WRITE_BASELINE = "--write-baseline"
STR_ANYWHERE = "~"
INT_BANNER_HEAD = 10
STR_REQUIRE_BASELINE = "--require-baseline"
STR_COMPARE_BASELINE = "--compare-baseline"

# PEP 263 — a `# -*- coding: utf-8 -*-` line is metadata, not prose, and only
# ever appears on line 1 or 2.
RE_ENCODING_DECL = re.compile(r"coding[:=]\s*[-\w.]+")

# A comment whose stripped content is nothing but rule punctuation — the
# decorative banner the issue names by example (`# -------`).
RE_BANNER_LINE = re.compile(r"^[-=*#~_\s]{3,}$")

# The exact rule line of tests/CLAUDE.md's mandated test-section-banner
# convention ("# --------------------------" / "# <section>" /
# "# --------------------------") — measured (blueprintx#466) to occur
# NOWHERE else in the tree, always this shape, only in `.py` files. Matched
# structurally in banner_findings, NOT via the pragma allowlist: a pragma
# BREAKS a run (line_breaks_run), so listing this string there would let one
# dash line split an oversized block into two under-ceiling halves
# (blueprintx#479). The two rule lines still count toward the block's
# length — only the banner FINDING is suppressed, never the run. Scoped to
# Python test modules by is_test_module: the same triple in a production
# .py, a Makefile, a shell or a .ts file is a plain decorative banner.
STR_TEST_SECTION_RULE = "--------------------------"


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
    tuple_entries = tuple(
        str_line.strip()
        for str_line in str_text.splitlines()
        if str_line.strip() and not str_line.lstrip().startswith("#")
    )
    if any(not str_entry.lstrip(STR_ANYWHERE) for str_entry in tuple_entries):
        raise ValueError(
            f"{PATH_ALLOWLIST.name} has an empty pattern, which would exempt everything"
        )
    return tuple_entries


def matches_entry(str_entry: str, str_text: str, int_line: int) -> bool:
    """Return whether one allowlist entry exempts a comment.

    Parameters
    ----------
    str_entry : str
        An entry: a prefix of the comment, or ``~text`` for a generated-file banner,
        which matches anywhere in the comment but only within the first
        ``INT_BANNER_HEAD`` lines of a file.
    str_text : str
        The comment's text, marker stripped.
    int_line : int
        The comment's 1-indexed line.

    Returns
    -------
    bool
        True when the entry exempts the comment.
    """
    if not str_entry.startswith(STR_ANYWHERE):
        return str_text.startswith(str_entry)
    return int_line <= INT_BANNER_HEAD and str_entry[1:] in str_text


def is_pragma_line(str_content: str, tuple_allowlist: tuple, int_line: int = 1) -> bool:
    """Return whether a comment line is machine-read configuration, not prose.

    Parameters
    ----------
    str_content : str
        The comment's text, marker already stripped.
    tuple_allowlist : tuple of str
        Suppression entries from ``load_allowlist``.
    int_line : int, optional
        The comment's 1-indexed line; ``~`` entries only match near the top.

    Returns
    -------
    bool
        True when the line carries a QA suppression pragma or a structural
        exemption (SPDX header, generated-file banner) and must break — never
        extend — a comment run.
    """
    str_text = str_content.strip().lstrip("*").strip()
    return any(matches_entry(str_pragma, str_text, int_line) for str_pragma in tuple_allowlist)


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
    return bool_structural or is_pragma_line(str_content, tuple_allowlist, int_line)


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
        ``"#"``, ``"//"`` or ``"--"``; empty when nothing here budgets this file's type.
    """
    bool_hash_name = path_file.name in TUPLE_HASH_NAMES or path_file.name.startswith("Dockerfile")
    bool_hash_file = bool_hash_name or path_file.suffix in DICT_HASH_SUFFIXES
    if bool_hash_file or path_file.suffix == ".py":
        return "#"
    if path_file.suffix in DICT_DASH_SUFFIXES:
        return "--"
    if path_file.suffix in DICT_SLASH_SUFFIXES:
        return "//"
    return ""


def heredoc_lines(str_source: str, bool_dedent: bool = False) -> set:
    """Return the 1-indexed lines that are heredoc body or terminator.

    A heredoc body is data a script writes out, not a comment: a ``#!`` shebang or a
    ``# foo`` line inside one is output. Covers shell ``<<EOF``, ``<<'EOF'``, ``<<"EOF"``,
    ``<<-EOF`` and Ruby ``<<~EOS``; a here-string ``<<<`` and a YAML ``<<:`` merge key
    are not heredocs.

    Parameters
    ----------
    str_source : str
        The file's text.
    bool_dedent : bool, optional
        True for YAML, where a block scalar dedents the script, so an indented terminator
        ends a plain ``<<EOF`` heredoc too.

    Returns
    -------
    set of int
        Lines after the opening line through the terminator, inclusive.
    """
    set_out: set = set()
    str_end = ""
    bool_indented = False
    for int_line, str_line in enumerate(str_source.splitlines(), 1):
        if str_end:
            set_out.add(int_line)
            str_seen = str_line.strip() if bool_indented or bool_dedent else str_line.rstrip()
            str_end = "" if str_seen == str_end else str_end
            continue
        cls_match = None if str_line.lstrip().startswith("#") else RE_HEREDOC.search(str_line)
        if cls_match:
            str_end = cls_match.group(3)
            bool_indented = cls_match.group(1) is not None
    return set_out


def marker_blocks(str_source: str, str_marker: str, bool_yaml: bool = False) -> list:
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
    bool_yaml : bool, optional
        True for YAML, where heredoc terminators may be indented.

    Returns
    -------
    list of tuple
        ``(int_start_line, list_of_content_lines)`` per block, 1-indexed.
    """
    tuple_allowlist = load_allowlist()
    list_out: list = []
    list_block: list = []
    int_start = 0
    set_data = heredoc_lines(str_source, bool_yaml) if str_marker == "#" else set()
    for int_line, str_line in enumerate(str_source.splitlines(), 1):
        str_stripped = str_line.lstrip()
        if int_line in set_data or not str_stripped.startswith(str_marker):
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
    # `.splitlines()` on the tail after the marker is EMPTY, not `[""]`, when the
    # marker is the very last text in the block — a bare `# comment-budget-ok:`
    # with no trailing newline and no reason. `[0]` on that crashed the first
    # draft instead of doing what a bare marker must do: fail the exemption.
    list_after_marker = str_joined.split(STR_ESCAPE, 1)[1].splitlines()
    str_reason = list_after_marker[0].strip() if list_after_marker else ""
    return bool(str_reason)


def is_test_module(path_file: pathlib.Path) -> bool:
    """Return whether a path is a Python test module.

    The test-section-banner exemption is scoped to these files and no others:
    the convention comes from ``tests/CLAUDE.md`` and was measured
    (blueprintx#466) to occur only in ``.py`` test modules. A production
    ``.py``, a Makefile, a shell script or a ``.ts`` file carrying the same
    triple is a decorative banner, not a mandated section header
    (blueprintx#479).

    Identified by pytest's OWN discovery convention — a ``tests`` path segment
    or a ``test_`` filename prefix — not by directory alone. Directory alone
    was the first draft and it was wrong: the four
    ``optional/multi_pipeline/test_pipeline.py`` templates are real test
    modules shipped outside any ``tests/`` tree, and scoping to the directory
    flagged 6 mandated banners in them.

    Parameters
    ----------
    path_file : pathlib.Path
        The file being checked.

    Returns
    -------
    bool
        True for a ``.py`` file pytest would collect as a test module.
    """
    if path_file.suffix != ".py":
        return False
    return "tests" in path_file.parts or path_file.name.startswith("test_")


def is_exempt_section_banner(list_lines: list, int_index: int) -> bool:
    """Return whether a triple at ``int_index`` is the mandated test-section banner.

    Matched on the FULL triple, not on any line containing 26 dashes, so a
    lone rule line elsewhere gets no special treatment. The lines still count
    toward the block's run length (see ``banner_findings`` — this only
    suppresses the FINDING, never the block accumulation).

    Parameters
    ----------
    list_lines : list of str
        The block's content lines.
    int_index : int
        Index of the triple's opening rule line.

    Returns
    -------
    bool
        True when both outer lines are exactly ``STR_TEST_SECTION_RULE``.
    """
    return (
        list_lines[int_index].strip() == STR_TEST_SECTION_RULE
        and list_lines[int_index + 2].strip() == STR_TEST_SECTION_RULE
    )


def banner_findings(
    int_start: int, list_lines: list, bool_allow_section_banner: bool = False
) -> list:
    """Return the decorative-banner defects inside one comment block.

    A punctuation-only line is a banner on its own; one flanked by two banner
    lines is the ``rule / SECTION NAME / rule`` triple the issue names by
    example, reported as a single three-line finding — except the exact
    tests/CLAUDE.md test-section-banner triple in a Python test module,
    which is exempt (see ``is_exempt_section_banner`` and ``is_test_module``).

    Parameters
    ----------
    int_start : int
        The block's first line number.
    list_lines : list of str
        The block's content lines.
    bool_allow_section_banner : bool, optional
        Whether the ``tests/CLAUDE.md`` section-banner exemption applies to this
        file. Defaults to False so an unclassified caller gets the strict
        behaviour: the exemption is opt-in per file type, never the fallback.

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
            bool_exempt = bool_allow_section_banner and is_exempt_section_banner(
                list_lines, int_index
            )
            if not bool_exempt:
                list_out.append((int_start + int_index, INT_BANNER_TRIPLE))
            int_index += INT_BANNER_TRIPLE
            continue
        if bool_this:
            list_out.append((int_start + int_index, 1))
        int_index += 1
    return list_out


def comment_blocks(str_source: str, str_marker: str) -> list:
    """Group the counted comments of a file into runs of consecutive lines.

    Parameters
    ----------
    str_source : str
        The file's text.
    str_marker : str
        The comment marker.

    Returns
    -------
    list of tuple
        ``(int_start_line, list_of_content_lines)`` per run, including ``/* */`` blocks.
    """
    list_out: list = []
    int_prev = 0
    for int_line, str_text in counted_comments(str_source, str_marker):
        if list_out and int_line == int_prev + 1:
            list_out[-1][1].append(str_text)
        else:
            list_out.append((int_line, [str_text]))
        int_prev = int_line
    return list_out


def blocks_for(path_file: pathlib.Path, str_source: str, str_marker: str) -> list:
    """Return the comment runs of a file by the grammar its type needs.

    Parameters
    ----------
    path_file : pathlib.Path
        The file.
    str_source : str
        Its text.
    str_marker : str
        Its comment marker.

    Returns
    -------
    list of tuple
        Runs from ``tokenize`` for ``.py``, from the token scanner for CSS block comments,
        and from line-start markers otherwise.
    """
    if path_file.suffix == ".py":
        return python_blocks(str_source)
    if path_file.suffix == ".css":
        return comment_blocks(str_source, str_marker)
    return marker_blocks(str_source, str_marker, path_file.suffix in TUPLE_YAML_SUFFIXES)


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

    list_blocks = blocks_for(path_file, str_source, str_marker)

    list_problems = []
    for int_start, list_lines in list_blocks:
        int_length = len(list_lines)
        bool_hatched = has_valid_escape(list_lines)
        if int_length > INT_MAX_RUN and not bool_hatched:
            list_problems.append(
                f"{str_shown}:{int_start}: comment block is {int_length} lines "
                f"(max {INT_MAX_RUN}) — move the explanation to docs/, README.md or "
                f"CONTRIBUTING.md and delete the comment; escape hatch: "
                f"# {STR_ESCAPE} <reason>"
            )
        if not bool_hatched:
            for int_line, int_span in banner_findings(
                int_start, list_lines, is_test_module(path_file)
            ):
                str_shape = (
                    "rule/title/rule" if int_span == INT_BANNER_TRIPLE else "punctuation-only line"
                )
                list_problems.append(
                    f"{str_shown}:{int_line}: decorative banner ({str_shape}) — delete it, "
                    f"the code beneath it already says this"
                )
    return list_problems


def tracked_files() -> list | None:
    """List the files git tracks under the audit root.

    Returns
    -------
    list of pathlib.Path or None
        Tracked files that still exist, so an untracked local file never changes the
        count. None when the root is not a git checkout (a scaffold before ``git init``).
    """
    if not (PATH_ROOT / ".git").exists():
        return None
    str_listing = git_out("ls-files", "-z")
    if not str_listing:
        return None
    list_found = [PATH_ROOT / str_name for str_name in str_listing.split("\0") if str_name]
    return [path_file for path_file in list_found if path_file.is_file()]


def walked_files() -> list:
    """List every file under the audit root, pruning the skipped directories.

    Returns
    -------
    list of pathlib.Path
        The fallback when git cannot say what is tracked.
    """
    list_found = []
    for str_dir, list_dirs, list_names in os.walk(PATH_ROOT):
        list_dirs[:] = [str_part for str_part in list_dirs if str_part not in TUPLE_SKIP_DIRS]
        list_found.extend(pathlib.Path(str_dir) / str_name for str_name in list_names)
    return list_found


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
    list_candidates = tracked_files()
    if list_candidates is None:
        list_candidates = walked_files()
    return sorted(
        path_file
        for path_file in set(list_candidates)
        if marker_for(path_file)
        and not any(
            str_part in TUPLE_SKIP_DIRS for str_part in path_file.relative_to(PATH_ROOT).parts
        )
    )


RE_HASH_TOKEN = re.compile(r"""'[^'\n]*'|"(?:\\.|[^"\\\n])*"|(?<!\S)#[^\n]*""")
RE_SLASH_TOKEN = re.compile(
    r"""'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|`[^`]*`|//[^\n]*|/\*.*?\*/""", re.DOTALL
)
RE_DASH_TOKEN = re.compile(r"""'(?:[^']|'')*'|"[^"]*"|--[^\n]*""")
RE_HEREDOC = re.compile(r"""(?<!<)<<(-|~)?[ \t]*(["']?)([A-Za-z_][A-Za-z0-9_]*)\2""")
RE_SHA_PIN = re.compile(r"@[0-9a-f]{40}\b")
RE_VERSION_NOTE = re.compile(r"^\s*v?\d+(\.\d+)*\S*\s*$")


def scan_comments(str_source: str, str_marker: str) -> list:
    """Return every comment line in a ``#`` or ``//`` file, trailing and ``/* */`` included.

    Strings are skipped so a ``#`` or ``//`` inside one is not a comment. A multi-line
    block comment yields one entry per line it spans.

    Parameters
    ----------
    str_source : str
        The file's text.
    str_marker : str
        ``"#"`` or ``"//"``.

    Returns
    -------
    list of tuple
        ``(int_line, str_text)``, text with the marker (``#``, ``//``, ``/*``) removed.
    """
    re_token = {"#": RE_HASH_TOKEN, "--": RE_DASH_TOKEN}.get(str_marker, RE_SLASH_TOKEN)
    list_out = []
    for cls_match in re_token.finditer(str_source):
        str_found = cls_match.group()
        if not str_found.startswith((str_marker, "/*")):
            continue
        int_first = str_source.count("\n", 0, cls_match.start()) + 1
        str_body = (
            str_found[len(str_marker) :] if str_found.startswith(str_marker) else str_found[2:-2]
        )
        list_out.extend(
            (int_first + int_i, str_text) for int_i, str_text in enumerate(str_body.split("\n"))
        )
    return list_out


def counted_comments(str_source: str, str_marker: str, bool_yaml: bool = False) -> list:
    """Return the comment lines that count: every one outside the allowlist.

    Parameters
    ----------
    str_source : str
        The file's text.
    str_marker : str
        ``"#"`` or ``"//"``.
    bool_yaml : bool, optional
        True for YAML, where heredoc terminators may be indented.

    Returns
    -------
    list of tuple
        ``(int_line, str_text)`` per counted comment line. A ``# vX`` after a SHA-pinned
        ``uses:`` is exempt: Dependabot rewrites it and it is the only readable version.
    """
    tuple_allowlist = load_allowlist()
    list_lines = str_source.split("\n")
    set_data = heredoc_lines(str_source, bool_yaml) if str_marker == "#" else set()
    return [
        (int_line, str_text)
        for int_line, str_text in scan_comments(str_source, str_marker)
        if int_line not in set_data
        and not line_breaks_run(int_line, str_marker + str_text, str_text, tuple_allowlist)
        and not (RE_SHA_PIN.search(list_lines[int_line - 1]) and RE_VERSION_NOTE.match(str_text))
    ]


def comment_line_count(path_file: pathlib.Path) -> int:
    """Count the non-allowlisted comment lines in one file, trailing comments included.

    Parameters
    ----------
    path_file : pathlib.Path
        The file to count. An unsupported or unreadable file counts 0.

    Returns
    -------
    int
        Comment lines outside the allowlist; docstrings and pragmas excluded.
    """
    str_marker = marker_for(path_file)
    if not str_marker:
        return 0
    try:
        str_source = path_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    if path_file.suffix == ".py":
        return sum(len(list_lines) for _, list_lines in python_blocks(str_source))
    return len(counted_comments(str_source, str_marker, path_file.suffix in TUPLE_YAML_SUFFIXES))


def shown_path(path_file: pathlib.Path) -> str:
    """Return the root-relative POSIX path a baseline row is keyed by.

    Parameters
    ----------
    path_file : pathlib.Path
        A file under ``PATH_ROOT``.

    Returns
    -------
    str
        The relative path, or the path as given when it lies outside the root.
    """
    try:
        return path_file.relative_to(PATH_ROOT).as_posix()
    except ValueError:
        return path_file.as_posix()


def parse_baseline_row(str_line: str) -> dict:
    """Parse one ``<count> <path>`` baseline row.

    Parameters
    ----------
    str_line : str
        A non-blank baseline line.

    Returns
    -------
    dict
        ``{path: count}``.

    Raises
    ------
    ValueError
        When the row is not a non-negative integer, a space, and a path.
    """
    str_count, _, str_path = str_line.partition(" ")
    if not (str_count.isdigit() and str_path):
        raise ValueError(f"malformed baseline row: {str_line!r}")
    return {str_path: int(str_count)}


def parse_baseline_text(str_text: str) -> tuple:
    """Parse baseline text into its scope version and its rows.

    Parameters
    ----------
    str_text : str
        The baseline file's content. A ``scope <n>`` row records which file types the
        run that wrote it discovered; a file without one is scope 1.

    Returns
    -------
    tuple
        ``(int_scope, {path: count})``.
    """
    int_scope = 1
    dict_out = {}
    for str_line in str_text.splitlines():
        if str_line.startswith(STR_SCOPE_ROW):
            int_scope = int(str_line[len(STR_SCOPE_ROW) :])
        elif str_line.strip():
            dict_out.update(parse_baseline_row(str_line))
    return int_scope, dict_out


def baseline_scope() -> int:
    """Return the discovery scope recorded in the committed baseline.

    Returns
    -------
    int
        The ``scope`` row's value, 1 when the baseline predates it.
    """
    return parse_baseline_text((PATH_ROOT / STR_BASELINE_NAME).read_text(encoding="utf-8"))[0]


def load_baseline() -> dict | None:
    """Read ``comment_budget_baseline.txt`` from the audit root.

    Returns
    -------
    dict or None
        ``{relative_path: count}``, or None when the file is absent (ratchet off).
    """
    path_baseline = PATH_ROOT / STR_BASELINE_NAME
    if not path_baseline.is_file():
        return None
    return parse_baseline_text(path_baseline.read_text(encoding="utf-8"))[1]


def current_counts(list_paths: list) -> dict:
    """Return ``{relative_path: count}`` for every file with at least one comment.

    Parameters
    ----------
    list_paths : list of pathlib.Path
        Files to count.

    Returns
    -------
    dict
        Only files with a non-zero count, so absence means 0.
    """
    dict_counts = {
        shown_path(path_file): comment_line_count(path_file) for path_file in list_paths
    }
    return {str_path: int_n for str_path, int_n in dict_counts.items() if int_n}


def ratchet_problems(dict_counts: dict, dict_baseline: dict, set_scope: set | None) -> list:
    """Compare counts with the baseline in both directions.

    Parameters
    ----------
    dict_counts : dict
        Current ``{path: count}``, non-zero only.
    dict_baseline : dict
        Recorded ``{path: count}``.
    set_scope : set of str or None
        Paths being checked; None means the whole tree (so a vanished file is stale).

    Returns
    -------
    list of str
        One finding per file above its baseline, and one per file below it.
    """
    list_problems = []
    for str_path in sorted(set(dict_counts) | set(dict_baseline)):
        if set_scope is not None and str_path not in set_scope:
            continue
        int_now = dict_counts.get(str_path, 0)
        int_was = dict_baseline.get(str_path, 0)
        if int_now > int_was:
            list_problems.append(
                f"{str_path}: {int_now} comment line(s), baseline {int_was} - comments are not "
                f"allowed here; delete them and move any explanation to docs/"
            )
        elif int_now < int_was:
            list_problems.append(
                f"{str_path}: {int_now} comment line(s), baseline {int_was} - stale baseline, "
                f"lower it with --write-baseline"
            )
    return list_problems


def write_baseline(dict_counts: dict) -> None:
    """Write the baseline file at the audit root, sorted by path.

    Parameters
    ----------
    dict_counts : dict
        ``{relative_path: count}`` to record.
    """
    str_rows = f"{STR_SCOPE_ROW}{INT_SCOPE}\n" + "".join(
        f"{int_n} {str_path}\n" for str_path, int_n in sorted(dict_counts.items())
    )
    (PATH_ROOT / STR_BASELINE_NAME).write_text(str_rows, encoding="utf-8")
    print(f"wrote {len(dict_counts)} file(s), {sum(dict_counts.values())} comment line(s)")


def git_out(*list_args: str) -> str:
    """Run a read-only git command inside ``PATH_ROOT`` and return stdout, "" on failure.

    Parameters
    ----------
    *list_args : str
        Git arguments.

    Returns
    -------
    str
        Standard output, or an empty string when git is unavailable or fails.
    """
    try:
        return subprocess.run(  # noqa: S603 -- fixed git argv, no shell
            ["git", "-C", str(PATH_ROOT), *list_args],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return ""


def default_base() -> str:
    """Return the ref renames are detected against: the merge-base with origin's default.

    Returns
    -------
    str
        ``merge-base(origin/main, HEAD)`` or the ``origin/master`` equivalent; ``HEAD``
        when neither exists, which still sees an uncommitted ``git mv``.
    """
    for str_ref in ("origin/main", "origin/master"):
        str_base = git_out("merge-base", str_ref, "HEAD").strip()
        if str_base:
            return str_base
    return "HEAD"


def rename_map(str_base: str) -> dict:
    """Return ``{new_path: old_path}`` for renames git detects between ``str_base`` and now.

    Parameters
    ----------
    str_base : str
        Git ref to diff the working tree against; committed and uncommitted renames
        both show.

    Returns
    -------
    dict
        Empty when git is unavailable or nothing was renamed.
    """
    list_tokens = git_out("diff", "-M", "-z", "--name-status", str_base, "--").split("\0")
    dict_out = {}
    int_i = 0
    while int_i < len(list_tokens) - 1:
        bool_rename = list_tokens[int_i].startswith("R")
        if bool_rename:
            dict_out[list_tokens[int_i + 2]] = list_tokens[int_i + 1]
        int_i += 3 if bool_rename else 2
    return dict_out


def scanned_at_scope_one(str_path: str) -> bool:
    """Return whether the first discovery scope already read this path's file type.

    Parameters
    ----------
    str_path : str
        A baseline path.

    Returns
    -------
    bool
        True for Python, the scope-1 ``#`` and ``//`` suffixes and ``Makefile``: a row for
        one of these is never the product of a widened scope, so it is always held.
    """
    path_file = pathlib.PurePosixPath(str_path)
    tuple_suffixes = (".py", *TUPLE_SCOPE1_HASH_SUFFIXES, *TUPLE_SCOPE1_SLASH_SUFFIXES)
    return path_file.suffix in tuple_suffixes or path_file.name in TUPLE_SCOPE1_NAMES


def raised_rows(
    dict_new: dict, dict_old: dict, dict_renames: dict, bool_widened: bool = False
) -> list:
    """Return the reasons ``dict_new`` raises the ratchet over ``dict_old``.

    A path absent from ``dict_old`` has budget 0, except a git-detected rename, which
    inherits its source's row. Freed budget never transfers to an unrelated new file.

    Parameters
    ----------
    dict_new : dict
        Proposed ``{path: count}``.
    dict_old : dict
        Reference ``{path: count}``.
    dict_renames : dict
        ``{new_path: old_path}`` from ``rename_map``.
    bool_widened : bool, optional
        True when the reference was written under an older discovery scope: paths whose
        file type that scope never read are exempt; every other path is held to its row,
        and a new or renamed file of a scanned type starts from 0 or its source's row.

    Returns
    -------
    list of str
        One message per violation; empty when the ratchet did not go up.
    """
    return [
        f"{str_path}: {int_n} comment line(s), allowed "
        f"{dict_old.get(str_path, dict_old.get(dict_renames.get(str_path, ''), 0))} - "
        f"the ratchet never goes up"
        for str_path, int_n in sorted(dict_new.items())
        if not (bool_widened and not scanned_at_scope_one(str_path))
        and int_n > dict_old.get(str_path, dict_old.get(dict_renames.get(str_path, ""), 0))
    ]


def regenerate_baseline(list_paths: list, bool_audit: bool) -> int:
    """Rewrite the baseline from a full audit, refusing any increase over an existing one.

    Parameters
    ----------
    list_paths : list of pathlib.Path
        The files counted.
    bool_audit : bool
        Whether this is a whole-tree run; a scoped run would drop every other row.

    Returns
    -------
    int
        0 after writing, 1 when refused.
    """
    if not bool_audit:
        print("❌ --write-baseline needs a full audit; do not name files")
        return 1
    dict_counts = current_counts(list_paths)
    dict_old = load_baseline()
    bool_widened = dict_old is not None and baseline_scope() < INT_SCOPE
    list_raised = (
        []
        if dict_old is None
        else raised_rows(dict_counts, dict_old, rename_map(default_base()), bool_widened)
    )
    for str_message in list_raised:
        print(str_message)
    if list_raised:
        return 1
    write_baseline(dict_counts)
    return 0


def compare_problems(str_reference: str) -> list:
    """Compare the committed baseline with a reference copy (the PR's base branch).

    Hand-editing the baseline upward would otherwise pass every other check.

    Parameters
    ----------
    str_reference : str
        Path to the reference baseline file.

    Returns
    -------
    list of str
        Findings; empty when the committed baseline did not go up.
    """
    try:
        str_ref_text = pathlib.Path(str_reference).read_text(encoding="utf-8")
    except OSError as cls_error:
        raise ValueError(f"cannot read the reference baseline {str_reference}") from cls_error
    int_scope, dict_ref = parse_baseline_text(str_ref_text)
    return raised_rows(
        load_baseline() or {}, dict_ref, rename_map("FETCH_HEAD"), int_scope < INT_SCOPE
    )


def baseline_problems(list_paths: list, bool_audit: bool, bool_require: bool) -> list:
    """Return the ratchet findings, or one finding when a required baseline is missing.

    Parameters
    ----------
    list_paths : list of pathlib.Path
        The files checked.
    bool_audit : bool
        Whether this is a whole-tree run.
    bool_require : bool
        True for the repository-root invocation, where no baseline file means the
        ratchet was deleted rather than never adopted.

    Returns
    -------
    list of str
        Findings; empty when the ratchet is off or clean.
    """
    dict_baseline = load_baseline()
    if dict_baseline is None:
        return [
            f"{STR_BASELINE_NAME} is missing but {STR_REQUIRE_BASELINE} was given"
        ] * bool_require
    set_scope = None if bool_audit else {shown_path(path_file) for path_file in list_paths}
    return ratchet_problems(current_counts(list_paths), dict_baseline, set_scope)


# `--root <dir>` is a flag plus its value, so argv must hold at least two entries.
_INT_FLAG_WITH_VALUE = 2


def apply_root_flag(list_argv: list) -> list | None:
    """Consume a leading ``--root <dir>`` and repoint ``PATH_ROOT`` at it.

    Parameters
    ----------
    list_argv : list of str
        Raw arguments.

    Returns
    -------
    list or None
        The remaining arguments, or None when ``--root`` has no value.
    """
    global PATH_ROOT  # noqa: PLW0603 -- see check_function_length.py for the same accepted pattern
    if list_argv[:1] != ["--root"]:
        return list_argv
    if len(list_argv) < _INT_FLAG_WITH_VALUE:
        return None
    PATH_ROOT = pathlib.Path(list_argv[1]).resolve()
    return list_argv[2:]


def split_flags(list_rest: list) -> tuple:
    """Separate the gate's own flags from the file names.

    Parameters
    ----------
    list_rest : list of str
        Arguments after ``--root`` was consumed.

    Returns
    -------
    tuple
        ``(write, require, reference_path, file_names)``; the reference is "" when
        ``--compare-baseline`` was not given.
    """
    str_reference = ""
    list_names = list(list_rest)
    if STR_COMPARE_BASELINE in list_names:
        int_at = list_names.index(STR_COMPARE_BASELINE)
        if int_at + 1 >= len(list_names):
            raise ValueError(f"{STR_COMPARE_BASELINE} needs a file")
        str_reference = list_names[int_at + 1]
        del list_names[int_at : int_at + 2]
    bool_write = STR_WRITE_BASELINE in list_names
    bool_require = STR_REQUIRE_BASELINE in list_names
    tuple_flags = (STR_WRITE_BASELINE, STR_REQUIRE_BASELINE)
    return bool_write, bool_require, str_reference, [n for n in list_names if n not in tuple_flags]


def run(list_argv: list) -> int:
    """Check comments: ratchet against the baseline, long runs, decorative banners.

    Parameters
    ----------
    list_argv : list of str
        Filenames, as pre-commit passes them. Empty means audit the whole
        repository. ``--root <dir>`` (first) repoints the audit; ``--write-baseline``
        regenerates ``comment_budget_baseline.txt`` instead of checking (full audit
        only, never upward); ``--require-baseline`` fails when that file is absent;
        ``--compare-baseline <file>`` fails when the baseline exceeds that reference
        copy (CI passes the base branch's).

    Returns
    -------
    int
        0 when everything is clean, 1 on a violation.
    """
    list_rest = apply_root_flag(list_argv)
    if list_rest is None:
        print("❌ --root needs a directory")
        return 1
    bool_write, bool_require, str_reference, list_argv = split_flags(list_rest)

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

    if bool_write:
        return regenerate_baseline(list_paths, bool_audit)

    list_problems = baseline_problems(list_paths, bool_audit, bool_require)
    if str_reference:
        list_problems.extend(compare_problems(str_reference))
    for path_file in list_paths:
        list_problems.extend(file_problems(path_file))
    for str_problem in list_problems:
        print(str_problem)

    if not list_problems:
        print(f"✅ comment budget OK ({len(list_paths)} file(s) checked)")
        return 0

    print(
        f"\n{len(list_problems)} finding(s). Delete the comment and put any explanation in "
        f"docs/, README.md or CONTRIBUTING.md; leave nothing behind. A stale baseline is "
        f"lowered with --write-baseline. QA suppressions (noqa, type: ignore, *-ok: markers) "
        f"are exempt by design (see comment_budget_allowlist.txt)."
    )
    return 1


def main(list_argv: list) -> int:
    """Run the gate, reporting a malformed baseline as a finding rather than a traceback.

    Parameters
    ----------
    list_argv : list of str
        Arguments, as for ``run``.

    Returns
    -------
    int
        0 when clean, 1 on a violation or a malformed baseline.
    """
    try:
        return run(list_argv)
    except ValueError as cls_error:
        print(f"❌ {cls_error}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
