"""Unit tests for the one-assert gate (offline; no git, no network — blueprintx#431).

**The negative control is the point.** A gate claiming to catch a test with zero assertion
sites is worthless unless something in this suite actually fails it. Every test below either
proves the zero-assertion rule FIRES on the shape it targets, or pins a measured reason it must
NOT fire — including the core differentiator from the issue's original "cap every test at one
assert" ask: with no ``--max-per-test`` flag, a legitimate multi-facet test with several
assertion sites is clean, matching ``tests/CLAUDE.md``'s "one behaviour, not one assert" rule
(blueprintx#429) rather than reproducing its measured 27% false-positive rate.
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


gate = _load("check_one_assert")


def _write_test_file(path_root: Path, str_content: str) -> None:
	"""Write one fixture test file under ``<path_root>/tests/test_sample.py``.

	Parameters
	----------
	path_root : pathlib.Path
		The fixture tree root.
	str_content : str
		The fixture file's full source text.
	"""
	path_tests = path_root / "tests"
	path_tests.mkdir(parents=True, exist_ok=True)
	(path_tests / "test_sample.py").write_text(str_content, encoding="utf-8")


def _run(path_root: Path, list_extra_args: list[str]) -> int:
	"""Run the gate's ``main()`` against a fixture root.

	Parameters
	----------
	path_root : pathlib.Path
		The fixture tree root.
	list_extra_args : list of str
		Extra argv tokens after ``--root <path_root>``.

	Returns
	-------
	int
		The gate's exit code.
	"""
	return gate.main(["--root", str(path_root), *list_extra_args])


# --------------------------
# The core defect — a test with zero assertion sites
# --------------------------


def test_a_zero_assertion_test_is_flagged(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
	"""A ``test_*`` function with no assert, call, or raises/warns block is a finding."""
	_write_test_file(tmp_path, "def test_x() -> None:\n\tpass\n")

	int_code = _run(tmp_path, [])

	str_err = capsys.readouterr().err
	assert int_code == 1
	assert "test_x" in str_err
	assert "asserts nothing" in str_err


def test_a_single_bare_assert_is_clean(tmp_path: Path) -> None:
	"""One ``assert`` statement is the ordinary, unflagged case."""
	_write_test_file(tmp_path, "def test_x() -> None:\n\tassert 1 == 1\n")

	assert _run(tmp_path, []) == 0


# --------------------------
# raises/warns count as one site, never zero
# --------------------------


def test_pytest_raises_counts_as_one_assertion_site(tmp_path: Path) -> None:
	"""A ``pytest.raises`` context manager is the check — not an assertion-less test."""
	_write_test_file(
		tmp_path, "def test_x() -> None:\n\twith pytest.raises(ValueError):\n\t\tf()\n"
	)

	assert _run(tmp_path, []) == 0


def test_pytest_warns_counts_as_one_assertion_site(tmp_path: Path) -> None:
	"""A ``pytest.warns`` context manager is likewise a real assertion site."""
	_write_test_file(
		tmp_path, "def test_x() -> None:\n\twith pytest.warns(UserWarning):\n\t\tf()\n"
	)

	assert _run(tmp_path, []) == 0


def test_a_pandas_or_mock_style_assert_call_counts_as_one_site(tmp_path: Path) -> None:
	"""``mock.assert_called_once()`` / ``pd.testing.assert_frame_equal(...)`` both count."""
	_write_test_file(tmp_path, "def test_x() -> None:\n\tmock_obj.assert_called_once()\n")

	assert _run(tmp_path, []) == 0


# --------------------------
# The core differentiator: no cap by default (tests/CLAUDE.md, blueprintx#429)
# --------------------------


def test_two_assertion_sites_with_no_cap_flag_is_clean(tmp_path: Path) -> None:
	"""Default mode never blocks a legitimate multi-facet test.

	Two assertions pinning one behaviour (a value and its dtype) must stay clean with no
	flag passed — reproducing blueprintx#431's original "cap every test" ask here would
	contradict tests/CLAUDE.md's measured 27% multi-assert rate (blueprintx#429).
	"""
	_write_test_file(
		tmp_path,
		"def test_x() -> None:\n\tassert compute() == 5\n\tassert compute().dtype == int\n",
	)

	assert _run(tmp_path, []) == 0


# --------------------------
# The opt-in --max-per-test cap
# --------------------------


def test_two_assertion_sites_over_an_explicit_cap_is_flagged(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
	"""With ``--max-per-test`` explicitly passed, exceeding it is a finding."""
	_write_test_file(tmp_path, "def test_x() -> None:\n\tassert 1 == 1\n\tassert 2 == 2\n")

	int_code = _run(tmp_path, ["--max-per-test", "1"])

	str_err = capsys.readouterr().err
	assert int_code == 1
	assert "test_x" in str_err
	assert "2 assertion sites" in str_err


def test_a_non_integer_max_per_test_value_is_rejected(tmp_path: Path) -> None:
	"""Bad usage is refused, not silently coerced or ignored."""
	assert _run(tmp_path, ["--max-per-test", "not-a-number"]) == 1


# --------------------------
# The escape hatch — reason required
# --------------------------


def test_a_justified_multi_assert_test_is_exempted_by_the_hatch(tmp_path: Path) -> None:
	"""``# one-assert-ok: <reason>`` clears a cap violation."""
	_write_test_file(
		tmp_path,
		"def test_x() -> None:\n\tassert 1 == 1\n"
		"\tassert 2 == 2  # one-assert-ok: value and dtype\n",
	)

	assert _run(tmp_path, ["--max-per-test", "1"]) == 0


def test_a_bare_hatch_marker_with_no_reason_does_not_exempt(tmp_path: Path) -> None:
	"""The reason is REQUIRED, matching ``# complexity-ok:``'s convention."""
	_write_test_file(
		tmp_path, "def test_x() -> None:\n\tassert 1 == 1\n\tassert 2 == 2  # one-assert-ok:\n"
	)

	assert _run(tmp_path, ["--max-per-test", "1"]) == 1


def test_the_hatch_also_exempts_a_zero_assertion_test(tmp_path: Path) -> None:
	"""The same hatch covers the zero-assertion default check, not only the opt-in cap."""
	_write_test_file(tmp_path, "def test_x() -> None:\n\tpass  # one-assert-ok: smoke test\n")

	assert _run(tmp_path, []) == 0


# --------------------------
# Three states: flagged / clean / could not parse
# --------------------------


def test_an_unparsable_file_is_a_finding_not_a_silent_skip(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
	"""A file the gate cannot parse must FAIL, never read as clean."""
	_write_test_file(tmp_path, "def test_x(:\n")

	int_code = _run(tmp_path, [])

	str_err = capsys.readouterr().err
	assert int_code == 1
	assert "not valid Python" in str_err
	assert "not checked" in str_err


# --------------------------
# Discovery: legitimate skip vs. broken discovery
# --------------------------


def test_no_tests_directory_is_a_legitimate_skip(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
	"""A tree with no ``tests/`` at all (like this repo's own root) is a real skip."""
	int_code = _run(tmp_path, [])

	str_out = capsys.readouterr().out
	assert int_code == 0
	assert "no tests/ directory" in str_out


def test_a_tests_dir_with_zero_matching_files_is_a_failure_not_a_skip(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
	"""An empty ``tests/`` is the broken-discovery shape, not a legitimate skip."""
	(tmp_path / "tests").mkdir()

	int_code = _run(tmp_path, [])

	str_err = capsys.readouterr().err
	assert int_code == 1
	assert "0 test_*.py files" in str_err


# --------------------------
# The distribution table (the measurement half of the deliverable)
# --------------------------


def test_the_distribution_table_reports_every_count_found(tmp_path: Path) -> None:
	"""``distribution_table`` groups counts into a histogram, sorted by count."""
	str_report = gate.distribution_table([0, 1, 1, 2])

	assert "0 assertion site(s): 1 test(s)" in str_report
	assert "1 assertion site(s): 2 test(s)" in str_report
	assert "2 assertion site(s): 1 test(s)" in str_report
