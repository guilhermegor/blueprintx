"""Webhook notifier port."""

from typing import Protocol


class WebhookNotifier(Protocol):
	"""Structural contract for outbound webhook notifications.

	Infrastructure adapters satisfy this Protocol by duck typing — they need
	not import or inherit from it. ``startup.py`` depends only on this port, so
	swapping the concrete platform (Teams, Slack, …) never changes the caller.
	"""

	def send(self, str_message: str, str_title: str = "ROUTINE_CONCLUSION") -> None:
		"""Deliver a notification.

		Parameters
		----------
		str_message : str
			Message body to deliver.
		str_title : str, optional
			Message title/subject.
		"""
		...
