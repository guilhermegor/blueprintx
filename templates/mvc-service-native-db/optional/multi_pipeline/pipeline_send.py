"""``send`` intent pipeline (native DB) — read, render, persist, notify.

The default/primary purpose: read the source data via the model, render the report, write
the JSON summary, then notify. Mirrors the single-mode orchestrator's phases but composes the
shared helpers in :mod:`controller.pipeline_common`. Same constructor contract and zero-arg
:meth:`run` as every other ``pipeline_<intent>.py``, so the dispatcher can build any intent
uniformly.
"""

from __future__ import annotations

from collections.abc import Callable
from logging import Logger
from pathlib import Path
from time import time
from typing import Any

import pandas as pd

from controller import pipeline_common
from controller.pipeline_common import EmailHandler, WebhookNotifier
from model.example_entity import ExampleEntity
from utils.loggers import log_message
from utils.typing import TypeChecker


class SendPipeline(metaclass=TypeChecker):
	"""Sequence the ``send`` purpose end to end (native DB).

	Parameters
	----------
	logger : logging.Logger | None
		The run logger (``None`` prints).
	fn_build_connection : Callable[[], Any]
		Zero-arg callable opening a DB-API connection (closed after the read).
	fn_output_path : Callable[[str], pathlib.Path]
		Resolver from an ``outputs.yaml`` key to an output path.
	path_json : pathlib.Path
		Path to write the JSON run summary.
	dict_context : dict
		Run-context values logged so every log file is self-describing.
	cls_email_handler : EmailHandler | None
		Optional e-mail handler (the ``EmailHandler`` port), injected by ``main.py``.
	cls_webhook : WebhookNotifier | None
		Optional webhook notifier (the ``WebhookNotifier`` port); when wired, the final
		phase sends ``str_webhook_message``.
	str_webhook_message : str
		The run-summary message sent through ``cls_webhook``; ignored when it is ``None``.
	"""

	def __init__(
		self,
		logger: Logger | None,
		fn_build_connection: Callable[[], Any],
		fn_output_path: Callable[[str], Path],
		path_json: Path,
		dict_context: dict[str, Any],
		cls_email_handler: EmailHandler | None = None,
		cls_webhook: WebhookNotifier | None = None,
		str_webhook_message: str = "",
	) -> None:
		self.logger = logger
		self.fn_build_connection = fn_build_connection
		self.fn_output_path = fn_output_path
		self.path_json = path_json
		self.dict_context = dict_context
		self.cls_email_handler = cls_email_handler
		self.cls_webhook = cls_webhook
		self.str_webhook_message = str_webhook_message

	def run(self) -> dict[str, Any]:
		"""Execute every phase in order, returning the run summary.

		Returns
		-------
		dict
			Run summary (intent, rows read, report path).
		"""
		float_start = time()
		pipeline_common.log_context(
			self.logger, self.dict_context, self.cls_email_handler, self.cls_webhook
		)
		cls_connection = self._open_connection()
		try:
			df_report = self._read(cls_connection)
		finally:
			cls_connection.close()
			log_message(self.logger, "DB connection closed")
		path_report = pipeline_common.render_report(self.logger, self.fn_output_path, df_report)
		dict_summary: dict[str, Any] = {
			"intent": "send",
			"rows_read": int(len(df_report)),
			"report_path": str(path_report),
		}
		pipeline_common.write_summary(self.logger, self.path_json, dict_summary)
		pipeline_common.log_elapsed(self.logger, time() - float_start)
		pipeline_common.notify(self.logger, self.cls_webhook, self.str_webhook_message)
		return dict_summary

	def _open_connection(self) -> Any:  # noqa: ANN401 — opaque DB-API connection
		"""Open the DB-API connection used by the read phase.

		Returns
		-------
		Any
			The open DB-API 2.0 connection (closed by :meth:`run` in a ``finally``).
		"""
		log_message(self.logger, "Opening DB connection")
		return self.fn_build_connection()

	def _read(self, cls_connection: Any) -> pd.DataFrame:  # noqa: ANN401 — opaque DB-API connection
		"""Read the source data into a DataFrame via the model.

		Parameters
		----------
		cls_connection : Any
			The open DB-API connection.

		Returns
		-------
		pandas.DataFrame
			The rows read by the model.
		"""
		log_message(self.logger, "Starting data-read process")
		cls_example = ExampleEntity(cls_connection)
		cls_example.ensure_table()
		cls_example.insert("Hello from the 'send' intent (MVC native-db service)!")
		df_report = cls_example.fetch_all()
		log_message(self.logger, f"Finishing data-read process ({len(df_report)} rows)")
		return df_report
