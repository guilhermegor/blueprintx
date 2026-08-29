"""Unit tests for ``PipelineOrchestrator._notify`` (SQLAlchemy ORM).

Covers issue #227: the notification payload must be measured at composition time,
**before** the ``cls_webhook is None`` gate — not only inside the branch that runs when a
webhook is wired. A test that exercises only the configured-webhook path would pass even if
the measurement lived after the gate, so each defect gets its own test: one proves the
measurement fires when the gate short-circuits, another proves it still precedes the send.
"""

from pathlib import Path
from unittest.mock import Mock

from pytest_mock import MockerFixture

from src.controller._pipeline import PipelineOrchestrator, WebhookNotifier


# --------------------------
# Helpers
# --------------------------
def _build_orchestrator(
	tmp_path: Path, cls_webhook: WebhookNotifier | None
) -> PipelineOrchestrator:
	"""Build a minimal orchestrator for exercising ``_notify`` in isolation.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest-provided temporary directory, used for the unused JSON summary path.
	cls_webhook : WebhookNotifier | None
		The notifier to inject (``None`` to exercise the short-circuit gate).

	Returns
	-------
	PipelineOrchestrator
		An orchestrator wired only with what ``_notify`` needs.
	"""
	return PipelineOrchestrator(
		logger=None,
		fn_build_engine=lambda: None,
		fn_output_path=lambda str_key: tmp_path / str_key,
		path_json=tmp_path / "summary.json",
		dict_context={},
		cls_webhook=cls_webhook,
		str_webhook_message="hello notification",
	)


# --------------------------
# Tests
# --------------------------
def test_notify_logs_payload_composition_when_gate_short_circuits(
	tmp_path: Path, mocker: MockerFixture
) -> None:
	"""The payload measurement fires even when ``cls_webhook is None`` short-circuits the send.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest-provided temporary directory.
	mocker : MockerFixture
		pytest-mock fixture for patching.

	Returns
	-------
	None
	"""
	mock_log = mocker.patch("src.controller._pipeline.log_message")
	_build_orchestrator(tmp_path, cls_webhook=None)._notify()
	str_log = "\n".join(call.args[1] for call in mock_log.call_args_list)
	assert "Notification payload composed: 18 chars" in str_log


def test_notify_does_not_send_when_gate_short_circuits(
	tmp_path: Path, mocker: MockerFixture
) -> None:
	"""No send-related log line is emitted when no webhook was injected.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest-provided temporary directory.
	mocker : MockerFixture
		pytest-mock fixture for patching.

	Returns
	-------
	None
	"""
	mock_log = mocker.patch("src.controller._pipeline.log_message")
	_build_orchestrator(tmp_path, cls_webhook=None)._notify()
	str_log = "\n".join(call.args[1] for call in mock_log.call_args_list)
	assert "Sending webhook notification" not in str_log


def test_notify_measures_payload_before_sending_when_webhook_configured(
	tmp_path: Path, mocker: MockerFixture
) -> None:
	"""The composition measurement is logged before the send, when a webhook IS wired.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest-provided temporary directory.
	mocker : MockerFixture
		pytest-mock fixture for patching.

	Returns
	-------
	None
	"""
	mock_log = mocker.patch("src.controller._pipeline.log_message")
	cls_webhook = Mock(spec=WebhookNotifier)
	_build_orchestrator(tmp_path, cls_webhook=cls_webhook)._notify()
	str_log = "\n".join(call.args[1] for call in mock_log.call_args_list)
	assert str_log.index("payload composed") < str_log.index("Sending webhook")


def test_notify_sends_through_webhook_when_configured(tmp_path: Path) -> None:
	"""The injected webhook's ``send`` is called with the composed message.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest-provided temporary directory.

	Returns
	-------
	None
	"""
	cls_webhook = Mock(spec=WebhookNotifier)
	_build_orchestrator(tmp_path, cls_webhook=cls_webhook)._notify()
	cls_webhook.send.assert_called_once_with("hello notification")
