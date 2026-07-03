"""Microsoft Teams webhook adapter.

This adapter satisfies the ``WebhookNotifier`` port (see ``domain/ports.py``). The transport
uses ``pymsteams`` (the same client stpstone wrapped internally), so a notification is an
incoming-webhook connector card with a title and text body. A send failure raises rather than
being swallowed, matching the Slack adapter; the caller decides whether to send at all via the
``WEBHOOK_ENV_GATE`` environment check.
"""

import pymsteams


class TeamsNotifier:
	"""Adapter that posts notifications to a Microsoft Teams incoming webhook."""

	def _validate_url(self, str_url: str) -> None:
		"""Validate the webhook URL format.

		Parameters
		----------
		str_url : str
			Microsoft Teams incoming webhook URL to validate.

		Raises
		------
		ValueError
			If the URL is empty or does not start with ``https://``.
		"""
		if not str_url:
			raise ValueError("Webhook URL cannot be empty")
		if not str_url.startswith("https://"):
			raise ValueError("Webhook URL must start with https://")

	def __init__(self, str_url: str) -> None:
		"""Store and validate the configured Teams webhook URL.

		Parameters
		----------
		str_url : str
			Microsoft Teams incoming webhook URL.
		"""
		self._validate_url(str_url)
		self._str_url = str_url

	def send(self, str_message: str, str_title: str = "ROUTINE_CONCLUSION") -> None:
		"""Post a message to the configured Teams channel.

		Parameters
		----------
		str_message : str
			Message body to deliver.
		str_title : str, optional
			Message title/subject.

		Raises
		------
		ValueError
			If the message is empty, or the send fails.
		"""
		if not str_message:
			raise ValueError("Message cannot be empty")

		cls_card = pymsteams.connectorcard(self._str_url)
		cls_card.title(str_title)
		cls_card.text(str_message)
		try:
			cls_card.send()
		except Exception as err:
			raise ValueError(f"Failed to send Teams message: {err}") from err
