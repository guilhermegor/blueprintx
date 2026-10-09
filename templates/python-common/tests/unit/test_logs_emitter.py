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


def test_logs_emitter_emits_at_any_level_without_raising() -> None:
    """A valid level and an unrecognised one both emit; the odd level degrades, never raises."""
    emitter = LogsEmitter()
    emitter.log_message("valid level", "info")
    emitter.log_message("odd level falls back", "not-a-level")


def test_skip_set_matches_package_qualified_module_last_component() -> None:
    """The stack-walker skip set matches a module's last dotted component, not a prefix.

    Regression: a package-qualified name (e.g. the nested private-package typing engine) must
    match its final segment so the reconstructed caller class is not misattributed to a wrapper
    frame — the earlier prefix match silently failed for that layout.
    """
    str_qualified = "myproject._internal.utils.typing"
    assert str_qualified.rsplit(".", 1)[-1] in _SET_SKIP_MODULES
    assert {"logs", "logs_emitter", "retry", "typing"} <= _SET_SKIP_MODULES


@pytest.fixture
def mock_create_log(mocker: MockerFixture) -> MagicMock:
    """Replace ``CreateLog`` in ``logs_emitter`` with a ``spec=``-ed mock.

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
