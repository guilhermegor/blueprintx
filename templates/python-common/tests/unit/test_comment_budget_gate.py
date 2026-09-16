"""Unit tests for the comment-budget gate (blueprintx#303).

**The calibration is the thing under test**, same rule as
``test_comment_language_gate.py``: a rule that "simplifies" away one class of
false positive or false negative keeps the obvious cases passing while
quietly reopening the exact gap it was written to close. Each test below pins
one measured behaviour by name — the should-fail witness the issue asks for
(``test_a_run_one_line_over_the_ceiling_is_flagged`` /
``test_the_same_run_passes_with_a_pragma_in_the_middle``) is the negative
control: the two tests share the same oversized run, differing only by one
``# noqa`` line, so a change that breaks the "pragma breaks a run" rule fails
the second test while the first stays green.
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


_BIN = Path(__file__).resolve().parents[2] / "bin"


def _load(str_name: str) -> ModuleType:
	"""Load a ``bin/`` script by path (``bin/`` is not a package).

	Parameters
	----------
	str_name : str
		Module stem under ``bin/``.

	Returns
	-------
	ModuleType
		The imported module.
	"""
	cls_spec = importlib.util.spec_from_file_location(str_name, _BIN / f"{str_name}.py")
	cls_module = importlib.util.module_from_spec(cls_spec)
	sys.modules[str_name] = cls_module
	cls_spec.loader.exec_module(cls_module)
	return cls_module


gate = _load("check_comment_budget")


# --------------------------
# The ratchet ceiling — should-fail witness
# --------------------------


def test_a_short_comment_block_is_not_flagged(tmp_path: Path) -> None:
	"""A handful of comment lines, well under the ratchet, is clean.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_file = tmp_path / "probe.sh"
	path_file.write_text("# short\n# rationale\necho hi\n", encoding="utf-8")
	assert gate.file_problems(path_file) == []


def test_a_run_one_line_over_the_ceiling_is_flagged(tmp_path: Path) -> None:
	"""The should-fail witness, part 1: one line past ``INT_MAX_RUN`` fails.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_file = tmp_path / "probe.sh"
	list_lines = ["# filler"] * (gate.INT_MAX_RUN + 1)
	path_file.write_text("\n".join(list_lines) + "\n", encoding="utf-8")
	list_problems = gate.file_problems(path_file)
	assert len(list_problems) == 1


def test_the_same_run_passes_with_a_pragma_in_the_middle(tmp_path: Path) -> None:
	"""The should-fail witness, part 2: a ``# noqa`` in the middle breaks the run.

	Same total line count as the failing case above — the only difference is
	one pragma line splitting it into two runs, each under the ceiling.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_file = tmp_path / "probe.sh"
	int_half = gate.INT_MAX_RUN // 2
	list_lines = ["# filler"] * int_half + ["# noqa"] + ["# filler"] * int_half
	path_file.write_text("\n".join(list_lines) + "\n", encoding="utf-8")
	assert gate.file_problems(path_file) == []


def test_a_qa_pragma_line_is_never_itself_a_finding(tmp_path: Path) -> None:
	"""A lone suppression pragma, nowhere near the ceiling, is clean.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_file = tmp_path / "probe.sh"
	path_file.write_text("# noqa\necho hi\n", encoding="utf-8")
	assert gate.file_problems(path_file) == []


# --------------------------
# The escape hatch — mirrors this repo's other gate escape-hatch markers
# --------------------------


def test_the_escape_hatch_exempts_a_flagged_block() -> None:
	"""``# comment-budget-ok: <reason>`` anywhere in the block exempts it."""
	list_lines = ["filler"] * (gate.INT_MAX_RUN + 1)
	list_lines[0] = " comment-budget-ok: pinned oracle, see docs/decisions/x.md"
	assert gate.has_valid_escape(list_lines) is True


def test_a_bare_escape_marker_with_no_reason_does_not_exempt() -> None:
	"""A marker with nothing after the colon is rejected, like `# complexity-ok:`."""
	assert gate.has_valid_escape([" comment-budget-ok:"]) is False


def test_the_escape_hatch_exempts_a_real_oversized_block(tmp_path: Path) -> None:
	"""A valid marker inside a real over-ceiling block exempts the whole file.

	Should-fail witness for blueprintx#303's own follow-up defect: the marker's
	text must NOT be in ``comment_budget_allowlist.txt``, because a pragma line
	BREAKS a run (``line_breaks_run``) before ``has_valid_escape`` ever sees it —
	so a listed escape hatch could never exempt the block it opens.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_file = tmp_path / "probe.sh"
	list_lines = ["# comment-budget-ok: pinned oracle, see docs/decisions/x.md"]
	list_lines += ["# filler"] * (gate.INT_MAX_RUN + 1)
	path_file.write_text("\n".join(list_lines) + "\n", encoding="utf-8")
	assert gate.file_problems(path_file) == []


def test_a_bare_marker_inside_a_real_oversized_block_still_fails(tmp_path: Path) -> None:
	"""A reasonless marker mid-block must not silently split or exempt the run.

	Same defect from the other side: if the marker were still in the allowlist
	it would BREAK the run in two, each half under the ceiling, so a bare
	marker with no reason would silently pass — exactly the bypass
	``has_valid_escape`` exists to reject.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_file = tmp_path / "probe.sh"
	list_lines = ["# filler"] * (gate.INT_MAX_RUN + 1)
	list_lines.insert(len(list_lines) // 2, "# comment-budget-ok:")
	path_file.write_text("\n".join(list_lines) + "\n", encoding="utf-8")
	assert len(gate.file_problems(path_file)) == 1


# --------------------------
# Pragma lines break a run, they never extend it
# --------------------------


def test_a_pragma_line_splits_one_block_into_two() -> None:
	"""Two five-line blocks separated by one pragma are two findings, not one."""
	list_lines = ["# a"] * 5 + ["# noqa"] + ["# b"] * 5
	list_blocks = gate.marker_blocks("\n".join(list_lines), "#")
	assert len(list_blocks) == 2


def test_a_hash_inside_a_python_string_literal_is_not_a_comment() -> None:
	"""``tokenize`` tells a real comment apart from a `#` inside a string."""
	assert gate.python_blocks('x = "# not a comment # not a comment"\n') == []


def test_python_docstrings_are_excluded_from_the_budget(tmp_path: Path) -> None:
	"""A long NumPy docstring is documentation, not the comment volume bounded here.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_file = tmp_path / "probe.py"
	list_docstring_lines = ["    line"] * (gate.INT_MAX_RUN + 1)
	str_source = 'def f() -> None:\n    """\n' + "\n".join(list_docstring_lines) + '\n    """\n'
	path_file.write_text(str_source, encoding="utf-8")
	assert gate.file_problems(path_file) == []


# --------------------------
# The decorative banner — regex-decidable, no ratchet
# --------------------------


def test_a_decorative_banner_triple_is_flagged() -> None:
	"""A rule / title / rule sandwich is the Makefile's own measured shape."""
	list_findings = gate.banner_findings(1, [" -------", " LINTING", " -------"])
	assert list_findings == [(1, 3)]


def test_a_lone_punctuation_line_is_flagged_as_a_banner() -> None:
	"""A single punctuation-only line, not sandwiching anything, is still a defect."""
	list_findings = gate.banner_findings(1, ["hello", " ----", "world"])
	assert list_findings == [(2, 1)]


def test_a_banner_rule_with_no_closing_rule_is_not_a_triple() -> None:
	"""One rule line with ordinary prose after it is a lone banner, not a sandwich."""
	list_findings = gate.banner_findings(1, [" -------", " a real sentence"])
	assert list_findings == [(1, 1)]


def test_a_section_title_alone_is_not_a_banner() -> None:
	"""Ordinary prose between two non-banner lines is never flagged."""
	assert gate.banner_findings(1, ["a", "b", "c"]) == []


def test_is_exempt_section_banner_matches_the_full_triple_only() -> None:
	"""Only the exact mandated triple is exempt — a shorter rule is not."""
	list_lines = [" --------------------------", " Tests", " --------------------------"]
	assert gate.is_exempt_section_banner(list_lines, 0) is True
	assert gate.is_exempt_section_banner([" -------", " LINTING", " -------"], 0) is False


# --------------------------
# Structural exemptions — positional, not textual
# --------------------------


def test_a_shebang_line_is_structurally_exempt() -> None:
	"""Line 1's ``#!`` never counts toward a run."""
	assert gate.line_breaks_run(1, "#!/usr/bin/env bash", "!/usr/bin/env bash", ()) is True


def test_an_encoding_declaration_is_structurally_exempt() -> None:
	"""A PEP 263 encoding declaration on line 2 is metadata, not prose."""
	assert gate.line_breaks_run(2, "# -*- coding: utf-8 -*-", " -*- coding: utf-8 -*-", ()) is True


def test_a_shebang_shaped_line_deeper_in_the_file_is_not_exempt() -> None:
	"""The same text past line 2 is ordinary prose — position, not content, decides."""
	assert gate.line_breaks_run(3, "#!/usr/bin/env bash", "!/usr/bin/env bash", ()) is False


# --------------------------
# File-type discovery — extensionless Makefile is the issue's own worked example
# --------------------------


def test_marker_for_recognizes_makefile_by_name() -> None:
	"""``Makefile`` has no suffix, so it must be matched on its exact name."""
	assert gate.marker_for(Path("Makefile")) == "#"


def test_marker_for_recognizes_mk_suffix() -> None:
	"""A ``*.mk`` include file gets the same ``#`` marker."""
	assert gate.marker_for(Path("common.mk")) == "#"


def test_marker_for_recognizes_typescript_suffixes() -> None:
	"""TypeScript files use ``//``, not ``#``."""
	assert gate.marker_for(Path("app.tsx")) == "//"


def test_marker_for_rejects_an_unsupported_extension() -> None:
	"""A binary or otherwise unlisted extension is not budgeted at all."""
	assert gate.marker_for(Path("image.png")) == ""


def test_marker_for_recognizes_python_files() -> None:
	"""``.py`` gets a marker too, even though its blocks are extracted elsewhere.

	``.py`` is deliberately absent from ``DICT_HASH_SUFFIXES`` (its blocks are
	extracted via ``tokenize`` instead) but ``marker_for`` must still return a
	marker for it — should-fail witness for blueprintx#466: without this,
	``file_problems`` returns ``[]`` for every ``.py`` file before ever reaching
	the ``python_blocks`` branch, so ``audit_paths`` reports files "checked"
	that were never actually inspected.
	"""
	assert gate.marker_for(Path("probe.py")) == "#"


def test_audit_discovers_an_extensionless_makefile(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""``audit_paths`` must find ``Makefile`` even though ``rglob("*Makefile")`` would not.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	monkeypatch : pytest.MonkeyPatch
		Used to point the gate's discovery root at ``tmp_path``.
	"""
	(tmp_path / "Makefile").write_text("build:\n\techo hi\n", encoding="utf-8")
	monkeypatch.setattr(gate, "PATH_ROOT", tmp_path)
	assert tmp_path / "Makefile" in gate.audit_paths()


# --------------------------
# Python files are actually checked (blueprintx#466)
# --------------------------


def test_a_python_file_with_a_decorative_banner_is_flagged(tmp_path: Path) -> None:
	"""Should-fail witness: a ``.py`` file's own banner defect must surface.

	Before blueprintx#466, ``marker_for`` never recognized ``.py``, so
	``file_problems`` returned ``[]`` for every Python file regardless of
	content — this is the case that must now fail.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_file = tmp_path / "probe.py"
	str_source = "# -------\n# LINTING\n# -------\ndef f() -> None:\n\tpass\n"
	path_file.write_text(str_source, encoding="utf-8")
	assert len(gate.file_problems(path_file)) == 1


def test_a_python_file_with_an_oversized_comment_run_is_flagged(tmp_path: Path) -> None:
	"""Should-fail witness: a ``.py`` file's long-run defect must surface too.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_file = tmp_path / "probe.py"
	list_lines = ["# filler"] * (gate.INT_MAX_RUN + 1)
	path_file.write_text("\n".join(list_lines) + "\ndef f() -> None:\n\tpass\n", encoding="utf-8")
	assert len(gate.file_problems(path_file)) == 1


def test_the_mandated_test_section_banner_is_exempt(tmp_path: Path) -> None:
	"""``tests/CLAUDE.md``'s rule/title/rule test-section banner is not a finding.

	This is the shape ``tests/CLAUDE.md`` mandates for structuring every test
	module in this repo (272 occurrences across 31 files, measured). It is not
	the essay/decorative-banner defect this gate polices — see
	``is_exempt_section_banner`` for the reasoning — so once ``.py`` files
	are actually checked (the fix above), this exact convention must stay clean.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_dir = tmp_path / "tests"
	path_dir.mkdir()
	path_file = path_dir / "probe.py"
	str_source = (
		"# --------------------------\n"
		"# Tests\n"
		"# --------------------------\n"
		"def test_something() -> None:\n"
		"\tassert True\n"
	)
	path_file.write_text(str_source, encoding="utf-8")
	assert gate.file_problems(path_file) == []


def test_a_test_module_outside_a_tests_dir_is_still_exempt(tmp_path: Path) -> None:
	"""Scoping the exemption by directory alone was measured wrong.

	``templates/*/optional/multi_pipeline/test_pipeline.py`` are real test
	modules shipped outside any ``tests/`` tree. A directory-only rule flagged
	6 mandated banners across those four files, so ``is_test_module`` follows
	pytest's own discovery convention and accepts the ``test_`` filename
	prefix too (blueprintx#479).

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_dir = tmp_path / "optional" / "multi_pipeline"
	path_dir.mkdir(parents=True)
	path_file = path_dir / "test_pipeline.py"
	str_source = (
		"# --------------------------\n"
		"# Tests\n"
		"# --------------------------\n"
		"def test_something() -> None:\n"
		"\tassert True\n"
	)
	path_file.write_text(str_source, encoding="utf-8")
	assert gate.file_problems(path_file) == []


def test_a_production_python_file_gets_no_section_banner_exemption(
	tmp_path: Path,
) -> None:
	"""The exemption is scoped to test modules, not to every ``.py`` file.

	``tests/CLAUDE.md`` mandates the rule/title/rule triple for structuring
	TEST modules. The same three lines in a production ``.py`` are the plain
	decorative banner this gate exists to police, so the exemption must not
	reach them — see ``is_test_module`` (blueprintx#479).

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_dir = tmp_path / "src"
	path_dir.mkdir()
	path_file = path_dir / "service.py"
	str_source = (
		"# --------------------------\n"
		"# Helpers\n"
		"# --------------------------\n"
		"def run() -> None:\n"
		"\treturn None\n"
	)
	path_file.write_text(str_source, encoding="utf-8")
	list_problems = gate.file_problems(path_file)
	assert len(list_problems) == 1
	assert "decorative banner (rule/title/rule)" in list_problems[0]


def test_a_non_python_file_gets_no_section_banner_exemption(tmp_path: Path) -> None:
	"""A shell file under ``tests/`` carrying the triple is still a banner.

	Guards the other half of the scope: ``is_test_module`` requires BOTH a
	``.py`` suffix and a ``tests`` path segment, so living under ``tests/`` is
	not on its own enough to earn the exemption. The convention was measured
	(blueprintx#466) to occur only in ``.py`` files.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_dir = tmp_path / "tests"
	path_dir.mkdir()
	path_file = path_dir / "probe.sh"
	str_source = (
		"#!/bin/bash\n"
		"# --------------------------\n"
		"# Fixtures\n"
		"# --------------------------\n"
		"echo hi\n"
	)
	path_file.write_text(str_source, encoding="utf-8")
	list_problems = gate.file_problems(path_file)
	assert len(list_problems) == 1
	assert "decorative banner (rule/title/rule)" in list_problems[0]


def test_the_exempt_banner_does_not_split_an_oversized_run(tmp_path: Path) -> None:
	"""Should-fail witness for blueprintx#479: the exemption must not be a pragma.

	``comment_budget_allowlist.txt`` is read by ``is_pragma_line``, and
	``line_breaks_run`` makes a pragma BREAK the current run — correct for a
	QA suppression, wrong for a banner: listing the test-section rule line
	there let one dash line split an 89-line block into two 44-line halves,
	each under ``INT_MAX_RUN``, so the whole file passed clean. A lone rule
	line (no title, no closing rule after it) is not the exempt triple, so it
	must both stay IN the run's line count and be flagged as its own
	decorative banner.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_file = tmp_path / "probe.py"
	list_lines = ["# filler"] * 44 + ["# --------------------------"] + ["# filler"] * 44
	path_file.write_text("\n".join(list_lines) + "\n", encoding="utf-8")
	list_problems = gate.file_problems(path_file)
	assert len(list_problems) == 2
	assert any("89 lines" in str_problem for str_problem in list_problems)
	assert any("decorative banner" in str_problem for str_problem in list_problems)


def test_the_exempt_triple_still_counts_toward_an_oversized_run(tmp_path: Path) -> None:
	"""The exemption suppresses the BANNER finding, never the run-length one.

	A full, valid section-banner triple wrapped inside an otherwise-oversized
	block must not disappear from the run's line count — only the triple
	itself must go unreported as a banner.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_dir = tmp_path / "tests"
	path_dir.mkdir()
	path_file = path_dir / "probe.py"
	list_lines = (
		["# filler"] * 44
		+ ["# --------------------------", "# Tests", "# --------------------------"]
		+ ["# filler"] * 44
	)
	path_file.write_text("\n".join(list_lines) + "\n", encoding="utf-8")
	list_problems = gate.file_problems(path_file)
	assert len(list_problems) == 1
	assert "91 lines" in list_problems[0]


# --------------------------
# Zero-discovery guard and the success message
# --------------------------


def test_audit_mode_fails_when_no_file_matches(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
	"""A gate that scans nothing must report failure, never a silent pass.

	Parameters
	----------
	tmp_path : pathlib.Path
		An empty throwaway directory — nothing here matches any supported type.
	monkeypatch : pytest.MonkeyPatch
		Used to point the gate's discovery root at ``tmp_path``.
	capsys : pytest.CaptureFixture
		Captures the printed diagnostic.
	"""
	monkeypatch.setattr(gate, "PATH_ROOT", tmp_path)
	assert gate.main([]) == 1


def test_a_clean_tree_reports_the_file_count_on_success(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
	"""A silent gate is indistinguishable from one that never ran — print the count.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory holding one clean file.
	monkeypatch : pytest.MonkeyPatch
		Used to point the gate's discovery root at ``tmp_path``.
	capsys : pytest.CaptureFixture
		Captures the printed success line.
	"""
	(tmp_path / "clean.sh").write_text("#!/bin/bash\necho hi\n", encoding="utf-8")
	monkeypatch.setattr(gate, "PATH_ROOT", tmp_path)
	gate.main([])
	assert "✅ comment budget OK (1 file" in capsys.readouterr().out
