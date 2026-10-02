"""Unit tests for the dead-code gate (``bin/check_dead_code.py``, blueprintx#332).

Two should-fail/should-pass pairs carry the whole point of the issue this gate answers:

- ``test_provable_dead_parameter_at_gate_confidence_fails`` / the 60-79% counterpart below
  prove the CLIFF is real and enforced, not merely observed in the issue's own measurement —
  a provable, unused function parameter fails the build; a shipped-but-uncalled function
  (the ``mask_cnpj`` shape the issue names explicitly) is reported, never gated.
- ``test_discover_python_files_ignores_skip_dir_named_ancestor`` pins a regression found
  WHILE writing this gate: the first draft filtered on ``path_file.parts`` (every ANCESTOR
  component, following ``check_coverage_floor.py``'s docstring pattern rather than
  ``check_function_length.py``'s ``TUPLE_SKIP_DIRS`` fix) and reported "found ZERO .py files"
  against the template's own 43-file ``src/`` tree — self-inflicted, because this repo's own
  worktrees live under ``.claude/worktrees/agent-*`` and every ancestor then contains
  ``.claude``, matching the skip list on every single file (blueprintx#331, the exact failure
  this test now pins so it cannot regress silently a second time).
"""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _load_gate() -> ModuleType:
	"""Import ``bin/check_dead_code.py`` as a module.

	Returns
	-------
	ModuleType
		The loaded gate module.
	"""
	path_gate = Path(__file__).resolve().parents[2] / "bin" / "check_dead_code.py"
	cls_spec = importlib.util.spec_from_file_location("_check_dead_code", path_gate)
	assert cls_spec is not None
	assert cls_spec.loader is not None
	cls_module = importlib.util.module_from_spec(cls_spec)
	cls_spec.loader.exec_module(cls_module)
	return cls_module


def _write_module(path_root: Path, str_rel_path: str, str_source: str) -> None:
	"""Write ``str_source`` to ``path_root / str_rel_path``, creating parent dirs.

	Parameters
	----------
	path_root : pathlib.Path
		The project root built by the test.
	str_rel_path : str
		Path relative to ``path_root``, e.g. ``"src/utils/thing.py"``.
	str_source : str
		The module's Python source.
	"""
	path_module = path_root / str_rel_path
	path_module.parent.mkdir(parents=True, exist_ok=True)
	path_module.write_text(str_source, encoding="utf-8")


def test_no_src_dir_is_a_legitimate_skip(tmp_path: Path) -> None:
	"""A tier shipping no ``src/`` (BlueprintX's own root) must pass, not fail."""
	assert _load_gate().main(["--root", str(tmp_path)]) == 0


def test_empty_src_dir_is_broken_discovery_fails(tmp_path: Path) -> None:
	"""``src/`` existing but holding zero ``.py`` files is broken discovery, not a clean slate."""
	(tmp_path / "src").mkdir()
	assert _load_gate().main(["--root", str(tmp_path)]) == 1


def test_root_flag_missing_value_fails(tmp_path: Path) -> None:
	"""``--root`` with no directory argument must fail, never silently scan the cwd."""
	assert _load_gate().main(["--root"]) == 1


def test_vulture_absent_is_a_legitimate_skip(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Not-yet-wired ``vulture`` is an expected skip, not broken discovery (blueprintx#332)."""
	_write_module(tmp_path, "src/thing.py", "def used():\n    return 1\n")
	cls_gate = _load_gate()
	monkeypatch.setattr(cls_gate, "resolve_vulture", lambda: None)
	assert cls_gate.main(["--root", str(tmp_path)]) == 0


def test_provable_dead_parameter_at_gate_confidence_fails(
	tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
	"""The should-fail witness: an unused function parameter is 100% confidence and gates.

	The exact shape the real measurement caught live in a generated project (``str_title``
	on ``app/bootstrap.py``'s ``routine_conclusion`` helper) — provable from the file alone,
	unlike a bare unused local, which vulture itself scores only 60% (contextual, not gating).
	"""
	_write_module(
		tmp_path,
		"src/thing.py",
		"def compute(unused_arg: int) -> int:\n    return 2\n",
	)
	assert _load_gate().main(["--root", str(tmp_path)]) == 1
	str_err = capsys.readouterr().err
	assert "unused_arg" in str_err
	assert ">=80% confidence" in str_err


def test_shipped_but_uncalled_function_does_not_gate(
	tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
	"""The mirror witness: a function nothing calls YET is 60% confidence and must NOT gate.

	This is ``mask_cnpj``'s exact shape (blueprintx#332) — a deliberately-shipped seam with no
	caller yet, which is the entire point of a template. Gating it would be the false positive
	the issue measured 63 of on the real template.
	"""
	_write_module(
		tmp_path,
		"src/thing.py",
		"def uncalled_seam() -> int:\n    return 1\n",
	)
	assert _load_gate().main(["--root", str(tmp_path)]) == 0
	assert "uncalled_seam" in capsys.readouterr().out


def test_discover_python_files_ignores_skip_dir_named_ancestor(tmp_path: Path) -> None:
	"""A skip-dir NAME sitting in an ANCESTOR of ``src/`` must not empty the discovered set.

	Regression pin for blueprintx#331 as it recurred while writing THIS gate: comparing
	``path_file.parts`` (every ancestor) rather than parts relative to ``path_src`` means any
	root living under ``.claude/worktrees/agent-*`` — this repo's own parallel-agent layout —
	reports zero files on its own, real, 43-file tree.
	"""
	path_root = tmp_path / ".claude" / "worktrees" / "agent-x" / "proj"
	_write_module(path_root, "src/thing.py", "def f() -> int:\n    return 1\n")
	cls_gate = _load_gate()

	list_files = cls_gate.discover_python_files(path_root / "src")

	assert len(list_files) == 1


def test_discover_python_files_skips_vendored_dir_inside_src(tmp_path: Path) -> None:
	"""A genuine vendored/cache dir NESTED INSIDE ``src/`` is still excluded."""
	_write_module(tmp_path, "src/thing.py", "def f() -> int:\n    return 1\n")
	_write_module(tmp_path, "src/__pycache__/thing.cpython-312.pyc.py", "garbage = 1\n")
	cls_gate = _load_gate()

	list_files = cls_gate.discover_python_files(tmp_path / "src")

	assert list_files == [tmp_path / "src" / "thing.py"]


def test_classify_findings_splits_on_gate_threshold() -> None:
	"""Items are bucketed strictly by the >=80% boundary, never by any other cutoff."""
	cls_gate = _load_gate()
	# Duck-typed stand-ins for vulture's Item, down to the one field this function reads.
	# Written as a flat literal, never a comprehension, to stay under the tests/ complexity
	# ceiling of one.
	list_items = [
		SimpleNamespace(confidence=60),
		SimpleNamespace(confidence=79),
		SimpleNamespace(confidence=80),
		SimpleNamespace(confidence=100),
	]

	list_gate, list_report = cls_gate.classify_findings(list_items)

	assert (list_gate[0].confidence, list_gate[1].confidence) == (80, 100)
	assert (list_report[0].confidence, list_report[1].confidence) == (60, 79)
