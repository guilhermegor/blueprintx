"""Unit tests for the logging module (``CreateLog`` + shared ``log_message``)."""

from pathlib import Path
import re

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
	logger.info("hello")
	for handler in logger.handlers:
		handler.flush()
	assert path_log.exists()
	assert "hello" in path_log.read_text()


def test_log_message_emits_through_logger(tmp_path: Path) -> None:
	"""``CreateLog.log_message`` routes the message through the logger with a caller prefix."""
	path_log = tmp_path / "run.log"
	cls_log = CreateLog()
	logger = cls_log.basic_conf(complete_path=str(path_log), basic_level="info")
	cls_log.log_message(logger, "boom", "error")
	for handler in logger.handlers:
		handler.flush()
	str_written = path_log.read_text()
	# The caller-context prefix is reconstructed by walking the stack, so the exact caller
	# under a test runner varies; assert the prefix shape rather than a specific caller name.
	assert "boom" in str_written
	assert re.search(r"\[\w+\.\w+\] boom", str_written) is not None


def test_log_message_prints_when_logger_none(capsys: pytest.CaptureFixture[str]) -> None:
	"""``CreateLog.log_message`` prints a timestamped line when no logger is provided."""
	CreateLog().log_message(None, "printed", "info")
	assert "printed" in capsys.readouterr().out
