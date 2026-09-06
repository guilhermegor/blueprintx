"""Brazilian business-day helpers backed by the ANBIMA holiday calendar.

Wraps wwdates' :class:`~wwdates.br.anbima.DatesBRAnbima` so the whole project
shares one calendar instance and a small, intention-revealing function surface
instead of each caller building its own. Every call is **local** — no network, no
cache warm-up.

⚠️ That is a property of the pinned floor, not of the name. wwdates 1.0.0 made
``wwdates.br.anbima.DatesBRAnbima`` the OFFLINE implementation and moved the
page-scraping one to ``wwdates.br.anbima_web.DatesBRAnbimaWeb``. Under the old
``>=0.1.0`` floor the same import could resolve to 0.1.0 and silently bring the
networked semantics back under this exact name, which is why the service tiers pin
``wwdates >=1.0.0`` (blueprintx#110). Accuracy is not the trade: wwdates measured an
EMPTY symmetric difference against ANBIMA's published table across 2001-2099, the full
span ANBIMA publishes. Reach for ``DatesBRAnbimaWeb`` explicitly only to cover dates
outside that span or to verify against the live source.

The floor is open (``>=``, the repo-wide constraint style), so it resolves to the newest
wwdates — 2.0.0 at the time of writing. Verified against both wheels rather than assumed:
1.0.0 and 2.0.0 each export ``DatesBRAnbima`` from ``wwdates.br.anbima`` with no HTTP
client imported, an all-optional ``__init__``, and every method this module calls. 2.0.0's
major is the addition of US calendars, not a change to this one.

Pass dates as :class:`datetime.date` (or :class:`datetime.datetime`); helpers that
return a calendar day return a :class:`datetime.date`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from wwdates.br.anbima import DatesBRAnbima


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). TYPE_CHECKING stubs the decorator's shape
# locally instead of importing: mypy treats a try/except import as executed code and flags
# the redefinition once actually checked, so this branch can't pick either layout
# (blueprintx#360). Runtime still resolves the real engine via try/except below.
if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    _F = TypeVar("_F", bound=Callable[..., object])

    def type_checker(fn: _F) -> _F:
        """Type-only stub — see src/utils/CLAUDE.md."""
else:
    try:
        from utils.typing import type_checker
    except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
        from chassis.typing import type_checker


# One shared calendar for the whole process (mirrors loggers._CLS_LOG). Cheap to
# construct, and the holiday table ships with the package — nothing is fetched, ever.
_CLS_CALENDAR = DatesBRAnbima()


@type_checker
def is_working_day(dt_date: date | datetime) -> bool:
    """Return whether ``dt_date`` is a Brazilian (ANBIMA) business day.

    Parameters
    ----------
    dt_date : datetime.date | datetime.datetime
            The date to test.

    Returns
    -------
    bool
            ``True`` when ``dt_date`` is neither a weekend nor an ANBIMA holiday.
    """
    return _CLS_CALENDAR.is_working_day(dt_date)


@type_checker
def is_holiday(dt_date: date | datetime) -> bool:
    """Return whether ``dt_date`` is an ANBIMA national holiday.

    Parameters
    ----------
    dt_date : datetime.date | datetime.datetime
            The date to test.

    Returns
    -------
    bool
            ``True`` when ``dt_date`` falls on an ANBIMA holiday.
    """
    return _CLS_CALENDAR.is_holiday(dt_date)


@type_checker
def add_working_days(dt_date: date | datetime, int_days: int) -> date:
    """Return the business day ``int_days`` ANBIMA working days from ``dt_date``.

    Parameters
    ----------
    dt_date : datetime.date | datetime.datetime
            The starting date.
    int_days : int
            Number of working days to add (may be negative to go backwards).

    Returns
    -------
    datetime.date
            The resulting business day.
    """
    return _CLS_CALENDAR.add_working_days(dt_date, int_days)


@type_checker
def delta_working_days(dt_start: date | datetime, dt_end: date | datetime) -> int:
    """Return the count of ANBIMA working days between two dates.

    Parameters
    ----------
    dt_start : datetime.date | datetime.datetime
            Start date (inclusive per wwdates' convention).
    dt_end : datetime.date | datetime.datetime
            End date.

    Returns
    -------
    int
            The number of working days between ``dt_start`` and ``dt_end``.
    """
    return _CLS_CALENDAR.delta_working_days(dt_start, dt_end)


@type_checker
def nearest_working_day(dt_date: date | datetime, bool_next: bool = True) -> date:
    """Return the nearest ANBIMA working day to ``dt_date``.

    Parameters
    ----------
    dt_date : datetime.date | datetime.datetime
            The reference date.
    bool_next : bool, optional
            When ``True`` (default) roll forward to the next working day; when
            ``False`` roll back to the previous one.

    Returns
    -------
    datetime.date
            ``dt_date`` if it is already a working day, else the nearest one in the
            requested direction.
    """
    return _CLS_CALENDAR.nearest_working_day(dt_date, bool_next)


@type_checker
def holidays() -> list[tuple[str, date]]:
    """Return the ANBIMA national holidays as ``(name, date)`` tuples.

    Returns
    -------
    list of tuple of (str, datetime.date)
            Each holiday's name and date. Read from the package's bundled table — no
            network call, so this is safe in a test suite and behind a corporate proxy.
    """
    return _CLS_CALENDAR.holidays()
