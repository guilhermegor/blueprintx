"""E-mail handler port."""

from typing import Protocol, runtime_checkable


# ``@runtime_checkable`` is required, not cosmetic: the runtime type-checking engine
# performs an ``isinstance`` against this port, and a plain ``Protocol`` raises
# ``TypeError`` on that check — at import time, not call time.
@runtime_checkable
class EmailHandler(Protocol):
	"""Structural contract for outbound e-mail, shared across backends.

	Infrastructure adapters (Outlook, SMTP, null) satisfy this Protocol by duck typing — they
	need not import or inherit from it. The consumer (controller/orchestrator) depends only on
	this port, so swapping the backend (Outlook ↔ SMTP) never changes the caller.

	The port holds only what **every** backend can do — sending — because SMTP is send-only.
	A concrete handler may expose more (the Outlook handler also downloads attachments and can
	grow body/table extraction); a consumer that needs those reads depends on the richer
	concrete type, not this shared port.
	"""

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
			Send without manual review where the backend supports it, by default ``True``.

		Returns
		-------
		bool
			``True`` when dispatched; ``False`` when not (e.g. off-platform, opted out).
		"""
		...
