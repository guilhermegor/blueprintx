"""No-op webhook adapter — the opt-out path when no URL is configured."""


class NullNotifier:
	"""Null-object adapter satisfying the ``WebhookNotifier`` port.

	Returned when no ``WEBHOOK_URL`` is configured so the notifier can always be
	built and passed around without a live URL. :meth:`send` does nothing, so the
	webhook is effectively opted out regardless of the environment gate.
	"""

	def send(self, str_message: str, str_title: str = "ROUTINE_CONCLUSION") -> None:
		"""Discard the notification (no URL configured).

		Parameters
		----------
		str_message : str
			Message body (ignored).
		str_title : str, optional
			Message title/subject (ignored).
		"""
