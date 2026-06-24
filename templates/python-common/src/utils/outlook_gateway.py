"""Outlook e-mail gateway — the seam over stpstone's Windows-only Outlook client.

Reach e-mail only through this gateway, never the vendor SDK directly, so a vendor change
is confined here (the library-coupling rule). stpstone's ``DealingOutlook`` requires Windows
(it imports ``win32com`` and raises elsewhere), so it is imported **lazily** inside the send
call and the whole module stays importable on Linux/CI. Off Windows the gateway logs what it
*would* send and returns ``False``/``None`` instead of failing — the run continues.

Deliberately decoupled from ``utils.typing`` so it stays portable across the ``utils.typing``
(MVC) and ``chassis.typing`` (DDD) layouts, like the other shared ``utils`` helpers.
"""

from __future__ import annotations

from logging import Logger
import os
from pathlib import Path
import platform
from typing import Any

from utils.loggers import log_message
from utils.signatures import resolve_signature


class OutlookGateway:
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
		_build_dealing_outlook().send_email(
			mail_subject=str_subject,
			mail_to="; ".join(list_to),
			mail_cc="; ".join(list_cc),
			mail_body=to_html_body(str_body),
			mail_attachments=list_attachments,
			send_behalf_of=self.str_sender,
			auto_send_email=bool_auto_send,
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
			dict_status = _build_dealing_outlook().download_attch(
				email_account=str_email_account,
				outlook_folder=str_folder,
				subj_sub_string=str_subject_substring,
				attch_save_path=str(path_dest_dir),
				bool_save_file_w_original_name=True,
				list_fileformat=list_formats,
				outlook_subfolder=str_subfolder,
				save_only_first_event=True,
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


def to_html_body(str_body: str) -> str:
	r"""Convert a plain-text e-mail body to HTML so its line breaks survive.

	stpstone's ``DealingOutlook`` assigns the body to ``mail.HTMLBody``, where bare newlines
	collapse and the message renders on a single line. Each newline is turned into a ``<br>``
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


def running_on_windows() -> bool:
	"""Return whether the current OS is Windows (where Outlook is available).

	Returns
	-------
	bool
		``True`` on Windows.
	"""
	return platform.system() == "Windows"


def _build_dealing_outlook() -> Any:  # noqa: ANN401 — opaque vendor client (Windows only)
	"""Lazily build stpstone's Outlook client (imported only on Windows).

	Returns
	-------
	Any
		A ``stpstone.utils.microsoft_apps.outlook.DealingOutlook`` instance.
	"""
	from stpstone.utils.microsoft_apps.outlook import DealingOutlook

	return DealingOutlook()
