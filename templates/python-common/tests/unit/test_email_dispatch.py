"""Unit tests for e-mail dispatch-flag resolution (utils/email/dispatch.py)."""

import logging

import pytest

from src.utils.email.dispatch import resolve_dispatch


def test_resolve_dispatch_reads_per_block_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A per-block flag overrides the hard default."""
    monkeypatch.setenv("EMAIL_SEND__REPORT", "no")
    monkeypatch.setenv("EMAIL_AUTO_SEND__REPORT", "yes")
    assert resolve_dispatch("report") == (False, True)


def test_resolve_dispatch_falls_back_to_hard_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """An absent per-block AND absent __DEFAULTS flag falls back to the hard default."""
    monkeypatch.delenv("EMAIL_SEND__DEFAULTS", raising=False)
    monkeypatch.delenv("EMAIL_AUTO_SEND__DEFAULTS", raising=False)
    assert resolve_dispatch("other") == (True, False)


def test_resolve_dispatch_logs_every_consulted_variable_name(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Every consulted env-var name and its set/unset status is logged (blueprintx#121)."""
    monkeypatch.setenv("EMAIL_SEND__REPORT", "no")
    monkeypatch.delenv("EMAIL_AUTO_SEND__REPORT", raising=False)
    monkeypatch.delenv("EMAIL_AUTO_SEND__DEFAULTS", raising=False)
    cls_logger = logging.getLogger("test_email_dispatch")
    with caplog.at_level(logging.INFO, logger="test_email_dispatch"):
        resolve_dispatch("report", cls_logger)
    str_log = caplog.text
    assert "EMAIL_SEND__REPORT" in str_log
    assert "EMAIL_AUTO_SEND__REPORT" in str_log
    assert "EMAIL_AUTO_SEND__DEFAULTS" in str_log


def test_resolve_dispatch_renamed_key_is_visible_in_the_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A renamed config key does not resolve silently: the OLD var name is logged as unset.

    Guards blueprintx#121's second lesson — a flag derived from a renamed config key that is
    still read under its old name falls back to the default with NOTHING saying which key it
    looked for. Here ``EMAIL_SEND__OLD_NAME`` (the stale var a rename left behind) is set, but
    the block is now looked up as ``report``, so the consulted name is ``EMAIL_SEND__REPORT`` —
    the log must show that exact name as unset, not the stale one silently winning.
    """
    monkeypatch.setenv("EMAIL_SEND__OLD_NAME", "false")
    monkeypatch.delenv("EMAIL_SEND__REPORT", raising=False)
    monkeypatch.delenv("EMAIL_SEND__DEFAULTS", raising=False)
    cls_logger = logging.getLogger("test_email_dispatch_rename")
    with caplog.at_level(logging.INFO, logger="test_email_dispatch_rename"):
        bool_send, _ = resolve_dispatch("report", cls_logger)
    assert bool_send is True  # the stale name is never consulted, so the hard default wins
    assert "EMAIL_SEND__REPORT (unset)" in caplog.text
    assert "OLD_NAME" not in caplog.text
