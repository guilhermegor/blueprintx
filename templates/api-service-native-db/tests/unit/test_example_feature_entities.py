"""``Note`` entity defaults for the example_feature capability (#646)."""

from __future__ import annotations

from datetime import timedelta

from capabilities.example_feature.domain.entities import Note


def test_note_created_at_default_is_timezone_aware_utc() -> None:
    """``Note.created_at`` is an aware UTC timestamp, not the naive ``utcnow`` one.

    ``datetime.utcnow`` is deprecated since Python 3.12 and returns a naive value that
    compares unequal to, and cannot be subtracted from, any aware ``datetime``. The default
    uses ``timezone.utc`` rather than ``ZoneInfo("UTC")`` because the latter needs tz data
    that Windows lacks without the ``tzdata`` package.
    """
    assert Note().created_at.utcoffset() == timedelta(0)
