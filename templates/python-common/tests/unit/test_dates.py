"""Unit tests for the Brazilian business-day helpers.

The stpstone ANBIMA calendar is replaced with a recording stand-in so the tests
assert delegation without touching the network or the holiday cache. The stand-in
returns **correctly-typed** values — the wrappers enforce their return annotations
at runtime (beartype), so a sentinel of the wrong type would be rejected — and
records each call so delegation is asserted on the forwarded arguments.
"""

from datetime import date

import pytest

from src.utils import dates


class _FakeCalendar:
	"""Recording stand-in for ``DatesBRAnbima`` that returns typed values."""

	def __init__(self) -> None:
		"""Start with an empty call log."""
		self.list_calls: list[tuple] = []

	def is_working_day(self, date_: date) -> bool:
		"""Record the call and return a fixed boolean."""
		self.list_calls.append(("is_working_day", date_))
		return True

	def is_holiday(self, date_: date) -> bool:
		"""Record the call and return a fixed boolean."""
		self.list_calls.append(("is_holiday", date_))
		return False

	def add_working_days(self, date_: date, int_days: int) -> date:
		"""Record the call and return a fixed date."""
		self.list_calls.append(("add_working_days", date_, int_days))
		return date(2026, 6, 11)

	def delta_working_days(self, date_start: date, date_end: date) -> int:
		"""Record the call and return a fixed count."""
		self.list_calls.append(("delta_working_days", date_start, date_end))
		return 5

	def nearest_working_day(self, date_: date, bool_next: bool) -> date:
		"""Record the call and return a fixed date."""
		self.list_calls.append(("nearest_working_day", date_, bool_next))
		return date(2026, 6, 8)

	def holidays(self) -> list[tuple[str, date]]:
		"""Record the call and return a fixed holiday list."""
		self.list_calls.append(("holidays",))
		return [("Confraternização", date(2026, 1, 1))]


@pytest.fixture
def cls_calendar(monkeypatch: pytest.MonkeyPatch) -> _FakeCalendar:
	"""Swap the module singleton for the recording stand-in and expose it."""
	cls_fake = _FakeCalendar()
	monkeypatch.setattr(dates, "_CLS_CALENDAR", cls_fake)
	return cls_fake


def test_is_working_day_delegates(cls_calendar: _FakeCalendar) -> None:
	"""``is_working_day`` forwards to the shared calendar and returns its result."""
	dt = date(2026, 6, 8)
	assert dates.is_working_day(dt) is True
	assert cls_calendar.list_calls == [("is_working_day", dt)]


def test_add_working_days_delegates(cls_calendar: _FakeCalendar) -> None:
	"""``add_working_days`` forwards the date and the day count."""
	dt = date(2026, 6, 8)
	assert dates.add_working_days(dt, 3) == date(2026, 6, 11)
	assert cls_calendar.list_calls == [("add_working_days", dt, 3)]


def test_delta_working_days_delegates(cls_calendar: _FakeCalendar) -> None:
	"""``delta_working_days`` forwards both endpoints."""
	dt_a, dt_b = date(2026, 6, 1), date(2026, 6, 8)
	assert dates.delta_working_days(dt_a, dt_b) == 5
	assert cls_calendar.list_calls == [("delta_working_days", dt_a, dt_b)]


def test_nearest_working_day_defaults_to_next(cls_calendar: _FakeCalendar) -> None:
	"""``nearest_working_day`` rolls forward by default."""
	dt = date(2026, 6, 7)
	assert dates.nearest_working_day(dt) == date(2026, 6, 8)
	assert cls_calendar.list_calls == [("nearest_working_day", dt, True)]


def test_holidays_delegates(cls_calendar: _FakeCalendar) -> None:
	"""``holidays`` returns the calendar's holiday list."""
	assert dates.holidays() == [("Confraternização", date(2026, 1, 1))]
	assert cls_calendar.list_calls == [("holidays",)]
