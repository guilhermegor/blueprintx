"""Unit tests for the retry-with-backoff decorator."""

import pytest

from src.utils.retry import LogEmitter, retry_with_backoff


def test_retry_returns_on_first_success() -> None:
	"""A call that succeeds immediately is not retried."""
	dict_calls = {"n": 0}

	@retry_with_backoff(int_max_attempts=3, float_base_wait_s=0.0)
	def fn() -> str:
		dict_calls["n"] += 1
		return "ok"

	assert fn() == "ok"
	assert dict_calls["n"] == 1


def test_retry_retries_transient_then_succeeds() -> None:
	"""A transient OSError is retried until the call succeeds."""
	dict_calls = {"n": 0}

	@retry_with_backoff(int_max_attempts=3, float_base_wait_s=0.0)
	def fn() -> str:
		dict_calls["n"] += 1
		if dict_calls["n"] < 3:
			raise OSError("transient")
		return "ok"

	assert fn() == "ok"
	assert dict_calls["n"] == 3


def test_retry_does_not_retry_non_transient() -> None:
	"""An exception outside the configured transient types fails fast (no retry)."""
	dict_calls = {"n": 0}

	@retry_with_backoff(int_max_attempts=3, float_base_wait_s=0.0, tuple_exceptions=(OSError,))
	def fn() -> None:
		dict_calls["n"] += 1
		raise ValueError("permanent")

	with pytest.raises(ValueError, match="permanent"):
		fn()
	assert dict_calls["n"] == 1


def test_retry_rejects_bad_max_attempts() -> None:
	"""``int_max_attempts`` below 1 fails fast."""
	with pytest.raises(ValueError, match=">= 1"):
		retry_with_backoff(int_max_attempts=0)


def test_retry_writes_warning_to_injected_logger() -> None:
	"""Each retry warning is routed to an injected ``LogEmitter`` (dependency injection)."""
	list_messages: list[str] = []

	class _CapturingEmitter(LogEmitter):
		"""Emitter that records messages instead of logging them."""

		def log_message(self, str_message: str, str_level: str) -> None:
			"""Record ``str_level``/``str_message`` for assertion.

			Parameters
			----------
			str_message : str
				The message to record.
			str_level : str
				The level name to record.
			"""
			list_messages.append(f"{str_level}:{str_message}")

	dict_calls = {"n": 0}

	@retry_with_backoff(int_max_attempts=3, float_base_wait_s=0.0, cls_logger=_CapturingEmitter())
	def fn() -> str:
		dict_calls["n"] += 1
		if dict_calls["n"] < 3:
			raise OSError("transient")
		return "ok"

	assert fn() == "ok"
	assert len(list_messages) == 2
	assert all(msg.startswith("warning:") for msg in list_messages)
