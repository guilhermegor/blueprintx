"""Intent resolution and pipeline construction for the multi-intent controller (ORM).

``main.py`` reads the ``PIPELINE_INTENT`` env value, calls :func:`resolve_intent` (bilingual,
fail-loud) to map it to a canonical intent, then :func:`build_pipeline` to construct the
matching orchestrator. Adding a purpose = add a ``pipeline_<intent>.py`` plus one entry in the
alias table and the builder table here — no ``if/elif`` chain in ``main``.
"""

from __future__ import annotations

from collections.abc import Callable
from logging import Logger
from pathlib import Path
import sys
from typing import Any, NoReturn

from sqlalchemy import Engine

from controller.pipeline_common import EmailHandler, Pipeline, WebhookNotifier
from controller.pipeline_reconcile import ReconcilePipeline
from controller.pipeline_send import SendPipeline
from utils.text import normalize_text
from utils.typing import type_checker


# Accepted spellings -> canonical intent (English + pt-BR). normalize_text folds case and
# accents; resolve_intent additionally folds spaces/hyphens, so "Envio", "ENVIO", "reconciliação"
# all map. Anything unmatched fails loud.
_INTENT_ALIASES: dict[str, str] = {
	"send": "send",
	"envio": "send",
	"reconcile": "reconcile",
	"reconciliacao": "reconcile",
}

# Canonical intent -> orchestrator class. One entry per pipeline_<intent>.py.
_INTENT_BUILDERS: dict[str, Callable[..., Pipeline]] = {
	"send": SendPipeline,
	"reconcile": ReconcilePipeline,
}


@type_checker
def resolve_intent(str_raw: str) -> str:
	"""Map a raw ``PIPELINE_INTENT`` value to a canonical intent, failing loud on an unknown one.

	Parameters
	----------
	str_raw : str
		The environment value (any reasonable spelling — case, accents and spaces/hyphens are
		normalised).

	Returns
	-------
	str
		The canonical intent key (e.g. ``"send"`` / ``"reconcile"``).

	Raises
	------
	SystemExit
		When ``str_raw`` maps to no known intent — after printing a clear error to stderr
		(exit code 2).
	"""
	str_norm = normalize_text(str_raw).replace(" ", "_").replace("-", "_")
	str_intent = _INTENT_ALIASES.get(str_norm)
	if str_intent is None:
		_abort(
			f"invalid PIPELINE_INTENT {str_raw!r}; expected one of: {sorted(set(_INTENT_ALIASES))}"
		)
	return str_intent


@type_checker
def build_pipeline(
	str_intent: str,
	logger: Logger | None,
	fn_build_engine: Callable[[], Engine],
	fn_output_path: Callable[[str], Path],
	path_json: Path,
	dict_context: dict[str, Any],
	cls_email_handler: EmailHandler | None = None,
	cls_webhook: WebhookNotifier | None = None,
	str_webhook_message: str = "",
) -> Pipeline:
	"""Construct the orchestrator for a canonical intent, sharing one constructor contract.

	Parameters
	----------
	str_intent : str
		A canonical intent key (as returned by :func:`resolve_intent`).
	logger : logging.Logger | None
		The run logger.
	fn_build_engine : Callable[[], Engine]
		Zero-arg callable building the SQLAlchemy engine.
	fn_output_path : Callable[[str], pathlib.Path]
		Resolver from an ``outputs.yaml`` key to an output path.
	path_json : pathlib.Path
		Path to write (or, for reconcile, read) the JSON run summary.
	dict_context : dict
		Run-context values logged so every log file is self-describing.
	cls_email_handler : EmailHandler | None
		Optional e-mail handler injected by ``main.py``.
	cls_webhook : WebhookNotifier | None
		Optional webhook notifier injected by ``main.py``.
	str_webhook_message : str
		The run-summary message sent through ``cls_webhook``.

	Returns
	-------
	Pipeline
		The constructed orchestrator (a zero-arg ``run`` returning the run summary).

	Raises
	------
	SystemExit
		When ``str_intent`` is not a known canonical intent (exit code 2).
	"""
	cls_builder = _INTENT_BUILDERS.get(str_intent)
	if cls_builder is None:
		_abort(f"no pipeline registered for intent {str_intent!r}")
	return cls_builder(
		logger,
		fn_build_engine,
		fn_output_path,
		path_json,
		dict_context,
		cls_email_handler,
		cls_webhook,
		str_webhook_message,
	)


# Undecorated on purpose: the bare `-> NoReturn` annotation must stay visible to mypy so it
# narrows the callers' Optional values after the `if x is None: _abort(...)` guard. The runtime
# checker adds nothing to a one-arg string abort.
def _abort(str_reason: str) -> NoReturn:
	"""Print a startup error to stderr and abort the process (``SystemExit`` code 2).

	Parameters
	----------
	str_reason : str
		The reason shown to the operator.

	Raises
	------
	SystemExit
		Always (exit code 2).
	"""
	print(f"[startup][ERROR] {str_reason}", file=sys.stderr)
	raise SystemExit(2)
