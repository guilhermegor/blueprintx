"""Service bootstrap: environment loading, logging setup, timing, and optional notify."""

from __future__ import annotations

from time import time
from typing import Protocol, runtime_checkable
import warnings

from chassis.typing import ProtocolTypeCheckerMeta, type_checker
from dotenv import load_dotenv
from stpstone.utils.calendars.calendar_br import DatesBRAnbima

from src.config.startup import DIR_PARENT, LOGGER
from utils.logs import CreateLog, initiate_logging


cls_create_log = CreateLog()
cls_dates = DatesBRAnbima()


@type_checker
def init() -> float:
	"""Load environment, configure logging, suppress warnings.

	Returns
	-------
	float
		Monotonic start timestamp for elapsed-time tracking.
	"""
	load_dotenv()
	warnings.simplefilter(action="ignore", category=FutureWarning)
	initiate_logging(LOGGER, DIR_PARENT)
	return time()


@type_checker
def teardown(start_time: float) -> None:
	"""Log elapsed time and routine end datetime.

	Parameters
	----------
	start_time : float
		Timestamp returned by :func:`init`.
	"""
	elapsed = time() - start_time
	hours, remainder = divmod(elapsed, 3600)
	minutes, seconds = divmod(remainder, 60)
	cls_create_log.log_message(
		logger=LOGGER,
		message=f"Time elapsed(HH:MM:SS): {int(hours)}:{int(minutes)}:{seconds:.2f}",
		log_level="info",
	)
	cls_create_log.log_message(
		logger=LOGGER,
		message=f"Routine ended in {cls_dates.curr_datetime()}",
		log_level="info",
	)


@runtime_checkable
class WebhookNotifier(Protocol, metaclass=ProtocolTypeCheckerMeta):
	"""Structural port for the optional outbound webhook notifier (see ``optional/webhook``).

	``notify`` depends only on ``send``; the concrete platform (Teams/Slack, or a no-op
	``NullNotifier`` for a blank URL) is injected by ``main.py`` when the webhook opt-in is
	chosen. Kept local so the always-shipped bootstrap never imports the opt-in seam.
	"""

	def send(self, str_message: str, str_title: str = "ROUTINE_CONCLUSION") -> None:
		"""Send one notification."""
		...


@type_checker
def notify(cls_webhook: WebhookNotifier | None, str_message: str) -> None:
	"""Send the run-summary notification — the final lifecycle step.

	No-op when ``cls_webhook`` is ``None`` (the webhook opt-in was declined or the
	environment failed the production gate in ``main.py``).

	Parameters
	----------
	cls_webhook : WebhookNotifier | None
		The injected notifier (the ``WebhookNotifier`` port), or ``None`` to skip.
	str_message : str
		The run-summary message to send.
	"""
	if cls_webhook is None:
		return
	cls_create_log.log_message(
		logger=LOGGER, message="Sending webhook notification", log_level="info"
	)
	cls_webhook.send(str_message)
	cls_create_log.log_message(
		logger=LOGGER, message="Webhook notification sent", log_level="info"
	)
