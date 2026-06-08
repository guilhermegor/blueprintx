"""Slack webhook adapter.

This adapter satisfies the ``WebhookNotifier`` port (see ``domain/ports.py``).
stpstone ships no Slack client, so the transport uses the standard library
(``urllib.request``) to keep the provider dependency-free — Slack incoming
webhooks accept a JSON ``POST`` with a ``text`` field
(see https://api.slack.com/messaging/webhooks).
"""

import json
from urllib import error, request


_HTTP_OK_MIN = 200
_HTTP_OK_MAX = 299
_TIMEOUT_SECONDS = 10


class SlackNotifier:
	"""Adapter that posts notifications to a Slack incoming webhook."""

	def _validate_url(self, str_url: str) -> None:
		"""Validate the webhook URL format.

		Parameters
		----------
		str_url : str
			Slack incoming webhook URL to validate.

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
		"""Store and validate the configured Slack webhook URL.

		Parameters
		----------
		str_url : str
			Slack incoming webhook URL.
		"""
		self._validate_url(str_url)
		self._str_url = str_url

	def send(self, str_message: str, str_title: str = "ROUTINE_CONCLUSION") -> None:
		"""Post a message to the configured Slack channel.

		The title is rendered as a bold first line (Slack ``mrkdwn``), followed
		by the message body. A non-2xx response raises — failures surface rather
		than being swallowed, matching the Teams adapter; the caller decides
		whether to send at all via the ``WEBHOOK_ENV_GATE`` environment check.

		Parameters
		----------
		str_message : str
			Message body to deliver.
		str_title : str, optional
			Message title/subject, rendered bold.

		Raises
		------
		ValueError
			If the message is empty, or the POST fails / returns a non-2xx status.
		"""
		if not str_message:
			raise ValueError("Message cannot be empty")

		bytes_payload = json.dumps({"text": f"*{str_title}*\n{str_message}"}).encode("utf-8")
		# The constructor validates that the URL uses an https scheme, so the S310
		# audit warning about arbitrary schemes does not apply here.
		cls_request = request.Request(  # noqa: S310
			self._str_url,
			data=bytes_payload,
			headers={"Content-Type": "application/json"},
			method="POST",
		)
		try:
			with request.urlopen(cls_request, timeout=_TIMEOUT_SECONDS) as cls_response:  # noqa: S310
				int_status = cls_response.status
		except error.URLError as err:
			raise ValueError(f"Failed to send Slack message: {err}") from err

		if not _HTTP_OK_MIN <= int_status <= _HTTP_OK_MAX:
			raise ValueError(f"Slack webhook returned non-2xx status: {int_status}")
