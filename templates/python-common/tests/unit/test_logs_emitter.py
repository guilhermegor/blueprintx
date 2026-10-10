"""Unit tests for the rich default log emitter (utils/logs_emitter.py)."""

import logging
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

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


@pytest.fixture
def mock_create_log(mocker: MockerFixture) -> MagicMock:
    """Replace ``CreateLog`` in ``logs_emitter`` with an autospec-ed mock.

    Parameters
    ----------
    mocker : pytest_mock.MockerFixture
            The pytest-mock fixture.

    Returns
    -------
    unittest.mock.MagicMock
            The mock standing in for the ``CreateLog`` instance the emitter builds.
    """
    return mocker.patch("utils.logs_emitter.CreateLog", autospec=True).return_value


def test_logs_emitter_without_logger_passes_none_to_create_log(
    mock_create_log: MagicMock,
) -> None:
    """With no logger injected the printer gets ``None``, so its screen path is reachable.

    Regression (blueprintx#597): the base ``LogEmitter`` swaps ``None`` for the module logger,
    so the screen fallback in ``CreateLog.log_message`` could never trigger.

    Parameters
    ----------
    mock_create_log : unittest.mock.MagicMock
            The mocked ``CreateLog`` instance.
    """
    LogsEmitter().log_message("hello", "info")
    mock_create_log.log_message.assert_called_once_with(None, "hello", "info")


def test_logs_emitter_default_prints_message_to_screen(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A default ``LogsEmitter()`` prints the message, through the real ``CreateLog``.

    Regression (blueprintx#597): before the fix the substituted module logger swallowed the
    line, so nothing reached the screen.

    Parameters
    ----------
    capsys : pytest.CaptureFixture[str]
            Captures what the emitter printed.
    """
    LogsEmitter().log_message("visible on screen", "info")
    assert "visible on screen" in capsys.readouterr().out


def test_logs_emitter_with_logger_passes_it_through_unchanged(
    mock_create_log: MagicMock,
) -> None:
    """An injected logger reaches the printer untouched.

    Parameters
    ----------
    mock_create_log : unittest.mock.MagicMock
            The mocked ``CreateLog`` instance.
    """
    cls_logger = logging.getLogger("test_logs_emitter_injected")
    LogsEmitter(cls_logger).log_message("hello", "info")
    mock_create_log.log_message.assert_called_once_with(cls_logger, "hello", "info")
