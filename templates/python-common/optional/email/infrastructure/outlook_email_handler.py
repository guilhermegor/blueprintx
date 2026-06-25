"""Outlook e-mail adapter — satisfies the ``EmailHandler`` port via an injected gateway.

This is the handler the mvc/ddd layer uses by default: the Outlook dependency (the
Windows-only Outlook client, wrapped by ``utils.outlook_gateway.OutlookGateway``) is
**injected** at construction rather than built here, so the handler stays testable and the
vendor coupling lives in the gateway. Off Windows the gateway is log-only, so this handler
degrades the same way (returns ``False`` / ``None`` without raising).

Beyond the shared ``send_email`` (the only method the send-only SMTP backend can also offer),
this handler exposes ``download_attachment`` — a read capability specific to Outlook (which
talks to the local mailbox). Body/table extraction methods can be added here the same way.
"""

from pathlib import Path

from utils.outlook_gateway import OutlookGateway


class OutlookEmailHandler:
	"""Adapter mapping the ``EmailHandler`` port onto an injected ``OutlookGateway``."""

	def __init__(self, cls_gateway: OutlookGateway) -> None:
		"""Store the injected Outlook gateway.

		Parameters
		----------
		cls_gateway : OutlookGateway
			The Outlook dependency (constructed by the caller with the sender account +
			signatures dir + logger), delegated to for send and read operations.
		"""
		self._cls_gateway = cls_gateway

	def send_email(
		self,
		str_subject: str,
		list_to: list[str],
		list_cc: list[str],
		str_body: str,
		list_attachments: list[str],
		bool_auto_send: bool = True,
	) -> bool:
		"""Send one e-mail through the injected Outlook gateway.

		Parameters
		----------
		str_subject : str
			Subject line.
		list_to : list of str
			Primary recipients.
		list_cc : list of str
			Carbon-copy recipients.
		str_body : str
			Plain-text (or HTML) body.
		list_attachments : list of str
			File paths to attach.
		bool_auto_send : bool
			Send without opening the Outlook compose window, by default ``True``.

		Returns
		-------
		bool
			``True`` when dispatched via Outlook; ``False`` off Windows (logged by the gateway).
		"""
		return self._cls_gateway.send_email(
			str_subject, list_to, list_cc, str_body, list_attachments, bool_auto_send
		)

	def download_attachment(
		self,
		str_email_account: str,
		str_folder: str,
		str_subject_substring: str,
		path_dest_dir: Path,
		str_subfolder: str | None = None,
		list_file_formats: list[str] | None = None,
	) -> Path | None:
		"""Save the first matching e-mail's attachment via the injected gateway.

		A read capability beyond the shared ``EmailHandler`` port (SMTP cannot read mail), so a
		consumer that needs it depends on this concrete Outlook handler. Non-fatal off Windows
		(returns ``None``); see :meth:`utils.outlook_gateway.OutlookGateway.download_attachment`.

		Parameters
		----------
		str_email_account : str
			The Outlook account/store name.
		str_folder : str
			The mail folder to search under the account.
		str_subject_substring : str
			Substring the message subject must contain.
		path_dest_dir : pathlib.Path
			Destination directory the attachment is saved into.
		str_subfolder : str | None
			Optional subfolder under ``str_folder``.
		list_file_formats : list of str | None
			Allowed attachment extensions without the dot, by default ``["xlsx"]``.

		Returns
		-------
		pathlib.Path | None
			The saved attachment path, or ``None`` off Windows / on any failure / no match.
		"""
		return self._cls_gateway.download_attachment(
			str_email_account,
			str_folder,
			str_subject_substring,
			path_dest_dir,
			str_subfolder,
			list_file_formats,
		)
