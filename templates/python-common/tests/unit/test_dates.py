"""Unit tests for the Brazilian business-day helpers.

The stpstone ANBIMA calendar is replaced with a recording stand-in so the tests
assert delegation without touching the network or the holiday cache.
"""

from datetime import date

import pytest

from src.utils import dates


class _FakeCalendar:
	"""Stand-in for ``DatesBRAnbima`` that echoes the method and arguments."""

	def is_working_day(self, date_: date) -> tuple[str, date]:
		"""Echo the call."""
		return ("is_working_day", date_)

	def is_holiday(self, date_: date) -> tuple[str, date]:
		"""Echo the call."""
		return ("is_holiday", date_)

	def add_working_days(self, date_: date, int_days: int) -> tuple[str, date, int]:
		"""Echo the call."""
		return ("add_working_days", date_, int_days)

	def delta_working_days(self, date_start: date, date_end: date) -> tuple[str, date, date]:
		"""Echo the call."""
		return ("delta_working_days", date_start, date_end)

	def nearest_working_day(self, date_: date, bool_next: bool) -> tuple[str, date, bool]:
		"""Echo the call."""
		return ("nearest_working_day", date_, bool_next)

	def holidays(self) -> list[tuple[str, date]]:
		"""Return a fixed holiday list."""
		return [("Confraternização", date(2026, 1, 1))]


@pytest.fixture(autouse=True)
def _patch_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Swap the module singleton for the recording stand-in."""
	monkeypatch.setattr(dates, "_CLS_CALENDAR", _FakeCalendar())


def test_is_working_day_delegates() -> None:
	"""``is_working_day`` forwards to the shared calendar."""
	dt = date(2026, 6, 8)
	assert dates.is_working_day(dt) == ("is_working_day", dt)


def test_add_working_days_delegates() -> None:
	"""``add_working_days`` forwards the date and the day count."""
	dt = date(2026, 6, 8)
	assert dates.add_working_days(dt, 3) == ("add_working_days", dt, 3)


def test_delta_working_days_delegates() -> None:
	"""``delta_working_days`` forwards both endpoints."""
	dt_a, dt_b = date(2026, 6, 1), date(2026, 6, 8)
	assert dates.delta_working_days(dt_a, dt_b) == ("delta_working_days", dt_a, dt_b)


def test_nearest_working_day_defaults_to_next() -> None:
	"""``nearest_working_day`` rolls forward by default."""
	dt = date(2026, 6, 7)
	assert dates.nearest_working_day(dt) == ("nearest_working_day", dt, True)


def test_holidays_delegates() -> None:
	"""``holidays`` returns the calendar's holiday list."""
	assert dates.holidays() == [("Confraternização", date(2026, 1, 1))]
