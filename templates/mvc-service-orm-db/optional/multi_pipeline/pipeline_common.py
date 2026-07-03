"""Shared lifecycle helpers and ports for the multi-intent controller (ORM).

When this service runs several distinct purposes off one codebase (selected by the
``PIPELINE_INTENT`` env key — see ``pipeline_dispatch``), each ``controller/pipeline_<intent>.py``
orchestrator composes the intent-agnostic phases defined here as plain functions — composition
over a shared base class. The optional e-mail and webhook ports live here too, since every
intent shares them. Business logic stays in the model; these helpers only log, render, persist
and notify.
"""

from __future__ import annotations

from collections.abc import Callable
import json
from logging import Logger
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from utils.logs import log_message
from utils.typing import ProtocolTypeCheckerMeta, type_checker
from view.report_renderer import RenderToExcel


@runtime_checkable
class EmailHandler(Protocol, metaclass=ProtocolTypeCheckerMeta):
	"""Structural port for the optional e-mail handler (see ``optional/email``).

	Every intent's orchestrator depends only on the shared ``send_email`` method; the concrete
	backend (Outlook by default, or SMTP) is injected by ``main.py`` when the e-mail opt-in is
	chosen. Kept here so the per-intent pipelines never import the opt-in seam directly.
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
		"""Send one e-mail; return whether it was dispatched."""
		...


@runtime_checkable
class WebhookNotifier(Protocol, metaclass=ProtocolTypeCheckerMeta):
	"""Structural port for the optional outbound webhook notifier (see ``optional/webhook``).

	Every intent's orchestrator depends only on ``send``; the concrete platform (Teams/Slack,
	or a no-op ``NullNotifier`` for a blank URL) is injected by ``main.py`` when the webhook
	opt-in is chosen. Mirrors :class:`EmailHandler`.
	"""

	def send(self, str_message: str, str_title: str = "ROUTINE_CONCLUSION") -> None:
		"""Send one notification."""
		...


@runtime_checkable
class Pipeline(Protocol, metaclass=ProtocolTypeCheckerMeta):
	"""Structural port every ``pipeline_<intent>`` satisfies.

	The dispatcher (:func:`controller.pipeline_dispatch.build_pipeline`) returns this contract:
	a zero-arg :meth:`run` that executes the intent and returns its run summary. Every
	per-intent orchestrator shares one constructor signature and this method.
	"""

	def run(self) -> dict[str, Any]:
		"""Execute the pipeline and return its run summary."""
		...


@type_checker
def log_context(
	logger: Logger | None,
	dict_context: dict[str, Any],
	cls_email_handler: EmailHandler | None,
	cls_webhook: WebhookNotifier | None,
) -> None:
	"""Log the run context (one line per item) so a run is self-describing.

	Parameters
	----------
	logger : logging.Logger | None
		The run logger (``None`` prints).
	dict_context : dict
		Run-context values (app/operator/host/environment/paths) to log.
	cls_email_handler : EmailHandler | None
		The injected e-mail handler, if any (logged as configured/none).
	cls_webhook : WebhookNotifier | None
		The injected webhook notifier, if any (logged as configured/none).
	"""
	log_message(logger, "Starting variable-definition process")
	for str_key, value in dict_context.items():
		log_message(logger, f"{str_key}: {value}")
	log_message(
		logger,
		f"Email handler: {'configured' if cls_email_handler is not None else 'none'}",
	)
	log_message(
		logger,
		f"Webhook notifier: {'configured' if cls_webhook is not None else 'none'}",
	)
	log_message(logger, "Finishing variable-definition process")


@type_checker
def render_report(
	logger: Logger | None,
	fn_output_path: Callable[[str], Path],
	df_report: pd.DataFrame,
) -> Path:
	"""Render the report via the view and return its path.

	Parameters
	----------
	logger : logging.Logger | None
		The run logger.
	fn_output_path : Callable[[str], pathlib.Path]
		Resolver from an ``outputs.yaml`` key to an output path.
	df_report : pandas.DataFrame
		The data to render.

	Returns
	-------
	pathlib.Path
		The written report path.
	"""
	log_message(logger, "Starting report-export process")
	path_report = fn_output_path("xlsx_name")
	RenderToExcel(path_report).render(df_report)
	log_message(logger, f"Finishing report-export process ({path_report})")
	return path_report


@type_checker
def write_summary(logger: Logger | None, path_json: Path, dict_summary: dict[str, Any]) -> None:
	"""Write the JSON run summary.

	Parameters
	----------
	logger : logging.Logger | None
		The run logger.
	path_json : pathlib.Path
		Path to write the JSON run summary.
	dict_summary : dict
		The run summary to serialise.
	"""
	log_message(logger, "Starting summary-export process")
	with path_json.open("w") as file_write:
		json.dump(dict_summary, file_write)
	log_message(logger, f"Summary exported: {path_json}")


@type_checker
def notify(logger: Logger | None, cls_webhook: WebhookNotifier | None, str_message: str) -> None:
	"""Send the run-summary notification when a webhook is wired (no-op otherwise).

	Parameters
	----------
	logger : logging.Logger | None
		The run logger.
	cls_webhook : WebhookNotifier | None
		The injected webhook notifier; when ``None`` this is a no-op.
	str_message : str
		The run-summary message to send.
	"""
	if cls_webhook is None:
		return
	log_message(logger, "Sending webhook notification")
	cls_webhook.send(str_message)
	log_message(logger, "Webhook notification sent")


@type_checker
def log_elapsed(logger: Logger | None, float_elapsed: float) -> None:
	"""Log the elapsed wall time as HH:MM:SS.

	Parameters
	----------
	logger : logging.Logger | None
		The run logger.
	float_elapsed : float
		Elapsed seconds.
	"""
	float_hours, float_remainder = divmod(float_elapsed, 3600)
	float_minutes, float_seconds = divmod(float_remainder, 60)
	str_hms = f"{int(float_hours)}:{int(float_minutes)}:{float_seconds:.2f}"
	log_message(logger, f"Run finished (HH:MM:SS): {str_hms}")
