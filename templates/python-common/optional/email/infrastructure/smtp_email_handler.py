"""SMTP e-mail adapter — satisfies the ``EmailHandler`` port via the standard library.

A dependency-free **send-only** backend (``smtplib`` + ``email.message``) for hosts without
Outlook (Linux servers, CI, containers). It implements the shared ``send_email`` method, so
it is interchangeable with the Outlook handler behind the port — but it offers no read
methods (download/parse), because SMTP cannot read a mailbox. Connection settings are injected
at construction (read from ``SMTP_*`` env vars by the factory).
"""

from __future__ import annotations

from email.message import EmailMessage
import mimetypes
from pathlib import Path
import smtplib


class SmtpEmailHandler:
	"""Adapter that sends e-mail through an SMTP server using the standard library."""

	def __init__(
		self,
		str_host: str,
		int_port: int,
		str_sender: str,
		str_user: str = "",
		str_password: str = "",
		bool_use_tls: bool = True,
		int_timeout_s: int = 30,
	) -> None:
		"""Store the SMTP connection settings.

		Parameters
		----------
		str_host : str
			SMTP server hostname.
		int_port : int
			SMTP server port (e.g. 587 for STARTTLS, 25 for plain).
		str_sender : str
			The ``From`` address.
		str_user : str, optional
			Login user; when blank, no authentication is attempted (open relay / local MTA).
		str_password : str, optional
			Login password (used only when ``str_user`` is set).
		bool_use_tls : bool, optional
			Issue ``STARTTLS`` before sending, by default ``True``.
		int_timeout_s : int, optional
			Socket timeout in seconds, by default 30.
		"""
		self._str_host = str_host
		self._int_port = int_port
		self._str_sender = str_sender
		self._str_user = str_user
		self._str_password = str_password
		self._bool_use_tls = bool_use_tls
		self._int_timeout_s = int_timeout_s

	def send_email(
		self,
		str_subject: str,
		list_to: list[str],
		list_cc: list[str],
		str_body: str,
		list_attachments: list[str],
		bool_auto_send: bool = True,
	) -> bool:
		"""Send one e-mail through the configured SMTP server.

		Parameters
		----------
		str_subject : str
			Subject line.
		list_to : list of str
			Primary recipients.
		list_cc : list of str
			Carbon-copy recipients.
		str_body : str
			Plain-text body.
		list_attachments : list of str
			File paths to attach (skipped if missing).
		bool_auto_send : bool
			Accepted for port parity; SMTP always sends (there is no compose window).

		Returns
		-------
		bool
			``True`` when the message was handed to the SMTP server.

		Raises
		------
		ValueError
			If the message is empty, has no recipients, or the host/sender is unconfigured.
		OSError
			If the SMTP connection or send fails.
		"""
		if not str_body and not list_attachments:
			raise ValueError("Refusing to send an empty e-mail (no body, no attachments)")
		if not (list_to or list_cc):
			raise ValueError("E-mail has no recipients (to/cc both empty)")
		if not self._str_host or not self._str_sender:
			raise ValueError("SMTP host and sender must be configured")

		cls_message = EmailMessage()
		cls_message["Subject"] = str_subject
		cls_message["From"] = self._str_sender
		cls_message["To"] = ", ".join(list_to)
		if list_cc:
			cls_message["Cc"] = ", ".join(list_cc)
		cls_message.set_content(str_body)
		self._attach_files(cls_message, list_attachments)

		with smtplib.SMTP(self._str_host, self._int_port, timeout=self._int_timeout_s) as cls_smtp:
			if self._bool_use_tls:
				cls_smtp.starttls()
			if self._str_user:
				cls_smtp.login(self._str_user, self._str_password)
			cls_smtp.send_message(cls_message)
		return True

	def _attach_files(self, cls_message: EmailMessage, list_attachments: list[str]) -> None:
		"""Attach each existing file to the message, guessing its MIME type.

		Parameters
		----------
		cls_message : email.message.EmailMessage
			The message being built.
		list_attachments : list of str
			Candidate file paths; a missing path is skipped.
		"""
		for str_path in list_attachments:
			path_file = Path(str_path)
			if not path_file.is_file():
				continue
			str_type, _ = mimetypes.guess_type(str(path_file))
			str_maintype, str_subtype = (
				str_type.split("/", 1) if str_type else ("application", "octet-stream")
			)
			cls_message.add_attachment(
				path_file.read_bytes(),
				maintype=str_maintype,
				subtype=str_subtype,
				filename=path_file.name,
			)
