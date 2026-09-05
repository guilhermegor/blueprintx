"""Recorded-browser-step runner — dict dispatch over the fixed step vocabulary.

Each step in ``data/browser-steps/*.json`` is ``{"kind": <name>, ...fields}``. The set
of valid ``kind`` values is :data:`STEP_KINDS`, derived from :data:`_DICT_STEP_HANDLERS`
itself rather than kept as a second, hand-maintained list — adding a step kind means
adding a dict entry, not another ``elif`` branch (see ``common.md`` — Design Patterns →
dict dispatch).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from .ports import BrowserPage, BrowserStep, BrowserStepError
from .secrets import resolve_placeholders


async def _navigate(cls_page: BrowserPage, dict_step: BrowserStep) -> None:
	"""Load ``url`` in the page."""
	await cls_page.goto(resolve_placeholders(dict_step["url"]))


async def _fill(cls_page: BrowserPage, dict_step: BrowserStep) -> None:
	"""Type ``value`` into the element at ``selector``."""
	await cls_page.fill(dict_step["selector"], resolve_placeholders(dict_step["value"]))


async def _fill_date(cls_page: BrowserPage, dict_step: BrowserStep) -> None:
	"""Type a formatted date ``value`` into a plain masked-text date input.

	Kept distinct from ``datepicker`` because a masked text input and a vendor calendar
	widget need different interactions, not the same ``fill``.
	"""
	await cls_page.fill(dict_step["selector"], resolve_placeholders(dict_step["value"]))


async def _click(cls_page: BrowserPage, dict_step: BrowserStep) -> None:
	"""Click the element at ``selector``."""
	await cls_page.click(dict_step["selector"])


async def _select(cls_page: BrowserPage, dict_step: BrowserStep) -> None:
	"""Choose ``option`` from the ``<select>`` at ``selector``."""
	await cls_page.select_option(dict_step["selector"], dict_step["option"])


async def _wait(cls_page: BrowserPage, dict_step: BrowserStep) -> None:
	"""Pause for ``timeout_ms`` milliseconds (use only when no selector settles the wait)."""
	await cls_page.wait_for_timeout(dict_step["timeout_ms"])


async def _datepicker(cls_page: BrowserPage, dict_step: BrowserStep) -> None:
	"""Open a vendor calendar widget at ``selector`` and click the day cell ``value``.

	The widget-specific mechanics (which selector reaches which day cell) live in the
	recording, not in this handler — a re-record after a vendor UI change is the fix.
	"""
	await cls_page.click(dict_step["selector"])
	await cls_page.click(resolve_placeholders(dict_step["value"]))


async def _download(cls_page: BrowserPage, dict_step: BrowserStep) -> None:
	"""Click ``trigger_selector`` and save the resulting download to ``save_path``."""
	async with cls_page.expect_download() as cls_download_info:
		await cls_page.click(dict_step["trigger_selector"])
	cls_download = await cls_download_info.value
	await cls_download.save_as(resolve_placeholders(dict_step["save_path"]))


_DICT_STEP_HANDLERS: dict[str, Callable[[BrowserPage, BrowserStep], Awaitable[None]]] = {
	"navigate": _navigate,
	"fill": _fill,
	"fill_date": _fill_date,
	"click": _click,
	"select": _select,
	"wait": _wait,
	"datepicker": _datepicker,
	"download": _download,
}

STEP_KINDS = frozenset(_DICT_STEP_HANDLERS)


async def run_browser_steps(list_steps: list[BrowserStep], cls_page: BrowserPage) -> None:
	"""Run a recorded flow: interpret each step in ``list_steps`` in order.

	Parameters
	----------
	list_steps : list[BrowserStep]
		Parsed from a ``data/browser-steps/*.json`` file.
	cls_page : BrowserPage
		A live Playwright page, or a test double satisfying the same Protocol.

	Raises
	------
	BrowserStepError
		If a step's ``kind`` is not one of :data:`STEP_KINDS`, or a step references an
		unset secret placeholder (raised by the handler it dispatches to).
	"""
	for int_index, dict_step in enumerate(list_steps):
		str_kind = dict_step.get("kind", "")
		if str_kind not in _DICT_STEP_HANDLERS:
			raise BrowserStepError(
				f"Step {int_index}: unknown kind {str_kind!r}; expected one of "
				f"{sorted(STEP_KINDS)}"
			)
		await _DICT_STEP_HANDLERS[str_kind](cls_page, dict_step)
