"""Outlook e-mail gateway — the single in-repo seam for Microsoft Outlook.

Reach e-mail only through this gateway (the library-coupling rule). The Outlook COM operations
live here as private ``_com_*`` functions that **lazy-import** ``win32com`` inside the call, so
the module stays importable on Linux/CI even though ``win32com`` is Windows-only. Off Windows the
gateway logs what it *would* do and returns ``False``/``None`` instead of failing — the run
continues.
"""

from __future__ import annotations

from logging import Logger
import os
from pathlib import Path
import platform
from typing import TYPE_CHECKING

from utils.logs import log_message
from utils.signatures import resolve_signature


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). mypy reads the single TYPE_CHECKING
# import (no redefinition); at runtime the try/except picks whichever layout shipped.
if TYPE_CHECKING:
	from utils.typing import TypeChecker, type_checker
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
		_com_send_email(
			str_subject=str_subject,
			str_to="; ".join(list_to),
			str_cc="; ".join(list_cc),
			str_body=to_html_body(str_body),
			list_attachments=list_attachments,
			str_send_behalf_of=self.str_sender,
			bool_auto_send=bool_auto_send,
			str_html_signature=str_signature,
		)
		log_message(self.logger, f"[email] sent. subject='{str_subject}' to={list_to}")
		return True

	def download_attachment(
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
			dict_status = _com_download_attch(
				str_email_account=str_email_account,
				str_folder=str_folder,
				str_subject_substring=str_subject_substring,
				str_dest_dir=str(path_dest_dir),
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

	def get_body_content(
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
def to_html_body(str_body: str) -> str:
	r"""Convert a plain-text e-mail body to HTML so its line breaks survive.

	The Outlook client assigns the body to ``mail.HTMLBody``, where bare newlines collapse and
	the message renders on a single line. Each newline is turned into a ``<br>``
	so paragraph breaks are preserved. A body that already looks like HTML (contains a ``<br``
	or ``<p>`` tag) is left untouched.

	Parameters
	----------
	str_body : str
		The plain-text body (possibly with ``\n`` / ``\r\n`` line breaks).

	Returns
	-------
	str
		The body with newlines rendered as ``<br>`` (unchanged when already HTML).
	"""
	str_low = str_body.casefold()
	if "<br" in str_low or "<p>" in str_low:
		return str_body
	return str_body.replace("\r\n", "\n").replace("\n", "<br>\n")


# E-mail dispatch flags live in the environment (.env), one pair per e-mail block, so ops
# toggles a notification without editing config. Per-block variables are
# EMAIL_SEND__<BLOCK> / EMAIL_AUTO_SEND__<BLOCK> (the block key upper-cased); an unset
# per-block variable falls back to EMAIL_SEND__DEFAULTS / EMAIL_AUTO_SEND__DEFAULTS, then to
# the hard default (send on, auto-send off).
_DISPATCH_DEFAULT_SUFFIX: str = "DEFAULTS"
_TRUE_TOKENS: frozenset[str] = frozenset({"1", "true", "yes", "on", "y", "t"})
_FALSE_TOKENS: frozenset[str] = frozenset({"0", "false", "no", "off", "n", "f"})


@type_checker
def _parse_env_bool(str_raw: str | None, bool_default: bool) -> bool:
	"""Parse an environment flag to ``bool``, returning ``bool_default`` when absent/unknown.

	Parameters
	----------
	str_raw : str | None
		The raw environment value (``None`` when the variable is unset).
	bool_default : bool
		The value returned when ``str_raw`` is ``None``, blank, or not a known token.

	Returns
	-------
	bool
		The parsed flag, or ``bool_default``.
	"""
	if str_raw is None:
		return bool_default
	str_norm = str_raw.strip().casefold()
	if str_norm in _TRUE_TOKENS:
		return True
	if str_norm in _FALSE_TOKENS:
		return False
	return bool_default


@type_checker
def _dispatch_flag(str_prefix: str, str_block_key: str, bool_default: bool) -> bool:
	"""Resolve one dispatch flag from the per-block then the default environment variable.

	Parameters
	----------
	str_prefix : str
		The variable prefix (``"EMAIL_SEND"`` or ``"EMAIL_AUTO_SEND"``).
	str_block_key : str
		The ``emails.yaml`` block key (e.g. ``"schema_failure"``); upper-cased for the var.
	bool_default : bool
		The hard default when neither the per-block nor the ``__DEFAULTS`` variable is set.

	Returns
	-------
	bool
		The resolved flag.
	"""
	str_block_var = os.getenv(f"{str_prefix}__{str_block_key.upper()}")
	if str_block_var is not None and str_block_var.strip():
		return _parse_env_bool(str_block_var, bool_default)
	str_default_var = os.getenv(f"{str_prefix}__{_DISPATCH_DEFAULT_SUFFIX}")
	return _parse_env_bool(str_default_var, bool_default)


@type_checker
def resolve_dispatch(str_block_key: str) -> tuple[bool, bool]:
	"""Resolve an e-mail block's ``(send, auto_send)`` flags from the environment.

	The flags are sourced from ``.env`` (loaded at startup), never from ``emails.yaml``: per
	block ``EMAIL_SEND__<BLOCK>`` / ``EMAIL_AUTO_SEND__<BLOCK>`` (block key upper-cased), with
	``EMAIL_SEND__DEFAULTS`` / ``EMAIL_AUTO_SEND__DEFAULTS`` as the fallback and a hard default
	of send on / auto-send off.

	Parameters
	----------
	str_block_key : str
		The ``emails.yaml`` block key (e.g. ``"schema_failure"``).

	Returns
	-------
	tuple of (bool, bool)
		``(bool_send, bool_auto_send)``.
	"""
	bool_send = _dispatch_flag("EMAIL_SEND", str_block_key, True)
	bool_auto_send = _dispatch_flag("EMAIL_AUTO_SEND", str_block_key, False)
	return bool_send, bool_auto_send


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
def _com_send_email(
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
def _com_download_attch(
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
def _com_get_body_content(
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
