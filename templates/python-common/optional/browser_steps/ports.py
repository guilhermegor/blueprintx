"""Recorded-browser-step shape and the page port its handlers call.

Kept dependency-free on purpose: :class:`BrowserPage` is a ``Protocol`` naming only the
``playwright.async_api.Page`` methods the handlers use, so this package (and its tests)
carry no hard dependency on ``playwright`` — any object with these methods (a real page,
or a test double) satisfies it.
"""

from __future__ import annotations

from collections.abc import Awaitable
from contextlib import AbstractAsyncContextManager
from typing import Protocol, TypedDict


class BrowserStepError(Exception):
	"""Raised when a recorded step cannot be run.

	Covers an unknown ``kind`` (see ``STEP_KINDS``) and a step field that references an
	environment variable which is not set (see ``resolve_placeholders``).
	"""


class BrowserStep(TypedDict, total=False):
	"""One recorded browser action, as it appears in ``data/browser-steps/*.json``.

	``kind`` selects the handler (see ``STEP_KINDS``); every other field is
	kind-specific — see each handler's docstring in :mod:`browser_steps.step_handlers`.
	"""

	kind: str
	selector: str
	value: str
	url: str
	option: str
	timeout_ms: int
	trigger_selector: str
	save_path: str


class BrowserDownload(Protocol):
	"""The subset of ``playwright.async_api.Download`` the ``download`` handler calls."""

	async def save_as(self, path: str) -> None:
		"""Save the completed download to ``path``."""
		...


class BrowserDownloadInfo(Protocol):
	"""The object yielded by ``page.expect_download()``'s ``async with`` block."""

	value: Awaitable[BrowserDownload]


class BrowserPage(Protocol):
	"""The subset of ``playwright.async_api.Page`` the step handlers call."""

	async def goto(self, url: str) -> object:
		"""Navigate the page to ``url`` (the return value is discarded).

		⚠️ ``object``, not ``None``: the real ``Page.goto`` returns ``Response | None``,
		and a Protocol method promising ``None`` is NOT satisfied by one returning a
		Response — strict type checking would reject the very page this port exists to
		describe. Same reason applies to ``select_option`` below.
		"""
		...

	async def fill(self, selector: str, value: str) -> None:
		"""Type ``value`` into the element matched by ``selector``."""
		...

	async def click(self, selector: str) -> None:
		"""Click the element matched by ``selector``."""
		...

	async def select_option(self, selector: str, value: str) -> object:
		"""Choose ``value`` from the ``<select>`` (the real page returns ``list[str]``)."""
		...

	async def wait_for_timeout(self, timeout: float) -> None:
		"""Pause for ``timeout`` milliseconds."""
		...

	def expect_download(self) -> AbstractAsyncContextManager[BrowserDownloadInfo]:
		"""Return an async context manager that captures the next download."""
		...
