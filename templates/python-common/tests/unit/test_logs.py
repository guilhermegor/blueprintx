"""Unit tests for the logging module (``CreateLog`` + shared ``log_message``)."""

import gc
from pathlib import Path
import re
import warnings

import pytest

from src.utils import logs
from src.utils.logs import CreateLog


class _RecordingLog:
    """Stand-in for ``CreateLog`` that records the last call."""

    def __init__(self) -> None:
        self.tuple_last_call: tuple[object, str, str] | None = None

    def log_message(self, logger: object, str_message: str, str_level: str) -> None:
        """Record the arguments instead of emitting a log line."""
        self.tuple_last_call = (logger, str_message, str_level)


def test_log_message_delegates_to_shared_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    """``log_message`` forwards its arguments to the shared ``CreateLog`` instance."""
    cls_recorder = _RecordingLog()
    monkeypatch.setattr(logs, "_CLS_LOG", cls_recorder)
    logs.log_message(None, "hello", "warning")
    assert cls_recorder.tuple_last_call == (None, "hello", "warning")


def test_log_message_defaults_to_info_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default level is ``info`` when none is given."""
    cls_recorder = _RecordingLog()
    monkeypatch.setattr(logs, "_CLS_LOG", cls_recorder)
    logs.log_message(None, "hello")
    assert cls_recorder.tuple_last_call == (None, "hello", "info")


def test_basic_conf_returns_logger_writing_to_file(tmp_path: Path) -> None:
    """``basic_conf`` configures a file logger that writes to the given path."""
    path_log = tmp_path / "run.log"
    cls_log = CreateLog()
    logger = cls_log.basic_conf(complete_path=str(path_log), basic_level="info")
    # No explicit flush is needed. A StreamHandler flushes on every record it emits, so the
    # flush loop that used to sit here was dead code that made the test look like it needed one.
    logger.info("hello")
    assert path_log.exists()
    assert "hello" in path_log.read_text()


def test_log_message_emits_through_logger(tmp_path: Path) -> None:
    """``CreateLog.log_message`` routes the message through the logger with a caller prefix."""
    path_log = tmp_path / "run.log"
    cls_log = CreateLog()
    logger = cls_log.basic_conf(complete_path=str(path_log), basic_level="info")
    cls_log.log_message(logger, "boom", "error")
    str_written = path_log.read_text()
    # The caller-context prefix is reconstructed by walking the stack, so the exact caller
    # under a test runner varies; assert the prefix shape rather than a specific caller name.
    assert "boom" in str_written
    assert re.search(r"\[\w+\.\w+\] boom", str_written) is not None


def test_log_message_prints_when_logger_none(capsys: pytest.CaptureFixture[str]) -> None:
    """``CreateLog.log_message`` prints a timestamped line when no logger is provided."""
    CreateLog().log_message(None, "printed", "info")
    assert "printed" in capsys.readouterr().out


def test_basic_conf_reconfigure_closes_previous_handler(tmp_path: Path) -> None:
    """Reconfiguring the logger closes the previous ``FileHandler`` instead of leaking it."""
    path_first = tmp_path / "first.log"
    path_second = tmp_path / "second.log"
    cls_log = CreateLog()
    logger = cls_log.basic_conf(complete_path=str(path_first), basic_level="info")
    cls_handler_first = logger.handlers[0]
    cls_log.basic_conf(complete_path=str(path_second), basic_level="info")
    # Closing a FileHandler sets its stream attribute back to None once the descriptor is
    # released — a deterministic signal that does not depend on garbage-collection timing.
    assert cls_handler_first.stream is None


def test_basic_conf_reconfigure_emits_no_resource_warning(tmp_path: Path) -> None:
    """Reconfiguring the logger raises no ``ResourceWarning`` even when GC is forced.

    ``ResourceWarning`` fires at garbage-collection time, not at the leak, so it is
    invisible under default settings — this forces collection and records every warning
    raised while it runs, so a regression here is caught rather than silently swallowed.

    ⚠️ Both ``basic_conf`` calls must sit INSIDE the capture block. The second call is what
    makes the first handler unreachable, so a leaked handler can be collected — and its
    ``ResourceWarning`` emitted — during that call. With the calls outside, the warning
    fires before the block opens and the test passes over a real leak: measured at 0
    captured warnings against a deliberately leaking reconfigure, versus 1 with the calls
    inside.
    """
    path_first = tmp_path / "first.log"
    path_second = tmp_path / "second.log"
    cls_log = CreateLog()
    with warnings.catch_warnings(record=True) as list_caught:
        warnings.simplefilter("always")
        cls_log.basic_conf(complete_path=str(path_first), basic_level="info")
        cls_log.basic_conf(complete_path=str(path_second), basic_level="info")
        gc.collect()
    assert not any(
        issubclass(cls_warning.category, ResourceWarning) for cls_warning in list_caught
    )
