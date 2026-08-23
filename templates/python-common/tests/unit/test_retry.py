"""Unit tests for the retry-with-backoff decorator."""

from unittest.mock import Mock

import pytest

from src.utils.retry import LogEmitter, retry_with_backoff


# ⚠️ The flaky callable is a `Mock(side_effect=[…])`, not a nested `def` with a counter and an
# `if`. Two reasons, and the second is the load-bearing one:
#
#   1. mccabe charges the ENCLOSING function 1 for every nested `def`, and tests/ is capped at
#      complexity 1 (bin/check_complexity.sh). An inline stub would spend the whole budget.
#   2. The `if dict_calls["n"] < 3: raise` form put a BRANCH in the test body — and which side
#      of it ran does not appear in the green. `side_effect` states the call sequence as data:
#      "raise, raise, return" is the scenario, written where a reader looks for it.
#
# `functools.wraps` (which the decorator applies) tolerates a Mock: it skips the wrapper
# attributes the target does not have.
class _CapturingEmitter(LogEmitter):
	"""Emitter that records messages instead of logging them.

	Subclasses :class:`LogEmitter` rather than duck-typing it: the runtime checker enforces
	NOMINAL types, so a structurally-identical stand-in is rejected at the call boundary.
	"""

	def __init__(self) -> None:
		super().__init__()
		self.list_messages: list[str] = []

	def log_message(self, str_message: str, str_level: str) -> None:
		"""Record ``str_level``/``str_message`` for assertion.

		Parameters
		----------
		str_message : str
			The message to record.
		str_level : str
			The level name to record.

		Returns
		-------
		None
		"""
		self.list_messages.append(f"{str_level}:{str_message}")


def test_retry_returns_on_first_success() -> None:
	"""A call that succeeds immediately is not retried."""
	cls_call = Mock(side_effect=["ok"])
	fn = retry_with_backoff(int_max_attempts=3, float_base_wait_s=0.0)(cls_call)

	assert fn() == "ok"
	assert cls_call.call_count == 1


def test_retry_retries_transient_then_succeeds() -> None:
	"""A transient OSError is retried until the call succeeds."""
	cls_call = Mock(side_effect=[OSError("transient"), OSError("transient"), "ok"])
	fn = retry_with_backoff(int_max_attempts=3, float_base_wait_s=0.0)(cls_call)

	assert fn() == "ok"
	assert cls_call.call_count == 3


def test_retry_does_not_retry_non_transient() -> None:
	"""An exception outside the configured transient types fails fast (no retry)."""
	cls_call = Mock(side_effect=ValueError("permanent"))
	fn = retry_with_backoff(
		int_max_attempts=3, float_base_wait_s=0.0, tuple_exceptions=(OSError,)
	)(cls_call)

	with pytest.raises(ValueError, match="permanent"):
		fn()
	assert cls_call.call_count == 1


def test_retry_rejects_bad_max_attempts() -> None:
	"""``int_max_attempts`` below 1 fails fast."""
	with pytest.raises(ValueError, match=">= 1"):
		retry_with_backoff(int_max_attempts=0)


def test_retry_writes_warning_to_injected_logger() -> None:
	"""Each retry warning is routed to an injected ``LogEmitter`` (dependency injection)."""
	cls_emitter = _CapturingEmitter()
	cls_call = Mock(side_effect=[OSError("transient"), OSError("transient"), "ok"])
	fn = retry_with_backoff(int_max_attempts=3, float_base_wait_s=0.0, cls_logger=cls_emitter)(
		cls_call
	)

	assert fn() == "ok"
	assert len(cls_emitter.list_messages) == 2
	assert all(msg.startswith("warning:") for msg in cls_emitter.list_messages)
