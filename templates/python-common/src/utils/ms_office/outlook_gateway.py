"""Outlook e-mail gateway — the single in-repo seam for Microsoft Outlook.

Reach e-mail only through this gateway (the library-coupling rule). The Outlook COM operations
live here as private ``_com_*`` functions that **lazy-import** ``win32com`` inside the call, so
the module stays importable on Linux/CI even though ``win32com`` is Windows-only. Off Windows the
gateway logs what it *would* do and returns ``False``/``None`` instead of failing — the run
continues.

Lives in ``utils/ms_office/`` — a vendor-app-scoped subpackage (blueprintx#118) — because this
is *Outlook* behaviour: a Windows COM client automated to send and read mail. Dispatch policy
(:func:`utils.email.dispatch.resolve_dispatch`) and body HTML-ization
(:func:`utils.email.html_body.to_html_body`) are capabilities *any* e-mail backend needs (SMTP
included), so they live in ``utils/email/`` instead — a port must not carry logic one adapter
happens to implement.
"""

from __future__ import annotations

from logging import Logger
import os
from pathlib import Path
import platform
from typing import TYPE_CHECKING

from utils.email.html_body import to_html_body
from utils.logs import log_message
from utils.paths import to_absolute
from utils.signatures import resolve_signature


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). TYPE_CHECKING stubs the decorator's shape
# locally instead of importing: mypy treats a try/except import as executed code and flags
# the redefinition once actually checked, so this branch can't pick either layout
# (blueprintx#360). Runtime still resolves the real engine via try/except below.
if TYPE_CHECKING:
	from collections.abc import Callable
	from typing import TypeVar

	_F = TypeVar("_F", bound=Callable[..., object])

	def type_checker(fn: _F) -> _F:
		"""Type-only stub — see src/utils/CLAUDE.md."""

	class TypeChecker(type):
		"""Type-only stub — see src/utils/CLAUDE.md."""
else:
	try:
		from utils.typing import TypeChecker, type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from chassis.typing import TypeChecker, type_checker


class OutlookGateway(metaclass=TypeChecker):
	"""Send e-mails through the local Outlook desktop app (Windows), else log-only.

	Parameters
	----------
	str_sender : str
		The sending account (used as send-on-behalf-of).
	path_signatures_dir : pathlib.Path | None
		Directory holding ``<sender>.html`` / ``default.html``; when set, the matching HTML
		signature is attached to every e-mail.
	logger : logging.Logger | None
		Run logger for the audit lines.
	"""

	def __init__(
		self,
		str_sender: str,
		path_signatures_dir: Path | None = None,
		logger: Logger | None = None,
	) -> None:
		self.str_sender = str_sender
		self.path_signatures_dir = path_signatures_dir
		self.logger = logger

	def send_email(
		self,
		str_subject: str,
		list_to: list[str],
		list_cc: list[str],
		str_body: str,
		list_attachments: list[str],
		bool_auto_send: bool = True,
	) -> bool:
		"""Send one e-mail; return whether it was actually dispatched.

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
			``True`` when dispatched via Outlook; ``False`` off Windows (logged).
		"""
		if not running_on_windows():
			log_message(
				self.logger,
				f"[email] Outlook unavailable (non-Windows); e-mail NOT sent. "
				f"subject='{str_subject}' to={list_to} cc={list_cc} "
				f"attachments={list_attachments}",
				"warning",
			)
			return False
		str_signature = (
			resolve_signature(self.path_signatures_dir, self.str_sender)
			if self.path_signatures_dir is not None
			else ""
		)
		# Outlook runs as its own process, so a relative attachment path re-anchors in ITS
		# working directory rather than ours, and on Windows a driveless path re-anchors to
		# whichever drive it sits on. The existence check downstream runs in our process, so
		# it passes and the attachment is then silently dropped.
		list_attachments_abs = [str(to_absolute(Path(str_path))) for str_path in list_attachments]
		_com_send_email(
			str_subject=str_subject,
			str_to="; ".join(list_to),
			str_cc="; ".join(list_cc),
			str_body=to_html_body(str_body),
			list_attachments=list_attachments_abs,
			str_send_behalf_of=self.str_sender,
			bool_auto_send=bool_auto_send,
			str_html_signature=str_signature,
		)
		log_message(self.logger, f"[email] sent. subject='{str_subject}' to={list_to}")
		return True

	def download_attachment(  # complexity-ok: COM interop, non-fatal degradation
		self,
		str_email_account: str,
		str_folder: str,
		str_subject_substring: str,
		path_dest_dir: Path,
		str_subfolder: str | None = None,
		list_file_formats: list[str] | None = None,
	) -> Path | None:
		"""Save the first matching e-mail's attachment into ``path_dest_dir`` (original name).

		Reads ``email_account -> folder -> optional subfolder`` via the local Outlook session,
		finds the first message whose subject contains ``str_subject_substring``, and saves its
		attachment(s) of the allowed formats. **Non-fatal**: off Windows it logs and returns
		``None``; any read/save failure is caught, logged, and also returns ``None`` so the
		caller can fall back.

		Parameters
		----------
		str_email_account : str
			The Outlook account/store name (top-level folder in the MAPI namespace).
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
			The saved attachment path on success; ``None`` off Windows or on any failure / no
			match (all logged).
		"""
		list_formats = list_file_formats or ["xlsx"]
		if not running_on_windows():
			log_message(
				self.logger,
				f"[email] Outlook unavailable (non-Windows); download NOT performed. "
				f"account='{str_email_account}' folder='{str_folder}' "
				f"subject~='{str_subject_substring}'",
				"warning",
			)
			return None
		try:
			dict_status = _com_download_attachment(
				str_email_account=str_email_account,
				str_folder=str_folder,
				str_subject_substring=str_subject_substring,
				# Outlook writes the file itself; a driveless destination lands on ITS drive
				# while our existence check looks at ours -- a false failure reported over a
				# file that really did save.
				str_dest_dir=str(to_absolute(path_dest_dir)),
				list_file_formats=list_formats,
				str_subfolder=str_subfolder,
			)
		except Exception as cls_err:  # noqa: BLE001 — e-mail download is optional; caller falls back.
			log_message(
				self.logger,
				f"[email] download failed (account='{str_email_account}' folder='{str_folder}' "
				f"subject~='{str_subject_substring}'): {cls_err}",
				"warning",
			)
			return None
		for str_path, bool_saved in dict_status.items():
			if bool_saved:
				log_message(
					self.logger,
					f"[email] attachment downloaded: {str_path} "
					f"(subject~='{str_subject_substring}')",
				)
				return Path(str_path)
		log_message(
			self.logger,
			f"[email] no matching attachment (folder='{str_folder}' "
			f"subject~='{str_subject_substring}')",
			"warning",
		)
		return None

	# ⚠️ The COM helpers below carry the complexity hatch, for one reason stated once here.
	# They are Windows COM interop with NON-FATAL degradation. Every branch is a platform
	# guard, an optional field the COM object may or may not expose, or a failure that has to
	# be logged and survived rather than raised. That last property is the whole contract of
	# this gateway, since a mail integration that dies takes the routine down with it, so
	# collapsing those branches would trade a documented, survivable path for a shorter one.
	def get_body_content(  # complexity-ok: COM interop, non-fatal degradation
		self,
		str_email_account: str,
		str_folder: str,
		str_subject_substring: str,
		str_subfolder: str | None = None,
	) -> list[dict[str, object]]:
		"""Return the body and metadata of e-mails whose subject contains a substring.

		**Non-fatal**: off Windows, or on any read failure, logs and returns an empty list so
		the caller can proceed.

		Parameters
		----------
		str_email_account : str
			The Outlook account/store name (top-level folder in the MAPI namespace).
		str_folder : str
			The mail folder to search under the account.
		str_subject_substring : str
			Substring the message subject must contain.
		str_subfolder : str | None
			Optional subfolder under ``str_folder``.

		Returns
		-------
		list[dict[str, object]]
			One dict per matching message (``subject`` / ``last_edition`` / ``creation_time`` /
			``body``); empty off Windows or on any failure (all logged).
		"""
		if not running_on_windows():
			log_message(
				self.logger,
				f"[email] Outlook unavailable (non-Windows); body read skipped. "
				f"account='{str_email_account}' folder='{str_folder}' "
				f"subject~='{str_subject_substring}'",
				"warning",
			)
			return []
		try:
			return _com_get_body_content(
				str_email_account=str_email_account,
				str_folder=str_folder,
				str_subject_substring=str_subject_substring,
				str_subfolder=str_subfolder,
			)
		except Exception as cls_err:  # noqa: BLE001 — body read is optional; caller handles empties.
			log_message(
				self.logger,
				f"[email] body read failed (account='{str_email_account}' folder='{str_folder}' "
				f"subject~='{str_subject_substring}'): {cls_err}",
				"warning",
			)
			return []


@type_checker
def running_on_windows() -> bool:
	"""Return whether the current OS is Windows (where Outlook is available).

	Returns
	-------
	bool
		``True`` on Windows.
	"""
	return platform.system() == "Windows"


@type_checker
def _com_send_email(  # complexity-ok: COM interop, optional fields and non-fatal failures
	str_subject: str,
	str_to: str,
	str_cc: str,
	str_body: str,
	list_attachments: list[str],
	str_send_behalf_of: str,
	bool_auto_send: bool,
	str_html_signature: str,
) -> None:
	"""Compose and send one e-mail through the local Outlook app (COM, Windows only).

	Parameters
	----------
	str_subject : str
		Subject line.
	str_to : str
		Semicolon-joined primary recipients.
	str_cc : str
		Semicolon-joined CC recipients.
	str_body : str
		HTML body.
	list_attachments : list of str
		File paths to attach (each skipped when missing on disk).
	str_send_behalf_of : str
		Account to send on behalf of.
	bool_auto_send : bool
		Send without opening the compose window.
	str_html_signature : str
		HTML signature appended to the body (may be empty).

	Raises
	------
	RuntimeError
		If the auto-send fails.
	"""
	import win32com.client as win32

	cls_outlook = win32.Dispatch("outlook.application")
	cls_mail = cls_outlook.CreateItem(0)
	if str_to:
		cls_mail.To = str_to
	if str_cc:
		cls_mail.CC = str_cc
	cls_mail.Subject = str_subject
	if str_send_behalf_of:
		cls_account = None
		for cls_candidate in cls_outlook.Session.Accounts:
			if str(cls_candidate) == str_send_behalf_of:
				cls_account = cls_candidate
				break
		if cls_account is not None:
			cls_mail._oleobj_.Invoke(*(64209, 0, 8, 0, cls_account))
		cls_mail.SentOnBehalfOfName = str_send_behalf_of
	cls_mail.HTMLBody = str_body + str_html_signature
	for str_attachment in list_attachments:
		if os.path.exists(str_attachment):
			cls_mail.Attachments.Add(Source=str_attachment)
	if not bool_auto_send:
		cls_mail.Display()
		return
	try:
		cls_mail.Send()
	except Exception as cls_err:
		raise RuntimeError(f"Failed to send email: {cls_err}") from cls_err


@type_checker
def _com_download_attachment(  # complexity-ok: COM interop, non-fatal degradation
	str_email_account: str,
	str_folder: str,
	str_subject_substring: str,
	str_dest_dir: str,
	list_file_formats: list[str],
	str_subfolder: str | None = None,
) -> dict[str, bool]:
	"""Save the first matching e-mail's attachment (original name) via Outlook COM (Windows only).

	Parameters
	----------
	str_email_account : str
		Outlook account name (top-level MAPI folder).
	str_folder : str
		Mail folder to search under the account.
	str_subject_substring : str
		Substring the message subject must contain.
	str_dest_dir : str
		Destination directory for the attachments.
	list_file_formats : list of str
		Allowed extensions without the dot.
	str_subfolder : str | None
		Optional subfolder under ``str_folder`` (default: ``None``).

	Returns
	-------
	dict[str, bool]
		Mapping of the saved path to whether the file now exists; returns after the first save.
	"""
	import win32com.client as win32

	cls_app = win32.Dispatch("Outlook.Application")
	cls_namespace = cls_app.GetNamespace("MAPI")
	if str_subfolder:
		cls_folder = (
			cls_namespace.Folders[str_email_account].Folders[str_folder].Folders[str_subfolder]
		)
	else:
		cls_folder = cls_namespace.Folders[str_email_account].Folders[str_folder]
	dict_status: dict[str, bool] = {}
	int_count = cls_folder.Items.Count
	for int_i in range(int_count):
		cls_message = cls_folder.Items[int_i]
		if str_subject_substring not in cls_message.Subject:
			continue
		for cls_attach in cls_message.Attachments:
			if cls_attach.FileName.split(".")[-1] in list_file_formats:
				str_full_path = os.path.join(str_dest_dir, cls_attach.FileName)
				cls_attach.SaveAsFile(str_full_path)
				dict_status[str_full_path] = os.path.exists(str_full_path)
				return dict_status
	return dict_status


@type_checker
def _com_get_body_content(  # complexity-ok: COM interop, non-fatal degradation
	str_email_account: str,
	str_folder: str,
	str_subject_substring: str,
	str_subfolder: str | None = None,
) -> list[dict[str, object]]:
	"""Read body + metadata of matching e-mails via Outlook COM (Windows only).

	Parameters
	----------
	str_email_account : str
		Outlook account name (top-level MAPI folder).
	str_folder : str
		Mail folder to search under the account.
	str_subject_substring : str
		Substring the message subject must contain.
	str_subfolder : str | None
		Optional subfolder under ``str_folder`` (default: ``None``).

	Returns
	-------
	list[dict[str, object]]
		One dict per matching message with ``subject`` / ``last_edition`` / ``creation_time`` /
		``body`` keys.
	"""
	import win32com.client as win32

	cls_app = win32.Dispatch("Outlook.Application")
	cls_namespace = cls_app.GetNamespace("MAPI")
	if str_subfolder:
		cls_folder = (
			cls_namespace.Folders[str_email_account].Folders[str_folder].Folders[str_subfolder]
		)
	else:
		cls_folder = cls_namespace.Folders[str_email_account].Folders[str_folder]
	list_content: list[dict[str, object]] = []
	int_count = cls_folder.Items.Count
	for int_i in range(int_count):
		cls_message = cls_folder.Items[int_i]
		if str_subject_substring in cls_message.Subject:
			list_content.append(
				{
					"subject": cls_message.Subject,
					"last_edition": cls_message.LastModificationTime,
					"creation_time": cls_message.CreationTime,
					"body": cls_message.body,
				}
			)
	return list_content
