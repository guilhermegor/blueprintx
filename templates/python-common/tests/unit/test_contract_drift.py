"""Unit tests for the weekly contract-drift reporter (offline; no network).

**The load-bearing test is `test_build_report_unreachable_source_is_not_reported_clean`.**
This job's whole purpose is to notice a source changing shape behind our back, and its
original failure mode was to announce an all-clear for a comparison that never happened: an
unreachable source returned the same empty list a clean comparison returns, so the summary
printed "No contract drift" after checking nothing. A reporting job that reports its own
blindness as OK is worse than no job — it converts an outage into a written assurance.

The rest pin the two asymmetric directions (a required column vanishing is always drift; an
extra source column is drift only for a contract that claims completeness) and the fact that
this driver never raises and never exits non-zero.
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


driver = _load("check_contract_drift")


# --------------------------
# Module Utilities
# --------------------------


class _Contract:
	"""Minimal stand-in for ``FileContract`` carrying only what the driver reads."""

	def __init__(
		self, tuple_required: tuple[str, ...], bool_full_column: bool, str_source_key: str
	) -> None:
		"""Store the three attributes the drift driver consults.

		Parameters
		----------
		tuple_required : tuple of str
			Columns the contract requires.
		bool_full_column : bool
			Whether the contract claims to list every column of the source.
		str_source_key : str
			The registry key this contract is pinned to.
		"""
		self.tuple_required = tuple_required
		self.bool_full_column = bool_full_column
		self.str_source_key = str_source_key


# --------------------------
# Fixtures
# --------------------------


@pytest.fixture
def dict_entry() -> dict:
	"""Return a registry entry for a single source.

	Returns
	-------
	dict
		A minimal ``{url, sep, encoding}`` entry.
	"""
	return {"url": "https://example.invalid/data.csv", "sep": ";", "encoding": "utf-8"}


# --------------------------
# Tests
# --------------------------


def test_drift_for_source_unreachable_returns_none_not_empty(
	dict_entry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""An unreachable source yields ``None``, never the ``[]`` a clean check yields.

	Parameters
	----------
	dict_entry : dict
		Registry entry fixture.
	monkeypatch : pytest.MonkeyPatch
		Used to make the fetch fail.
	"""
	monkeypatch.setattr(
		driver, "live_header", lambda _entry: (_ for _ in ()).throw(OSError("host down"))
	)
	list_lines, _ = driver.drift_for_source(_Contract(("a",), False, "k"), dict_entry)
	assert list_lines is None


def test_drift_for_source_unreachable_note_names_the_exception_type(
	dict_entry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""The note names the exception type, so "down" and "misconfigured" stay distinguishable.

	Parameters
	----------
	dict_entry : dict
		Registry entry fixture.
	monkeypatch : pytest.MonkeyPatch
		Used to make the fetch fail.
	"""
	monkeypatch.setattr(
		driver, "live_header", lambda _entry: (_ for _ in ()).throw(ValueError("bad url"))
	)
	_, list_notes = driver.drift_for_source(_Contract(("a",), False, "k"), dict_entry)
	assert "ValueError" in list_notes[0]


def test_drift_for_source_matching_header_returns_empty_list(
	dict_entry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A source that still matches yields ``[]`` — checked and clean.

	Parameters
	----------
	dict_entry : dict
		Registry entry fixture.
	monkeypatch : pytest.MonkeyPatch
		Used to pin the live header.
	"""
	monkeypatch.setattr(driver, "live_header", lambda _entry: ("a", "b"))
	list_lines, _ = driver.drift_for_source(_Contract(("a", "b"), True, "k"), dict_entry)
	assert list_lines == []


def test_drift_for_source_dropped_required_column_is_drift(
	dict_entry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A required column missing from the source is always drift — the read would raise.

	Parameters
	----------
	dict_entry : dict
		Registry entry fixture.
	monkeypatch : pytest.MonkeyPatch
		Used to pin the live header.
	"""
	monkeypatch.setattr(driver, "live_header", lambda _entry: ("a",))
	list_lines, _ = driver.drift_for_source(_Contract(("a", "b"), False, "k"), dict_entry)
	assert any("`b`" in ln for ln in list_lines)


def test_drift_for_source_extra_column_is_not_drift_on_a_subset_contract(
	dict_entry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""``tuple_required`` means "at least these", so an unlisted column is noise, not signal.

	Parameters
	----------
	dict_entry : dict
		Registry entry fixture.
	monkeypatch : pytest.MonkeyPatch
		Used to pin the live header.
	"""
	monkeypatch.setattr(driver, "live_header", lambda _entry: ("a", "b", "c"))
	list_lines, _ = driver.drift_for_source(_Contract(("a",), False, "k"), dict_entry)
	assert list_lines == []


def test_drift_for_source_extra_column_is_drift_on_a_full_column_contract(
	dict_entry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A contract claiming completeness must flag a column the source added.

	Parameters
	----------
	dict_entry : dict
		Registry entry fixture.
	monkeypatch : pytest.MonkeyPatch
		Used to pin the live header.
	"""
	monkeypatch.setattr(driver, "live_header", lambda _entry: ("a", "b"))
	list_lines, _ = driver.drift_for_source(_Contract(("a",), True, "k"), dict_entry)
	assert any("`b`" in ln for ln in list_lines)


def test_build_report_unreachable_source_is_not_reported_clean(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The unreachable key lands in ``list_skipped`` — the all-clear's only defence.

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Used to make the fetch fail.
	"""
	monkeypatch.setattr(
		driver, "live_header", lambda _entry: (_ for _ in ()).throw(OSError("down"))
	)
	dict_registry = {"k": {"url": "https://example.invalid/x.csv"}}
	_, _, list_skipped = driver.build_report(dict_registry, {"k": _Contract(("a",), False, "k")})
	assert list_skipped == ["k"]


def test_build_report_unreachable_source_stays_out_of_the_report_body(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""An outage must not open an issue — "source down" is not "contract wrong".

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Used to make the fetch fail.
	"""
	monkeypatch.setattr(
		driver, "live_header", lambda _entry: (_ for _ in ()).throw(OSError("down"))
	)
	str_report, _, _ = driver.build_report(
		{"k": {"url": "https://example.invalid/x.csv"}}, {"k": _Contract(("a",), False, "k")}
	)
	assert str_report == ""


def test_main_prints_skipped_and_never_the_all_clear(
	monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
) -> None:
	"""The negative control: a run that checked nothing must not print "No contract drift".

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Used to stub the registry, the contracts and the fetch.
	capsys : pytest.CaptureFixture
		Captures the driver's summary output.
	tmp_path : pathlib.Path
		Redirects the written report away from the repo.
	"""
	monkeypatch.setattr(driver, "_REPORT_PATH", tmp_path / "report.md")
	monkeypatch.setattr(
		driver, "load_registry", lambda: {"k": {"url": "https://example.invalid/x.csv"}}
	)
	monkeypatch.setattr(
		driver, "contracts_by_source_key", lambda: {"k": _Contract(("a",), False, "k")}
	)
	monkeypatch.setattr(
		driver, "live_header", lambda _entry: (_ for _ in ()).throw(OSError("down"))
	)
	driver.main()
	assert "No contract drift" not in capsys.readouterr().out


def test_main_returns_zero_even_when_every_source_is_unreachable(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
	"""A reporter never reddens the job — an outage and a wrong contract must not look alike.

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Used to stub the registry, the contracts and the fetch.
	tmp_path : pathlib.Path
		Redirects the written report away from the repo.
	"""
	monkeypatch.setattr(driver, "_REPORT_PATH", tmp_path / "report.md")
	monkeypatch.setattr(
		driver, "load_registry", lambda: {"k": {"url": "https://example.invalid/x.csv"}}
	)
	monkeypatch.setattr(
		driver, "contracts_by_source_key", lambda: {"k": _Contract(("a",), False, "k")}
	)
	monkeypatch.setattr(
		driver, "live_header", lambda _entry: (_ for _ in ()).throw(OSError("down"))
	)
	assert driver.main() == 0
