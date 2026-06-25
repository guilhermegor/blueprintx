"""No-op e-mail adapter — the opt-out path when no backend is configured."""


class NullEmailHandler:
	"""Null-object adapter satisfying the ``EmailHandler`` port.

	Returned when ``EMAIL_BACKEND`` is blank/``none`` so the handler can always be built and
	injected without live settings. :meth:`send_email` does nothing and returns ``False``, so
	e-mail is effectively opted out.
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
		"""Discard the e-mail (no backend configured).

		Parameters
		----------
		str_subject : str
			Subject line (ignored).
		list_to : list of str
			Primary recipients (ignored).
		list_cc : list of str
			Carbon-copy recipients (ignored).
		str_body : str
			Body (ignored).
		list_attachments : list of str
			Attachment paths (ignored).
		bool_auto_send : bool
			Accepted for port parity (ignored).

		Returns
		-------
		bool
			Always ``False`` (nothing dispatched).
		"""
		return False
