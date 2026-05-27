"""Webhook factory — selects an adapter by platform and returns the port."""

from chassis.webhook.domain.ports import WebhookNotifier
from chassis.webhook.infrastructure.slack_notifier import SlackNotifier
from chassis.webhook.infrastructure.teams_notifier import TeamsNotifier


def build_webhook(str_platform: str, str_url: str) -> WebhookNotifier:
	"""Build a webhook notifier for the given platform.

	Parameters
	----------
	str_platform : str
		Platform key: ``"teams"`` or ``"slack"``.
	str_url : str
		Incoming webhook URL for the chosen platform.

	Returns
	-------
	WebhookNotifier
		An adapter satisfying the notifier port.

	Raises
	------
	ValueError
		If ``str_platform`` is not a registered platform.

	Examples
	--------
	>>> cls_webhook = build_webhook("teams", "https://outlook.office.com/webhook/…")
	>>> cls_webhook.send("Routine finished", str_title="DONE")
	"""
	dict_builders = {
		"teams": TeamsNotifier,
		"slack": SlackNotifier,
	}
	if str_platform not in dict_builders:
		raise ValueError(
			f"Unknown webhook platform '{str_platform}'; "
			f"choose one of {sorted(dict_builders)}"
		)
	return dict_builders[str_platform](str_url)
