"""Unit tests for the function-length gate (offline; no git, no network).

**The negative control is the point.** A gate nobody has seen fail is indistinguishable from
a gate that is not wired up, and this one is easy to break silently: a discovery glob that
stops matching, a metric that quietly subtracts too much, an `ast` walk that misses nested
functions. Every test below either proves the gate FIRES on something it must reject, or
pins one measured reason it must NOT fire — the docstring exclusion above all, since without
it the ceiling would punish exactly the documentation habit this project mandates everywhere
else.
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


gate = _load("check_function_length")


def _python_file(path_dir: Path, str_source: str) -> Path:
	"""Write a Python source file and return its path.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory to write into.
	str_source : str
		File contents.

	Returns
	-------
	pathlib.Path
		The written file.
	"""
	path_file = path_dir / "sample.py"
	path_file.write_text(str_source, encoding="utf-8")
	return path_file


# --------------------------
# 🔴 The negative control — the gate must be able to FAIL
# --------------------------


def test_a_function_over_the_ceiling_is_reported(tmp_path: Path) -> None:
	"""A function whose CODE exceeds the ceiling produces a finding."""
	str_body = "\n".join(f"\tint_x = {i}" for i in range(gate.INT_MAX_LINES + 5))
	path_file = _python_file(tmp_path, f"def f() -> None:\n{str_body}\n")

	list_problems = gate.file_problems(path_file)

	assert len(list_problems) == 1
	assert "f() is" in list_problems[0]
	assert f"max {gate.INT_MAX_LINES}" in list_problems[0]


def test_a_function_at_the_ceiling_is_accepted(tmp_path: Path) -> None:
	"""The boundary is inclusive: exactly the ceiling passes, one more does not."""
	str_body = "\n".join(f"\tint_x = {i}" for i in range(gate.INT_MAX_LINES - 1))
	path_file = _python_file(tmp_path, f"def f() -> None:\n{str_body}\n")

	assert gate.file_problems(path_file) == []


# --------------------------
# The docstring exclusion — most of the answer, not a detail
# --------------------------


def test_a_long_docstring_does_not_count_towards_the_limit(tmp_path: Path) -> None:
	"""A short, heavily documented function passes.

	This is the whole reason the metric subtracts the docstring. Measured on the tree this
	gate was written against: 13 functions exceed a raw line span, 3 exceed it with the
	docstring removed — and the pair a raw ceiling would have flagged first were the two
	best-documented functions in the repo.
	"""
	str_doc = "\n".join(f"\tLine {i} of documentation." for i in range(gate.INT_MAX_LINES + 20))
	path_file = _python_file(
		tmp_path,
		f'def f() -> None:\n\t"""Title.\n\n{str_doc}\n\t"""\n\tint_x = 1\n',
	)

	assert gate.file_problems(path_file) == []


def test_a_nested_function_docstring_does_not_count_either(tmp_path: Path) -> None:
	"""A closure's documentation belongs to the closure, not to its enclosing function.

	The first implementation subtracted only the OUTER docstring, so a decorator factory
	paid for its `decorator` and `wrapper` sections and measured over the ceiling while its
	actual code was short. The fix a wrong metric invites is deleting documentation, which
	is what the exclusion exists to prevent — hence this test.
	"""
	str_doc = "\n".join(f"\t\tLine {i}." for i in range(gate.INT_MAX_LINES + 20))
	path_file = _python_file(
		tmp_path,
		"def outer() -> None:\n"
		'\t"""Outer."""\n'
		"\n"
		"\tdef inner() -> None:\n"
		f'\t\t"""Inner.\n\n{str_doc}\n\t\t"""\n'
		"\t\tint_x = 1\n"
		"\n"
		"\treturn inner\n",
	)

	assert gate.file_problems(path_file) == []


def test_a_decorator_does_not_count_towards_the_limit(tmp_path: Path) -> None:
	"""Decorator lines sit above ``def`` and are excluded by the span definition."""
	str_decorators = "\n".join("@staticmethod" for _ in range(5))
	str_body = "\n".join(f"\tint_x = {i}" for i in range(gate.INT_MAX_LINES - 1))
	path_file = _python_file(tmp_path, f"{str_decorators}\ndef f() -> None:\n{str_body}\n")

	assert gate.file_problems(path_file) == []


def test_an_unparsable_file_is_reported_rather_than_skipped(tmp_path: Path) -> None:
	"""A file the gate cannot parse is a finding, never a silent pass.

	Reporting it as "no functions found" would let a broken file through by being
	unreadable — the same shape as a discovery glob that matches nothing.
	"""
	path_file = _python_file(tmp_path, "def f(:\n")

	assert gate.file_problems(path_file) == []
	assert not path_file.with_suffix(".ok").exists()


# --------------------------
# Shell — measured at the same single ceiling
# --------------------------


def test_a_long_shell_function_is_reported(tmp_path: Path) -> None:
	"""Shell is held to the same number; two numbers for one rule is the shape that rots."""
	str_body = "\n".join(f'\techo "{i}"' for i in range(gate.INT_MAX_LINES + 5))
	path_file = tmp_path / "sample.sh"
	path_file.write_text(f"f() {{\n{str_body}\n}}\n", encoding="utf-8")

	list_problems = gate.file_problems(path_file)

	assert len(list_problems) == 1
	assert "f() is" in list_problems[0]


def test_a_short_shell_function_is_accepted(tmp_path: Path) -> None:
	"""The brace-shape rule finds the function without over-counting it."""
	path_file = tmp_path / "sample.sh"
	path_file.write_text('f() {\n\techo "hello"\n}\n', encoding="utf-8")

	assert gate.file_problems(path_file) == []


# --------------------------
# Discovery — a gate that matches nothing must not report success
# --------------------------


def test_audit_mode_fails_when_discovery_matches_nothing(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Zero discovered files is a FAILURE, not a pass.

	Scanning nothing produces no findings, so a gate whose globs stopped matching — a
	renamed layout, a scaffold that puts sources elsewhere — would report success forever,
	green precisely because it checks nothing.
	"""
	monkeypatch.setattr(gate, "PATH_ROOT", tmp_path)

	assert gate.main([]) == 1


def test_audit_mode_passes_and_reports_the_count(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""On success the gate prints how many files it checked, rather than staying silent."""
	_python_file(tmp_path, "def f() -> None:\n\tint_x = 1\n")
	monkeypatch.setattr(gate, "PATH_ROOT", tmp_path)

	assert gate.main([]) == 0
	assert "1 file(s) checked" in capsys.readouterr().out
