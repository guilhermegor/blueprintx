"""``reconcile`` intent pipeline (native DB) — re-read the last run, compare, re-notify.

Demonstrates a re-processing purpose: it consumes the PRIOR run's output (here the JSON
summary the ``send`` intent wrote) and reports the delta. Same constructor contract and
zero-arg :meth:`run` as every other ``pipeline_<intent>.py``.

A production reconcile should persist the FULL payload (plus routing keys) to a values store
at produce time and read it back **DB-first**, falling back to a **bounded, year-aware
backfill** of the dated output folders (fail loud if nothing within the cap — never a silent
empty), reusing the producer's senders via :mod:`controller.pipeline_common` so the re-send
takes the exact delivery path. See the "Multi-intent + reconcile" note in ``controller/CLAUDE.md``.
This example keeps the baseline read simple (the prior summary JSON) to illustrate the
dispatch/compose seam without a values-store dependency.
"""

from __future__ import annotations

from collections.abc import Callable
import json
from logging import Logger
from pathlib import Path
from time import time
from typing import Any

from controller import pipeline_common
from controller.pipeline_common import EmailHandler, WebhookNotifier
from utils.loggers import log_message
from utils.typing import TypeChecker


class ReconcilePipeline(metaclass=TypeChecker):
	"""Sequence the ``reconcile`` purpose end to end (native DB).

	Parameters
	----------
	logger : logging.Logger | None
		The run logger (``None`` prints).
	fn_build_connection : Callable[[], Any]
		Zero-arg callable opening a DB-API connection. Unused by this illustrative read; a
		production reconcile uses it to read the persisted values store (see the module note).
	fn_output_path : Callable[[str], pathlib.Path]
		Resolver from an ``outputs.yaml`` key to an output path.
	path_json : pathlib.Path
		Path of the prior run's JSON summary, read here as the reconciliation baseline.
	dict_context : dict
		Run-context values logged so every log file is self-describing.
	cls_email_handler : EmailHandler | None
		Optional e-mail handler (the ``EmailHandler`` port), injected by ``main.py``.
	cls_webhook : WebhookNotifier | None
		Optional webhook notifier (the ``WebhookNotifier`` port); when wired, the final phase
		sends ``str_webhook_message``.
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
		"""Execute every phase in order, returning the reconciliation summary.

		Returns
		-------
		dict
			Reconciliation summary (intent, whether a baseline was found, baseline rows).
		"""
		float_start = time()
		pipeline_common.log_context(
			self.logger, self.dict_context, self.cls_email_handler, self.cls_webhook
		)
		dict_baseline = self._read_baseline()
		dict_summary: dict[str, Any] = {
			"intent": "reconcile",
			"baseline_found": bool(dict_baseline),
			"baseline_rows": int(dict_baseline.get("rows_read", 0)),
		}
		pipeline_common.write_summary(self.logger, self.path_json, dict_summary)
		pipeline_common.log_elapsed(self.logger, time() - float_start)
		pipeline_common.notify(self.logger, self.cls_webhook, self.str_webhook_message)
		return dict_summary

	def _read_baseline(self) -> dict[str, Any]:
		"""Read the prior run's summary as the reconciliation baseline.

		Returns
		-------
		dict
			The prior summary, or an empty dict when no prior output exists. A production
			reconcile reads a values store DB-first and falls back to a bounded backfill
			(fail loud on nothing within the cap) rather than returning empty.
		"""
		log_message(self.logger, "Reading prior-run baseline for reconciliation")
		if not self.path_json.exists():
			log_message(
				self.logger, "No prior summary found — baseline empty (prod: bounded backfill)"
			)
			return {}
		dict_prior: dict[str, Any] = json.loads(self.path_json.read_text(encoding="utf-8"))
		log_message(self.logger, f"Baseline loaded ({dict_prior.get('rows_read', 0)} prior rows)")
		return dict_prior
