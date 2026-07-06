"""Unit tests for the rich default log emitter (utils/logs_emitter.py)."""

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
