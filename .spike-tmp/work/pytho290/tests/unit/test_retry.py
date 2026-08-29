"""Unit tests for the retry-with-backoff seam (decorator, executor and policy)."""

from dataclasses import FrozenInstanceError
from unittest.mock import Mock

import pytest

from src.utils import retry
from src.utils.retry import LogEmitter, RetryPolicy, call_with_backoff, retry_with_backoff
from src.utils.retry._schedule import _compute_backoff_wait


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


# --------------------------
# The package surface added in blueprintx#116
# --------------------------
#
# The three below did not exist while retry was a flat module: the RetryPolicy value object,
# the selectable wait schedule, and the imperative `call_with_backoff` executor. The split
# itself is covered by `test_retry_package_exports_its_public_surface` — an introspective
# check over `__all__` rather than five hand-listed imports, so adding a name to the package
# without exporting it is what fails.


def test_retry_package_exports_its_public_surface() -> None:
	"""The package re-exports the four public names; the submodule split stays internal."""
	assert set(retry.__all__) == {
		"LogEmitter",
		"RetryPolicy",
		"call_with_backoff",
		"retry_with_backoff",
	}


def test_policy_defaults_match_an_unconfigured_retry() -> None:
	"""``RetryPolicy()`` reproduces the module defaults, so it is a no-op wrapper."""
	cls_policy = RetryPolicy()

	assert (cls_policy.int_max_attempts, cls_policy.str_strategy) == (3, "exponential")


def test_policy_rejects_unknown_strategy() -> None:
	"""A strategy name outside the dispatch table fails at construction, not mid-retry."""
	with pytest.raises(ValueError, match="str_strategy must be one of"):
		RetryPolicy(str_strategy="fibonacci")


def test_policy_rejects_bad_max_attempts() -> None:
	"""``int_max_attempts`` below 1 fails fast."""
	with pytest.raises(ValueError, match=">= 1"):
		RetryPolicy(int_max_attempts=0)


def test_policy_is_frozen() -> None:
	"""The policy is immutable, so a shared instance cannot be mutated by one consumer."""
	with pytest.raises(FrozenInstanceError):
		RetryPolicy().int_max_attempts = 9


@pytest.mark.parametrize(
	("str_strategy", "int_attempt", "float_expected"),
	[
		# Every strategy waits the base before the FIRST retry — they diverge only after it.
		("exponential", 1, 2.0),
		("linear", 1, 2.0),
		("constant", 1, 2.0),
		("exponential", 3, 8.0),
		("linear", 3, 6.0),
		("constant", 3, 2.0),
	],
)
def test_compute_wait_follows_the_named_schedule(
	str_strategy: str, int_attempt: int, float_expected: float
) -> None:
	"""Each strategy computes its documented wait.

	Parameters
	----------
	str_strategy : str
		The schedule under test.
	int_attempt : int
		The 1-indexed number of the attempt that just failed.
	float_expected : float
		The wait the schedule must produce.
	"""
	assert _compute_backoff_wait(str_strategy, 2.0, 2.0, int_attempt, None) == float_expected


def test_compute_wait_clamps_to_the_cap() -> None:
	"""The cap bounds an exponential schedule that would otherwise grow without limit."""
	assert _compute_backoff_wait("exponential", 2.0, 2.0, 5, 10.0) == 10.0


def test_call_with_backoff_returns_on_first_success() -> None:
	"""The imperative executor returns the value and does not retry a success."""
	cls_call = Mock(side_effect=["ok"])

	assert call_with_backoff(cls_call) == "ok"


def test_call_with_backoff_retries_transient_then_succeeds() -> None:
	"""A transient failure is retried under the supplied policy."""
	cls_call = Mock(side_effect=[OSError("transient"), "ok"])
	cls_policy = RetryPolicy(int_max_attempts=2, float_base_wait_s=0.0)

	assert call_with_backoff(cls_call, cls_policy) == "ok"


def test_call_with_backoff_reraises_after_exhausting_attempts() -> None:
	"""The final attempt's exception propagates unchanged, never a wrapper exception."""
	cls_call = Mock(side_effect=OSError("still down"))
	cls_policy = RetryPolicy(int_max_attempts=2, float_base_wait_s=0.0)

	with pytest.raises(OSError, match="still down"):
		call_with_backoff(cls_call, cls_policy)


def test_call_with_backoff_label_names_the_caller_not_the_lambda() -> None:
	"""``str_label`` keeps the log meaningful when the callable is a ``lambda``.

	Without it the line reads ``<lambda> failed``, which names the wrapper rather than the
	operation that failed — and the log is the only record a scheduled run leaves behind.
	"""
	cls_emitter = _CapturingEmitter()
	cls_call = Mock(side_effect=[OSError("transient"), "ok"])
	cls_policy = RetryPolicy(int_max_attempts=2, float_base_wait_s=0.0)

	call_with_backoff(cls_call, cls_policy, cls_emitter, "download_file")

	assert "download_file failed" in cls_emitter.list_messages[0]


@pytest.mark.parametrize(
	"dict_kwargs",
	[
		{"float_base_wait_s": -1.0},
		{"float_factor": -2.0},
		{"float_max_wait_s": -0.5},
		{"float_base_wait_s": float("inf")},
		{"float_base_wait_s": float("nan")},
	],
)
def test_policy_rejects_a_wait_time_sleep_cannot_accept(dict_kwargs: dict) -> None:
	"""A wait that would crash the retry loop is refused at construction instead.

	``time.sleep`` raises ``ValueError`` on a negative and ``OverflowError`` on an infinity,
	so an unvalidated policy replaces the transient error being retried with a different one,
	raised from inside the recovery path.

	Parameters
	----------
	dict_kwargs : dict
		One invalid wait value to construct the policy with.
	"""
	with pytest.raises(ValueError, match="finite and >= 0"):
		RetryPolicy(**dict_kwargs)


def test_policy_accepts_an_unset_max_wait() -> None:
	"""``float_max_wait_s=None`` means uncapped and must survive the finite check."""
	assert RetryPolicy(float_max_wait_s=None).float_max_wait_s is None
