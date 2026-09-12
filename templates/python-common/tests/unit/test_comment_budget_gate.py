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
# The escape hatch — mirrors `# complexity-ok:`
# --------------------------


def test_the_escape_hatch_exempts_a_flagged_block() -> None:
	"""``# comment-budget-ok: <reason>`` anywhere in the block exempts it."""
	list_lines = ["filler"] * (gate.INT_MAX_RUN + 1)
	list_lines[0] = " comment-budget-ok: pinned oracle, see docs/decisions/x.md"
	assert gate.has_valid_escape(list_lines) is True


def test_a_bare_escape_marker_with_no_reason_does_not_exempt() -> None:
	"""A marker with nothing after the colon is rejected, like `# complexity-ok:`."""
	assert gate.has_valid_escape([" comment-budget-ok:"]) is False


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
