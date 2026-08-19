"""Unit tests for the Outlook e-mail gateway seam (off-Windows behaviour + helpers)."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from src.utils.outlook_gateway import OutlookGateway, resolve_dispatch, to_html_body


def test_send_email_off_windows_is_logonly(mocker: MockerFixture) -> None:
	"""Off Windows, send_email logs and returns False instead of touching Outlook."""
	mocker.patch("src.utils.outlook_gateway.running_on_windows", return_value=False)
	cls_gateway = OutlookGateway("sender@example.com")
	bool_sent = cls_gateway.send_email("subject", ["to@example.com"], [], "body", [])
	assert bool_sent is False


def test_download_attachment_off_windows_returns_none(
	mocker: MockerFixture, tmp_path: Path
) -> None:
	"""Off Windows, download_attachment logs and returns None."""
	mocker.patch("src.utils.outlook_gateway.running_on_windows", return_value=False)
	cls_gateway = OutlookGateway("sender@example.com")
	path_out = cls_gateway.download_attachment("acct", "Inbox", "subject~", tmp_path)
	assert path_out is None


def test_to_html_body_converts_newlines() -> None:
	"""Plain-text newlines become <br>; already-HTML bodies are left untouched."""
	assert "<br>" in to_html_body("line one\nline two")
	assert to_html_body("<p>already html</p>") == "<p>already html</p>"


def test_resolve_dispatch_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Per-block env flags override; absent flags fall back to the hard defaults."""
	monkeypatch.setenv("EMAIL_SEND__REPORT", "no")
	monkeypatch.setenv("EMAIL_AUTO_SEND__REPORT", "yes")
	bool_send, bool_auto = resolve_dispatch("report")
	assert bool_send is False
	assert bool_auto is True
	monkeypatch.delenv("EMAIL_SEND__DEFAULTS", raising=False)
	monkeypatch.delenv("EMAIL_AUTO_SEND__DEFAULTS", raising=False)
	assert resolve_dispatch("other") == (True, False)


def test_send_email_hands_com_an_absolute_attachment_path(
	mocker: MockerFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A relative attachment reaches Outlook absolute — it does not share our CWD."""
	monkeypatch.chdir(tmp_path)
	mocker.patch("src.utils.outlook_gateway.running_on_windows", return_value=True)
	cls_com = mocker.patch("src.utils.outlook_gateway._com_send_email")
	cls_gateway = OutlookGateway("sender@example.com")
	cls_gateway.send_email("subject", ["to@example.com"], [], "body", ["out/report.xlsx"])
	list_sent = cls_com.call_args.kwargs["list_attachments"]
	assert Path(list_sent[0]).is_absolute()
	assert Path(list_sent[0]).name == "report.xlsx"


def test_download_attachment_hands_com_an_absolute_dest_dir(
	mocker: MockerFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""The COM save destination is absolute, so exists() and Outlook look at the same file."""
	monkeypatch.chdir(tmp_path)
	mocker.patch("src.utils.outlook_gateway.running_on_windows", return_value=True)
	cls_com = mocker.patch("src.utils.outlook_gateway._com_download_attch", return_value={})
	cls_gateway = OutlookGateway("sender@example.com")
	cls_gateway.download_attachment("acct", "Inbox", "subject~", Path("downloads"))
	assert Path(cls_com.call_args.kwargs["str_dest_dir"]).is_absolute()
