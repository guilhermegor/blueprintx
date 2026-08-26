"""Unit tests for the Outlook e-mail gateway seam (off-Windows behaviour + COM interop)."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from src.utils.ms_office.outlook_gateway import OutlookGateway


def test_send_email_off_windows_is_logonly(mocker: MockerFixture) -> None:
	"""Off Windows, send_email logs and returns False instead of touching Outlook."""
	mocker.patch("src.utils.ms_office.outlook_gateway.running_on_windows", return_value=False)
	cls_gateway = OutlookGateway("sender@example.com")
	bool_sent = cls_gateway.send_email("subject", ["to@example.com"], [], "body", [])
	assert bool_sent is False


def test_download_attachment_off_windows_returns_none(
	mocker: MockerFixture, tmp_path: Path
) -> None:
	"""Off Windows, download_attachment logs and returns None."""
	mocker.patch("src.utils.ms_office.outlook_gateway.running_on_windows", return_value=False)
	cls_gateway = OutlookGateway("sender@example.com")
	path_out = cls_gateway.download_attachment("acct", "Inbox", "subject~", tmp_path)
	assert path_out is None


def test_send_email_hands_com_an_absolute_attachment_path(
	mocker: MockerFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A relative attachment reaches Outlook absolute — it does not share our CWD."""
	monkeypatch.chdir(tmp_path)
	mocker.patch("src.utils.ms_office.outlook_gateway.running_on_windows", return_value=True)
	cls_com = mocker.patch("src.utils.ms_office.outlook_gateway._com_send_email")
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
	mocker.patch("src.utils.ms_office.outlook_gateway.running_on_windows", return_value=True)
	cls_com = mocker.patch(
		"src.utils.ms_office.outlook_gateway._com_download_attch", return_value={}
	)
	cls_gateway = OutlookGateway("sender@example.com")
	cls_gateway.download_attachment("acct", "Inbox", "subject~", Path("downloads"))
	assert Path(cls_com.call_args.kwargs["str_dest_dir"]).is_absolute()
