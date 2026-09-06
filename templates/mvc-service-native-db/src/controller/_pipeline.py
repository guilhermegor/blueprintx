"""Phase orchestrator for the MVC pipeline (native DB).

The controller's ``main.py`` only builds this orchestrator and calls :meth:`run`. The
sequencing — log the run context, open the DB connection, read via the model, enrich with
optional labels, render the report via the view, write the JSON summary, then notify via the
optional webhook — lives here, each phase bracketed by log lines. Business logic lives in the
model (:class:`model.example_entity.ExampleEntity`); this module wires and sequences it. The
connection is opened for the read and always closed in a ``finally``.

:meth:`_enrich` is the reference example for a **documented graceful degradation**: see
docs/architecture.md#enrichment-degradation-contract for why a degradation is a contract
enforced against every failure mode, not a docstring claim covering only the one that was
tested (blueprintx#151).
"""

from __future__ import annotations

from collections.abc import Callable
import json
from logging import Logger
from pathlib import Path
from time import time
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from model.example_entity import ExampleEntity
from utils.logs import log_message
from utils.typing import ProtocolTypeCheckerMeta, TypeChecker
from view.report_renderer import RenderToExcel


@runtime_checkable
class EmailHandler(Protocol, metaclass=ProtocolTypeCheckerMeta):
	"""Structural port for the optional e-mail handler (see ``optional/email``).

	The orchestrator depends only on the shared ``send_email`` method; the concrete backend
	(Outlook by default, or SMTP) is injected by ``main.py`` when the e-mail opt-in is chosen.
	Kept local so the always-shipped controller never imports the opt-in seam. A concrete
	handler may carry more methods (the Outlook one also downloads attachments) — not in this
	shared port, which holds only what every backend can do.
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

	The orchestrator depends only on ``send``; the concrete platform (Teams/Slack, or a
	no-op ``NullNotifier`` for a blank URL) is injected by ``main.py`` when the webhook
	opt-in is chosen. Kept local so the always-shipped controller never imports the opt-in
	seam (mirrors :class:`EmailHandler`).
	"""

	def send(self, str_message: str, str_title: str = "ROUTINE_CONCLUSION") -> None:
		"""Send one notification."""
		...


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
		is self-describing. An optional ``"path_labels"`` key (``pathlib.Path``) points
		:meth:`_enrich` at a ``{id: label}`` JSON lookup; absent or ``None`` means the
		enrichment is not configured for this project — the first of the five failure modes
		it degrades on.
	cls_email_handler : EmailHandler | None
		Optional e-mail handler (the ``EmailHandler`` port). Injected by ``main.py`` only when
		the e-mail opt-in is chosen — Outlook backend by default, SMTP if configured. The
		reference run does not send; a project adds its own notify phase.
	cls_webhook : WebhookNotifier | None
		Optional outbound webhook notifier (the ``WebhookNotifier`` port). Injected by
		``main.py`` only when the webhook opt-in is chosen *and* the environment passes the
		production gate. When wired, :meth:`run` sends ``str_webhook_message`` as its final
		phase; when ``None`` the notify phase is a no-op.
	str_webhook_message : str
		The run-summary message sent through ``cls_webhook`` (rendered from ``webhooks.yaml``
		in ``startup``). Ignored when ``cls_webhook`` is ``None``.
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
		df_report = self._enrich(df_report)
		path_report = self._render(df_report)
		dict_summary: dict[str, Any] = {
			"rows_read": int(len(df_report)),
			"report_path": str(path_report),
		}
		self._write_summary(dict_summary)
		self._log_elapsed(time() - float_start)
		self._notify()
		return dict_summary

	def _log_context(self) -> None:
		"""Log the run context (one line per item) so a run is self-describing."""
		log_message(self.logger, "Starting variable-definition process")
		for str_key, value in self.dict_context.items():
			log_message(self.logger, f"{str_key}: {value}")
		log_message(
			self.logger,
			f"Email handler: {'configured' if self.cls_email_handler is not None else 'none'}",
		)
		log_message(
			self.logger,
			f"Webhook notifier: {'configured' if self.cls_webhook is not None else 'none'}",
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

	def _enrich(  # complexity-ok: two distinct degradation triggers, each its own log line
		self, df_report: pd.DataFrame
	) -> pd.DataFrame:
		"""Best-effort merge of the optional labels file onto the report.

		A documented graceful degradation is a contract, not a docstring claim — it holds only
		if every failure mode that can prevent the merge reaches the SAME degraded value:
		``df_report`` unchanged (the ``label`` column simply absent). Five modes can prevent
		it, and this method degrades on all five (full rationale, and the incident it
		generalises from: docs/architecture.md#enrichment-degradation-contract):

		1. no ``path_labels`` configured (checked up front, no call attempted);
		2. the file is absent; 3. the file is malformed (not valid JSON, or not a
		``{id: label}`` object); 4. a permission error; 5. any other unforeseen failure while
		reading or applying it.

		Modes 2-5 all raise from the same read-and-apply block, so one ``try/except
		Exception`` around it — logging the collaborator and ``type(exc).__name__``, then
		returning ``df_report`` unchanged — covers them together; splitting them into separate
		``except`` clauses would only re-create the original defect under a different shape
		(one clause remembered, the rest fall through).

		Called before :meth:`_render`, which persists the report — nothing this method does
		may run after persistence, so a failure here can never invalidate an already-written
		report.

		Parameters
		----------
		df_report : pandas.DataFrame
			The already-fetched report (the read phase already succeeded; never re-read here).

		Returns
		-------
		pandas.DataFrame
			``df_report`` merged with the ``label`` column, or unchanged when enrichment could
			not run.
		"""
		path_labels = self.dict_context.get("path_labels")
		if path_labels is None:
			log_message(self.logger, "Label enrichment skipped: no path_labels configured")
			return df_report
		try:
			with path_labels.open(encoding="utf-8") as file_labels:
				dict_labels = json.load(file_labels)
			df_enriched = df_report.copy()
			df_enriched["label"] = df_enriched["id"].astype(str).map(dict_labels)
		except Exception as exc:
			log_message(
				self.logger,
				f"Label enrichment degraded: reading {path_labels.name} raised "
				f"{type(exc).__name__}",
				"warning",
			)
			return df_report
		return df_enriched

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
		with self.path_json.open("w") as file_write:
			json.dump(dict_summary, file_write)
		log_message(self.logger, f"Summary exported: {self.path_json}")

	def _notify(self) -> None:
		"""Send the run-summary notification when a webhook is wired (final phase).

		The payload is measured at composition time, **before** the
		``cls_webhook is None`` gate — not inside the branch that only runs when a
		notifier is wired. A measurement placed after the gate only produces output on
		the success path, which tells you nothing about a run where the webhook opt-in
		was declined or the environment failed the production gate (the exact runs a
		"was this safe to turn on?" question needs data from).

		No-op past the log line when no notifier was injected (``cls_webhook is None``)
		— i.e. the webhook opt-in was declined or the environment failed the production
		gate in ``main.py``.
		"""
		int_payload_chars = len(self.str_webhook_message)
		log_message(self.logger, f"Notification payload composed: {int_payload_chars} chars")
		if self.cls_webhook is None:
			return
		log_message(self.logger, "Sending webhook notification")
		self.cls_webhook.send(self.str_webhook_message)
		log_message(self.logger, "Webhook notification sent")

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
