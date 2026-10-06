"""Unit tests for the opt-in e-mail handler seam (factory selection + backend behaviour)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from chassis.email.factory import build_email_handler
from chassis.email.infrastructure.null_email_handler import NullEmailHandler
from chassis.email.infrastructure.outlook_email_handler import OutlookEmailHandler
from chassis.email.infrastructure.smtp_email_handler import SmtpEmailHandler


@pytest.mark.parametrize("str_backend", ["none", "off"])
def test_build_email_handler_opt_out_returns_null(str_backend: str) -> None:
	"""Every opt-out backend key resolves to a NullEmailHandler."""
	assert isinstance(build_email_handler(str_backend), NullEmailHandler)


@pytest.mark.parametrize("str_backend", ["", "outlook"])
def test_build_email_handler_default_is_outlook(str_backend: str) -> None:
	"""An empty or explicit outlook key resolves to the Outlook handler (the default)."""
	assert isinstance(build_email_handler(str_backend), OutlookEmailHandler)


def test_build_email_handler_smtp_selected() -> None:
	"""The smtp key resolves to the SMTP handler."""
	assert isinstance(build_email_handler("smtp", str_sender="ops@example.com"), SmtpEmailHandler)


def test_build_email_handler_unknown_backend_raises() -> None:
	"""An unknown backend key fails loud rather than silently picking a default."""
	with pytest.raises(ValueError, match="Unsupported EMAIL_BACKEND"):
		build_email_handler("carrier-pigeon")


def test_null_handler_send_email_returns_false() -> None:
	"""The opt-out handler dispatches nothing and reports False."""
	cls_null = NullEmailHandler()
	assert cls_null.send_email("subject", ["to@example.com"], [], "body", []) is False


def test_smtp_handler_rejects_missing_recipients() -> None:
	"""SMTP refuses to send with no to/cc recipients."""
	cls_smtp = SmtpEmailHandler("smtp.example.com", 587, "from@example.com")
	with pytest.raises(ValueError, match="no recipients"):
		cls_smtp.send_email("subject", [], [], "body", [])


def test_smtp_handler_rejects_unconfigured_host() -> None:
	"""SMTP refuses to send when the host/sender is unconfigured."""
	cls_smtp = SmtpEmailHandler("", 587, "")
	with pytest.raises(ValueError, match="host and sender"):
		cls_smtp.send_email("subject", ["to@example.com"], [], "body", [])


def test_outlook_handler_delegates_send_and_download(tmp_path: Path) -> None:
	"""The Outlook handler forwards send_email and download_attachment to the gateway."""
	cls_gateway = MagicMock()
	cls_gateway.send_email.return_value = True
	cls_gateway.download_attachment.return_value = tmp_path / "out.xlsx"
	cls_handler = OutlookEmailHandler(cls_gateway)

	assert cls_handler.send_email("subject", ["to@example.com"], [], "body", []) is True
	cls_gateway.send_email.assert_called_once()

	cls_handler.download_attachment("acct", "Inbox", "subject~", tmp_path)
	cls_gateway.download_attachment.assert_called_once()
