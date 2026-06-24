"""Phase orchestrator for the MVC pipeline (native DB).

The controller's ``main.py`` only builds this orchestrator and calls :meth:`run`. The
sequencing — log the run context, open the DB connection, read via the model, render the
report via the view, write the JSON summary — lives here, each phase bracketed by log lines.
Business logic lives in the model (:class:`model.example_entity.ExampleEntity`); this module
wires and sequences it. The connection is opened for the read and always closed in a
``finally``.
"""

from __future__ import annotations

from collections.abc import Callable
from logging import Logger
from pathlib import Path
from time import time
from typing import Any

import pandas as pd
from stpstone.utils.parsers.json import JsonFiles

from model.example_entity import ExampleEntity
from utils.loggers import log_message
from utils.outlook_gateway import OutlookGateway
from utils.typing import TypeChecker
from view.report_renderer import RenderToExcel


class PipelineOrchestrator(metaclass=TypeChecker):
	"""Sequence the MVC phases end to end.

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
		Run-context values (app/operator/host/environment/paths) logged so every log file
		is self-describing.
	cls_email_gateway : OutlookGateway | None
		Optional e-mail seam (log-only off Windows). Injected like the proving ground so a
		real notify phase can use it; the reference run does not send.
	"""

	def __init__(
		self,
		logger: Logger | None,
		fn_build_connection: Callable[[], Any],
		fn_output_path: Callable[[str], Path],
		path_json: Path,
		dict_context: dict[str, Any],
		cls_email_gateway: OutlookGateway | None = None,
	) -> None:
		self.logger = logger
		self.fn_build_connection = fn_build_connection
		self.fn_output_path = fn_output_path
		self.path_json = path_json
		self.dict_context = dict_context
		self.cls_email_gateway = cls_email_gateway

	def run(self) -> dict[str, Any]:
		"""Execute every phase in order, returning the run summary.

		Returns
		-------
		dict
			Run summary (rows read, report path).
		"""
		float_start = time()
		self._log_context()
		cls_connection = self._open_connection()
		try:
			df_report = self._read(cls_connection)
		finally:
			cls_connection.close()
			log_message(self.logger, "DB connection closed")
		path_report = self._render(df_report)
		dict_summary: dict[str, Any] = {
			"rows_read": int(len(df_report)),
			"report_path": str(path_report),
		}
		self._write_summary(dict_summary)
		self._log_elapsed(time() - float_start)
		return dict_summary

	def _log_context(self) -> None:
		"""Log the run context (one line per item) so a run is self-describing."""
		log_message(self.logger, "Starting variable-definition process")
		for str_key, value in self.dict_context.items():
			log_message(self.logger, f"{str_key}: {value}")
		log_message(
			self.logger,
			f"Email gateway: {'configured' if self.cls_email_gateway is not None else 'none'}",
		)
		log_message(self.logger, "Finishing variable-definition process")

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
		cls_example.insert("Hello from MVC native-db service!")
		df_report = cls_example.fetch_all()
		log_message(self.logger, f"Finishing data-read process ({len(df_report)} rows)")
		return df_report

	def _render(self, df_report: pd.DataFrame) -> Path:
		"""Render the report via the view and return its path.

		Parameters
		----------
		df_report : pandas.DataFrame
			The data to render.

		Returns
		-------
		pathlib.Path
			The written report path.
		"""
		log_message(self.logger, "Starting report-export process")
		path_report = self.fn_output_path("xlsx_name")
		RenderToExcel(path_report).render(df_report)
		log_message(self.logger, f"Finishing report-export process ({path_report})")
		return path_report

	def _write_summary(self, dict_summary: dict[str, Any]) -> None:
		"""Write the JSON run summary.

		Parameters
		----------
		dict_summary : dict
			The run summary to serialise.
		"""
		log_message(self.logger, "Starting summary-export process")
		bool_ok = JsonFiles().dump_message(dict_summary, str(self.path_json))
		log_message(self.logger, f"Summary export ok={bool_ok}: {self.path_json}")

	def _log_elapsed(self, float_elapsed: float) -> None:
		"""Log the elapsed wall time as HH:MM:SS.

		Parameters
		----------
		float_elapsed : float
			Elapsed seconds.
		"""
		float_hours, float_remainder = divmod(float_elapsed, 3600)
		float_minutes, float_seconds = divmod(float_remainder, 60)
		str_hms = f"{int(float_hours)}:{int(float_minutes)}:{float_seconds:.2f}"
		log_message(self.logger, f"Run finished (HH:MM:SS): {str_hms}")
