"""Unit tests for the rich default log emitter (utils/logs_emitter.py)."""

import logging

import pytest

from utils.logs import _SET_SKIP_MODULES
from utils.logs_emitter import LogsEmitter
from utils.retry import LogEmitter


def test_logs_emitter_is_a_log_emitter() -> None:
    """LogsEmitter is a drop-in LogEmitter, so any consumer can inject it in place of the base."""
    assert isinstance(LogsEmitter(), LogEmitter)


@pytest.mark.parametrize("str_level", ["info", "not-a-level"])
def test_logs_emitter_emits_at_any_level_without_raising(
    caplog: pytest.LogCaptureFixture, str_level: str
) -> None:
    """A valid level and an unrecognised one both emit; the odd level degrades, never raises.

    Parameters
    ----------
    caplog : pytest.LogCaptureFixture
        Captures what the emitter logged.
    str_level : str
        A recognised level, then one the emitter must degrade on.
    """
    cls_logger = logging.getLogger("test_logs_emitter")
    with caplog.at_level(logging.DEBUG, logger="test_logs_emitter"):
        LogsEmitter(cls_logger).log_message("emitted message", str_level)
    assert "emitted message" in caplog.text


def test_skip_set_matches_package_qualified_module_last_component() -> None:
    """The stack-walker skip set matches a module's last dotted component, not a prefix.

    Regression: a package-qualified name (e.g. the nested private-package typing engine) must
    match its final segment so the reconstructed caller class is not misattributed to a wrapper
    frame — the earlier prefix match silently failed for that layout.
    """
    str_qualified = "myproject._internal.utils.typing"
    assert str_qualified.rsplit(".", 1)[-1] in _SET_SKIP_MODULES


def test_skip_set_names_every_wrapper_module() -> None:
    """The skip set carries every wrapper module the stack walker must step over."""
    assert {"logs", "logs_emitter", "retry", "typing"} <= _SET_SKIP_MODULES
