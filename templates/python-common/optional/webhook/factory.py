"""Webhook factory — detect the platform from the URL and return the port.

The platform is inferred from the URL (it is redundant to configure both), so the
caller passes only ``WEBHOOK_URL``. A blank URL yields a :class:`NullNotifier`
(opt-out) instead of crashing an adapter constructor that requires a live URL.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from chassis.webhook.domain.ports import WebhookNotifier
from chassis.webhook.infrastructure.null_notifier import NullNotifier
from chassis.webhook.infrastructure.slack_notifier import SlackNotifier
from chassis.webhook.infrastructure.teams_notifier import TeamsNotifier


if TYPE_CHECKING:
    from typing import TypeVar

    _F = TypeVar("_F")

    def type_checker(fn: _F) -> _F:
        """Type-only stub — see src/utils/CLAUDE.md."""
else:
    try:
        from utils.typing import type_checker
    except ModuleNotFoundError:
        from chassis.typing import type_checker


_DICT_PLATFORM_SIGNATURES = {
    "teams.microsoft": "teams",
    "office.com": "teams",
    "slack": "slack",
}

_DICT_BUILDERS: dict[str, Callable[[str], WebhookNotifier]] = {
    "teams": TeamsNotifier,
    "slack": SlackNotifier,
}


@type_checker
def detect_platform(str_url: str) -> str:  # complexity-ok: signature scan
    """Infer the webhook platform from its URL.

    Parameters
    ----------
    str_url : str
        The incoming-webhook URL.

    Returns
    -------
    str
        The platform key (``"teams"`` or ``"slack"``).

    Raises
    ------
    ValueError
        If no known platform signature matches ``str_url``.
    """
    str_lower = str_url.lower()
    for str_signature, str_platform in _DICT_PLATFORM_SIGNATURES.items():
        if str_signature in str_lower:
            return str_platform
    raise ValueError(
        f"Cannot infer webhook platform from URL; expected one of "
        f"{sorted(set(_DICT_PLATFORM_SIGNATURES.values()))} signatures"
    )


@type_checker
def build_webhook(str_url: str) -> WebhookNotifier:
    """Build a webhook notifier from a URL, auto-detecting the platform.

    Parameters
    ----------
    str_url : str
        Incoming webhook URL. A blank/whitespace URL opts out and returns a
        :class:`NullNotifier`.

    Returns
    -------
    WebhookNotifier
        An adapter satisfying the notifier port (or a no-op ``NullNotifier``).

    Raises
    ------
    ValueError
        If a non-blank URL matches no known platform signature.

    Examples
    --------
    >>> cls_webhook = build_webhook("https://outlook.office.com/webhook/…")
    >>> cls_webhook.send("Routine finished", str_title="DONE")
    """
    if not str_url.strip():
        return NullNotifier()
    return _DICT_BUILDERS[detect_platform(str_url)](str_url)
