"""Unit tests for the shared logging entry point."""

import pytest

from src.utils import loggers


class _RecordingLog:
	"""Stand-in for stpstone ``CreateLog`` that records the last call."""

	def __init__(self) -> None:
		self.tuple_last_call: tuple[object, str, str] | None = None

	def log_message(self, logger: object, str_message: str, str_level: str) -> None:
		"""Record the arguments instead of emitting a log line."""
		self.tuple_last_call = (logger, str_message, str_level)


def test_log_message_delegates_to_shared_logger(monkeypatch: pytest.MonkeyPatch) -> None:
	"""``log_message`` forwards its arguments to the shared CreateLog instance."""
	cls_recorder = _RecordingLog()
	monkeypatch.setattr(loggers, "_CLS_LOG", cls_recorder)
	loggers.log_message(None, "hello", "warning")
	assert cls_recorder.tuple_last_call == (None, "hello", "warning")


def test_log_message_defaults_to_info_level(monkeypatch: pytest.MonkeyPatch) -> None:
	"""The default level is ``info`` when none is given."""
	cls_recorder = _RecordingLog()
	monkeypatch.setattr(loggers, "_CLS_LOG", cls_recorder)
	loggers.log_message(None, "hello")
	assert cls_recorder.tuple_last_call == (None, "hello", "info")
