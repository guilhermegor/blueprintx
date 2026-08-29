"""Unit tests for e-mail send orchestration (utils/email/sender.py)."""

import pytest
from pytest_mock import MockerFixture

from src.utils.email.sender import send_email_block


def test_send_email_block_calls_sender_when_dispatch_allows(
	monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
	"""When dispatch resolves send=True, the injected sender is called and its result returned."""
	monkeypatch.setenv("EMAIL_SEND__REPORT", "true")
	fn_send_email = mocker.Mock(return_value=True)
	bool_result = send_email_block(
		fn_send_email, "report", "Subject", ["to@example.com"], [], "line one\nline two"
	)
	assert bool_result is True
	assert "<br>" in fn_send_email.call_args.args[3]  # body was HTML-ized


def test_send_email_block_skips_sender_when_dispatch_denies(
	monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
	"""When dispatch resolves send=False, the injected sender is never called."""
	monkeypatch.setenv("EMAIL_SEND__REPORT", "false")
	fn_send_email = mocker.Mock(return_value=True)
	bool_result = send_email_block(
		fn_send_email, "report", "Subject", ["to@example.com"], [], "body"
	)
	assert bool_result is False
	fn_send_email.assert_not_called()
