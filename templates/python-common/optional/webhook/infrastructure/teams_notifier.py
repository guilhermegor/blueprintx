"""Microsoft Teams webhook adapter."""

from stpstone.utils.webhooks.teams import WebhookTeams


class TeamsNotifier:
	"""Adapter mapping the ``WebhookNotifier`` port onto stpstone's ``WebhookTeams``."""

	def __init__(self, str_url: str) -> None:
		"""Store the configured Teams webhook URL.

		Parameters
		----------
		str_url : str
			Microsoft Teams incoming webhook URL.
		"""
		self._cls_teams = WebhookTeams(str_url)

	def send(self, str_message: str, str_title: str = "ROUTINE_CONCLUSION") -> None:
		"""Send a message to the configured Teams channel.

		Parameters
		----------
		str_message : str
			Message body to deliver.
		str_title : str, optional
			Message title/subject.
		"""
		self._cls_teams.send_message(str_msg=str_message, str_title=str_title)
