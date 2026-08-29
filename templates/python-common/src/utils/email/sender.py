"""E-mail sending orchestration — resolve dispatch policy, then hand off to an injected sender.

The seam a caller uses to send ONE e-mail block: it asks :func:`utils.email.dispatch.resolve_
dispatch` whether the block may send at all, converts the body via
:func:`utils.email.html_body.to_html_body`, and — only when dispatch allows it — calls the
injected ``fn_send_email`` (typically a concrete ``EmailHandler.send_email`` bound method) with
the resolved auto-send flag.

The sender is **injected as a callable**, not as the ``EmailHandler`` port type: this module
ships unconditionally to every tier's ``utils/`` (blueprintx#121), while the port lives beside
its adapters (``chassis.email.domain.ports`` in DDD, ``utils.email.domain.ports`` in MVC via the
webhook-style prefix rewrite) — a location that differs by layout. Importing either would tie
this always-shipped seam to one layout's optional package.
"""

from __future__ import annotations

from collections.abc import Callable
from logging import Logger
from typing import TYPE_CHECKING

from utils.email.dispatch import resolve_dispatch
from utils.email.html_body import to_html_body
from utils.logs import log_message


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). mypy reads the single TYPE_CHECKING
# import (no redefinition); at runtime the try/except picks whichever layout shipped.
if TYPE_CHECKING:
	from utils.typing import type_checker
else:
	try:
		from utils.typing import type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from chassis.typing import type_checker


@type_checker
def send_email_block(  # noqa: PLR0913 — one orchestration call, each argument a real option
	fn_send_email: Callable[[str, list[str], list[str], str, list[str], bool], bool],
	str_block_key: str,
	str_subject: str,
	list_to: list[str],
	list_cc: list[str],
	str_body: str,
	list_attachments: list[str] | None = None,
	logger: Logger | None = None,
) -> bool:
	"""Send one e-mail block, gated by :func:`utils.email.dispatch.resolve_dispatch`.

	Parameters
	----------
	fn_send_email : Callable[[str, list of str, list of str, str, list of str, bool], bool]
		The concrete sender, matching ``EmailHandler.send_email``'s signature — pass a bound
		method such as ``cls_handler.send_email``.
	str_block_key : str
		The ``emails.yaml`` block key controlling this send's dispatch policy.
	str_subject : str
		Subject line.
	list_to : list of str
		Primary recipients.
	list_cc : list of str
		Carbon-copy recipients.
	str_body : str
		Plain-text (or HTML) body; converted via :func:`utils.email.html_body.to_html_body`.
	list_attachments : list of str | None, optional
		File paths to attach; ``None`` sends none.
	logger : logging.Logger | None, optional
		Run logger, forwarded to :func:`~utils.email.dispatch.resolve_dispatch` and used for
		the skip line.

	Returns
	-------
	bool
		``True`` when ``fn_send_email`` was called and dispatched; ``False`` when the block's
		dispatch policy skipped the send.
	"""
	bool_send, bool_auto_send = resolve_dispatch(str_block_key, logger)
	if not bool_send:
		log_message(
			logger, f"[email] block '{str_block_key}' skipped (EMAIL_SEND resolved off)", "info"
		)
		return False
	return fn_send_email(
		str_subject,
		list_to,
		list_cc,
		to_html_body(str_body),
		list_attachments or [],
		bool_auto_send,
	)
