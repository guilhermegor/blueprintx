"""E-mail factory — pick the backend from ``EMAIL_BACKEND`` and return the handler port.

Mirrors the webhook factory: the caller depends only on the :class:`EmailHandler` port and
this factory decides the concrete backend. ``EMAIL_BACKEND`` selects it (default ``outlook``);
a blank/``none`` value yields a :class:`NullEmailHandler` (opt-out). The Outlook backend injects
an :class:`~utils.outlook_gateway.OutlookGateway` into :class:`OutlookEmailHandler`; the SMTP
backend reads ``SMTP_*`` settings from the environment (like ``connection_db`` reads ``DB_*``).
"""

from __future__ import annotations

from logging import Logger
import os
from pathlib import Path

from chassis.email.domain.ports import EmailHandler
from chassis.email.infrastructure.null_email_handler import NullEmailHandler
from chassis.email.infrastructure.outlook_email_handler import OutlookEmailHandler
from chassis.email.infrastructure.smtp_email_handler import SmtpEmailHandler
from utils.outlook_gateway import OutlookGateway


_SET_NONE = frozenset({"", "none", "null", "off"})
_TRUE_TOKENS = frozenset({"1", "true", "yes", "on", "y", "t"})


def build_email_handler(
	str_backend: str = "",
	str_sender: str = "",
	path_signatures_dir: Path | None = None,
	logger: Logger | None = None,
) -> EmailHandler:
	"""Build an e-mail handler for the configured backend, returning the port.

	Parameters
	----------
	str_backend : str, optional
		Backend key (``outlook`` / ``smtp`` / ``none``). When blank, ``EMAIL_BACKEND`` is read
		(default ``outlook``). A ``none``/blank backend returns a :class:`NullEmailHandler`.
	str_sender : str, optional
		The sending account. When blank, ``SENDER_EMAIL`` is read. Used by both backends.
	path_signatures_dir : pathlib.Path | None, optional
		Signatures directory passed to the Outlook gateway (ignored by SMTP).
	logger : logging.Logger | None, optional
		Run logger passed to the Outlook gateway.

	Returns
	-------
	EmailHandler
		An adapter satisfying the port (Outlook, SMTP, or no-op ``NullEmailHandler``).

	Raises
	------
	ValueError
		If ``str_backend`` is a non-blank, unknown key.

	Examples
	--------
	>>> cls_email = build_email_handler("outlook", str_sender="ops@example.com")
	>>> cls_email.send_email("Done", ["team@example.com"], [], "Run finished", [])
	"""
	str_resolved = (str_backend or os.getenv("EMAIL_BACKEND", "outlook")).strip().lower()
	str_from = str_sender or os.getenv("SENDER_EMAIL", "")
	if str_resolved in _SET_NONE:
		return NullEmailHandler()
	if str_resolved == "outlook":
		return OutlookEmailHandler(
			OutlookGateway(str_from, path_signatures_dir=path_signatures_dir, logger=logger)
		)
	if str_resolved == "smtp":
		return SmtpEmailHandler(
			str_host=os.getenv("SMTP_HOST", ""),
			int_port=int(os.getenv("SMTP_PORT", "587") or "587"),
			str_sender=str_from,
			str_user=os.getenv("SMTP_USER", ""),
			str_password=os.getenv("SMTP_PASSWORD", ""),
			bool_use_tls=os.getenv("SMTP_USE_TLS", "true").strip().lower() in _TRUE_TOKENS,
		)
	raise ValueError(f"Unsupported EMAIL_BACKEND {str_resolved!r}. Use: outlook, smtp, none.")
