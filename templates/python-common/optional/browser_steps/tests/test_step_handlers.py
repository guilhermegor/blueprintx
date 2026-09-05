"""Tests for the recorded-browser-step dict-dispatch runner.

Run directly (no scaffold, no pytest-asyncio plugin — ``asyncio.run`` drives each
coroutine): ``python3 -m pytest templates/python-common/optional/browser_steps/tests``
from the repo root. ``conftest.py`` puts ``optional/`` on ``sys.path`` so the package
imports as plain ``browser_steps`` (see its docstring for why that is enough).
"""

from __future__ import annotations

import asyncio
import os

from browser_steps import BrowserStep, BrowserStepError, resolve_placeholders, run_browser_steps
from browser_steps.step_handlers import STEP_KINDS
import pytest


class FakeDownload:
	"""Records where the runner asked to save a download."""

	def __init__(self) -> None:
		self.str_saved_to: str | None = None

	async def save_as(self, path: str) -> None:
		"""Record ``path`` as where the download was saved."""
		self.str_saved_to = path


class FakeDownloadInfo:
	"""Async context manager standing in for ``page.expect_download()``."""

	def __init__(self, cls_download: FakeDownload) -> None:
		self._cls_download = cls_download

	async def __aenter__(self) -> FakeDownloadInfo:
		"""Enter the ``async with`` block, yielding this download info."""
		return self

	async def __aexit__(self, *args: object) -> None:
		"""Exit the ``async with`` block; nothing to clean up in the fake."""
		return None

	@property
	async def value(self) -> FakeDownload:
		"""Resolve to the fake download the ``download`` handler saves."""
		return self._cls_download


class FakePage:
	"""Records every call the runner makes, in order — no real browser involved."""

	def __init__(self) -> None:
		self.list_calls: list[tuple[str, ...]] = []
		self.cls_download = FakeDownload()

	async def goto(self, url: str) -> None:
		"""Record a ``navigate`` step's call."""
		self.list_calls.append(("goto", url))

	async def fill(self, selector: str, value: str) -> None:
		"""Record a ``fill``/``fill_date`` step's call."""
		self.list_calls.append(("fill", selector, value))

	async def click(self, selector: str) -> None:
		"""Record a ``click``/``datepicker`` step's call."""
		self.list_calls.append(("click", selector))

	async def select_option(self, selector: str, value: str) -> None:
		"""Record a ``select`` step's call."""
		self.list_calls.append(("select_option", selector, value))

	async def wait_for_timeout(self, timeout: float) -> None:
		"""Record a ``wait`` step's call."""
		self.list_calls.append(("wait_for_timeout", timeout))

	def expect_download(self) -> FakeDownloadInfo:
		"""Record a ``download`` step's call and hand back the fake download info."""
		self.list_calls.append(("expect_download",))
		return FakeDownloadInfo(self.cls_download)


def test_step_kinds_matches_the_vocabulary_in_issue_228() -> None:
	"""STEP_KINDS is the exact 8-word vocabulary the seam promises — not a subset."""
	set_expected_kinds = {
		"navigate",
		"fill",
		"fill_date",
		"click",
		"select",
		"wait",
		"datepicker",
		"download",
	}

	assert set_expected_kinds == STEP_KINDS


def test_run_browser_steps_dispatches_every_kind_in_order() -> None:
	"""A full recorded flow calls the page in the recorded order with resolved values."""
	os.environ["TEST_BROWSER_STEPS_INJECTED_VALUE"] = "resolved-from-env"
	cls_page = FakePage()
	list_steps: list[BrowserStep] = [
		{"kind": "navigate", "url": "https://vendor.example.com"},
		{"kind": "fill", "selector": "#password", "value": "${TEST_BROWSER_STEPS_INJECTED_VALUE}"},
		{"kind": "click", "selector": "#login"},
		{"kind": "select", "selector": "#report", "option": "Extrato"},
		{"kind": "fill_date", "selector": "#start", "value": "01/01/2026"},
		{"kind": "datepicker", "selector": "#picker", "value": "#day-15"},
		{"kind": "wait", "timeout_ms": 500},
		{"kind": "download", "trigger_selector": "#export", "save_path": "out.xlsx"},
	]
	list_expected_calls = [
		("goto", "https://vendor.example.com"),
		("fill", "#password", "resolved-from-env"),
		("click", "#login"),
		("select_option", "#report", "Extrato"),
		("fill", "#start", "01/01/2026"),
		("click", "#picker"),
		("click", "#day-15"),
		("wait_for_timeout", 500),
		("expect_download",),
		("click", "#export"),
	]

	asyncio.run(run_browser_steps(list_steps, cls_page))

	assert cls_page.list_calls == list_expected_calls
	assert cls_page.cls_download.str_saved_to == "out.xlsx"


def test_run_browser_steps_rejects_an_unknown_kind() -> None:
	"""An unrecognised kind fails fast, naming the offending step index."""
	cls_page = FakePage()
	list_steps: list[BrowserStep] = [{"kind": "double_click", "selector": "#x"}]

	with pytest.raises(BrowserStepError, match="Step 0: unknown kind 'double_click'"):
		asyncio.run(run_browser_steps(list_steps, cls_page))
	assert cls_page.list_calls == []


def test_resolve_placeholders_substitutes_from_environment() -> None:
	"""A ``${VAR}`` reference resolves to the matching environment variable's value."""
	os.environ["TEST_BROWSER_STEPS_USER"] = "ana"

	str_resolved = resolve_placeholders("${TEST_BROWSER_STEPS_USER}")

	assert str_resolved == "ana"


def test_resolve_placeholders_fails_fast_on_unset_variable() -> None:
	"""An unset ``${VAR}`` reference raises, naming the missing variable."""
	os.environ.pop("TEST_BROWSER_STEPS_UNSET", None)

	with pytest.raises(BrowserStepError, match="TEST_BROWSER_STEPS_UNSET"):
		resolve_placeholders("${TEST_BROWSER_STEPS_UNSET}")
