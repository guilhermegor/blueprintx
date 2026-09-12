"""OTLP log export (opt-in) — an OpenTelemetry-backed handler for the existing logger.

Wires OTLP log export in ADDITION to the project's file logger (``utils.logs``), never in
place of it: a project with no collector configured keeps working exactly as today. OTel is
not a new API application code calls — this module is the only place ``opentelemetry`` is
imported (the vendor boundary ``.layer-policy.yaml`` enforces via ``bin/check_layer_imports.py``),
and it forwards to the same stdlib :class:`logging.Logger` every existing caller already writes
through (``utils.logs.log_message``, ``utils.retry.log_emitter.LogEmitter``, …).

⚠️ MEASURED (2026-09), not assumed: OpenTelemetry's Logs signal is "Development" status for
Python — https://opentelemetry.io/docs/languages/python/ lists Traces and Metrics as Stable and
Logs as Development, and ``opentelemetry.sdk._logs`` is documented as experimental (its APIs may
change in a minor/patch release with no backward-compatibility guarantee). Traces and metrics
stabilised first; logs is still the signal this project already has a *shape* for (a project
logger every layer writes through), so it ships anyway with the instability named here and in
``optional/otel.env.fragment`` — pin exact versions in ``pyproject.toml`` and re-read this comment
before bumping ``opentelemetry-sdk``.

⚠️ SECOND, SHARPER measurement (running ``opentelemetry-sdk`` 1.44.0 against a real scaffolded
project): ``opentelemetry.sdk._logs.LoggingHandler`` itself — the class this module builds on —
already emits ``DeprecationWarning: LoggingHandler in opentelemetry-sdk is deprecated. Use the
handler from opentelemetry-instrumentation-logging instead`` on every construction. That
replacement package is real but is ITSELF pre-release (``0.65b0`` on PyPI as of 2026-09) — moving
to it now would trade one instability for a less-tested one. This module uses the deprecated-but-
working handler deliberately (ponytail: known ceiling, not an oversight) — re-check both package
versions before the next bump and switch once the replacement leaves beta.
"""

import logging
import os
from typing import TYPE_CHECKING
from urllib.parse import urlsplit


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). mypy reads the single TYPE_CHECKING
# import (no redefinition); at runtime the try/except picks whichever layout shipped.
if TYPE_CHECKING:
	from utils.typing import type_checker
else:
	try:
		from utils.typing import type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from chassis.typing import type_checker


# A cleartext endpoint is only a credential leak when there is a credential to leak, and only
# when it leaves the machine. Both halves matter: refusing every http:// endpoint would break
# this seam's own documented quickstart (docker-compose.otel-collector.yml serves
# http://localhost:4318), and refusing none would ship an API key over the wire in the clear.
_TUPLE_LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


@type_checker
def _signal_override(str_signal_var: str, str_generic_var: str) -> str:
	"""Resolve a signal-specific OTLP variable over its generic fallback.

	⚠️ Presence decides, never truthiness. ``OTLPLogExporter`` reads the environment when it
	is constructed and honours a signal-specific variable that is SET BUT EMPTY — an `or`
	chain does not, because ``""`` is falsy, so it silently falls through to the generic
	value. That divergence is the whole defect: the caller would then vet an endpoint the
	exporter is not using, and could report credentials as safe that are in fact sent
	nowhere, or unsafe when they are not sent at all.

	Parameters
	----------
	str_signal_var : str
		Name of the signal-specific variable (``OTEL_EXPORTER_OTLP_LOGS_*``).
	str_generic_var : str
		Name of the generic fallback variable (``OTEL_EXPORTER_OTLP_*``).

	Returns
	-------
	str
		The effective value, stripped; ``""`` when neither variable is set.

	Examples
	--------
	>>> isinstance(_signal_override("A_MISSING_VAR", "ANOTHER_MISSING_VAR"), str)
	True
	"""
	str_signal = os.getenv(str_signal_var)
	if str_signal is not None:
		return str_signal.strip()
	return (os.getenv(str_generic_var) or "").strip()


@type_checker
def _effective_otlp_logs_config() -> tuple[str, bool]:
	"""Resolve the endpoint and whether credential headers are set, honouring precedence.

	⚠️ The signal-specific variables OVERRIDE the generic ones (OTel spec). Reading only
	``OTEL_EXPORTER_OTLP_ENDPOINT``/``_HEADERS`` therefore answers about a configuration the
	SDK may not be using — it would miss a project that sets only ``..._LOGS_...``, and the
	miss is silent in both directions: no export where one was configured, or no TLS check
	where credentials are in fact being sent. Precedence is resolved by ``_signal_override``,
	which keys on PRESENCE so a set-but-empty override is preserved rather than skipped.

	Returns
	-------
	tuple[str, bool]
		The effective logs endpoint (``""`` when unset) and whether any headers are set.

	Examples
	--------
	>>> isinstance(_effective_otlp_logs_config(), tuple)
	True
	"""
	str_endpoint = _signal_override(
		"OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "OTEL_EXPORTER_OTLP_ENDPOINT"
	)
	str_headers = _signal_override("OTEL_EXPORTER_OTLP_LOGS_HEADERS", "OTEL_EXPORTER_OTLP_HEADERS")
	return str_endpoint, bool(str_headers)


@type_checker
def _is_cleartext_with_credentials(str_endpoint: str, bool_has_headers: bool) -> bool:
	"""Report whether credentials would be sent over an unencrypted, off-host connection.

	Parameters
	----------
	str_endpoint : str
		The effective OTLP logs endpoint.
	bool_has_headers : bool
		Whether ``OTEL_EXPORTER_OTLP_[LOGS_]HEADERS`` carries anything.

	Returns
	-------
	bool
		``True`` when the exporter must not be started.

	Examples
	--------
	>>> _is_cleartext_with_credentials("http://collector.example:4318", True)
	True
	>>> _is_cleartext_with_credentials("http://localhost:4318", True)
	False
	>>> _is_cleartext_with_credentials("http://collector.example:4318", False)
	False
	"""
	return (
		bool_has_headers
		and bool(str_endpoint)
		and not str_endpoint.startswith("https://")
		and urlsplit(str_endpoint).hostname not in _TUPLE_LOOPBACK_HOSTS
	)


@type_checker
def _exportable_endpoint(logger: logging.Logger) -> str:
	"""Return the endpoint to export to, or ``""`` when export must not start.

	⚠️ The refusal WARNS rather than returning quietly. The install below is deliberately
	fire-and-forget, so a silent refusal here would look identical to a working exporter that
	simply never delivers: the user configured export, saw no error, and gets no logs. That is
	the silent wrong answer this seam is otherwise careful to avoid.

	Parameters
	----------
	logger : logging.Logger
		The logger the warning is written to.

	Returns
	-------
	str
		The effective endpoint, or ``""``.

	Examples
	--------
	>>> import logging
	>>> isinstance(_exportable_endpoint(logging.getLogger("app")), str)
	True
	"""
	str_endpoint, bool_has_headers = _effective_otlp_logs_config()
	if _is_cleartext_with_credentials(str_endpoint, bool_has_headers):
		# The endpoint is named because the fix is to change it; the header VALUES never are,
		# since they are the credential this guard exists to protect.
		logger.warning(
			"OTel log export refused: OTLP headers are set but the endpoint %r is neither "
			"https:// nor loopback, so the credentials would cross the network in cleartext. "
			"Use an https:// endpoint, or drop the headers for a local collector.",
			str_endpoint,
		)
		return ""
	return str_endpoint


# CWE-319, and the reason it is not covered by the cleartext guard above: that guard vets the
# CONFIGURED endpoint, while `requests` follows a 3xx on its own and re-sends the OTLP headers —
# the API key — to whatever host the hop names, over http:// if it says so. So the credential can
# leave in the clear via an endpoint no check ever saw. `max_redirects = 0` makes requests raise
# TooManyRedirects on the first hop instead of forwarding it.
# ⚠️ `_session` is a vendor internal. It is read through getattr and its ABSENCE is fatal on
# purpose: if a future opentelemetry release renames it, the right outcome is "no export", never
# "export with credentials unprotected" — a silent downgrade is the failure this repo writes
# guards to prevent. The raise is caught by the fire-and-forget handler in the caller.
@type_checker
def _reject_credential_forwarding_redirects(cls_exporter: object) -> None:
	"""Refuse to follow redirects, so credential headers cannot reach another host.

	Parameters
	----------
	cls_exporter : object
		The ``OTLPLogExporter`` whose underlying ``requests`` session is hardened.

	Returns
	-------
	None

	Raises
	------
	RuntimeError
		When the exporter exposes no session to harden — see the note above the function.
	"""
	cls_session = getattr(cls_exporter, "_session", None)
	if cls_session is None:
		raise RuntimeError(
			"OTLPLogExporter exposes no _session, so redirect-based credential forwarding "
			"(CWE-319) cannot be blocked; refusing to start the exporter"
		)
	cls_session.max_redirects = 0


@type_checker
def _install_otel_handler(logger: logging.Logger) -> None:  # complexity-ok: one guard, one sink
	"""Build the OTLP logger provider and attach its handler to ``logger``.

	Split out of :func:`configure_otel_logging` so the opt-out guard (env unset) and the
	fire-and-forget failure guard each carry their own single branch — two responsibilities,
	not one function doing both.

	Parameters
	----------
	logger : logging.Logger
		The logger the OTel handler is added to (never replaces its existing handlers).

	Returns
	-------
	None
	"""
	# Fire-and-forget, deliberately. A failure here must never become an application outage —
	# raising would turn an unreachable OTel collector into a crashed scaffolded project, and
	# the FileHandler above already gives the message somewhere to land either way. This is
	# the ONE place a silently swallowed error is the correct choice.
	try:
		from opentelemetry._logs import set_logger_provider
		from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
		from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
		from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
		from opentelemetry.sdk.resources import Resource

		# The SDK classes below already read the standard OTEL environment variables for the
		# endpoint, headers, service name and resource attributes on their own, so none of
		# that is passed explicitly — reimplementing the lookup would be a second, driftable
		# copy of it.
		cls_exporter = OTLPLogExporter()
		_reject_credential_forwarding_redirects(cls_exporter)
		cls_provider = LoggerProvider(resource=Resource.create())
		cls_provider.add_log_record_processor(BatchLogRecordProcessor(cls_exporter))
		set_logger_provider(cls_provider)
		logger.addHandler(LoggingHandler(logger_provider=cls_provider))
	except Exception as cls_exc:  # noqa: BLE001 — see the fire-and-forget note above
		logger.warning("OTel log export not started: %s", cls_exc)


@type_checker
def configure_otel_logging(logger: logging.Logger) -> None:
	"""Attach an OTLP log handler to ``logger`` when a collector endpoint is configured.

	Opt-in and additive. With both ``OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`` and
	``OTEL_EXPORTER_OTLP_ENDPOINT`` unset (the default — nothing
	prompts for it unless the OTel scaffold question was answered yes), this returns
	immediately: no ``opentelemetry`` import is even attempted, so a project that declined the
	prompt never pays for a dependency it did not install and never sends a byte over the
	network. With the endpoint set, the handler is ADDED to ``logger`` alongside whatever it
	already carries — the ``logging.FileHandler`` from ``utils.logs.CreateLog.basic_conf``
	keeps writing to the local log file exactly as before.

	Parameters
	----------
	logger : logging.Logger
		The project logger to export from (e.g. ``config.startup.LOGGER``).

	Returns
	-------
	None

	Examples
	--------
	>>> import logging
	>>> configure_otel_logging(logging.getLogger("app"))
	"""
	if not _exportable_endpoint(logger):
		return
	_install_otel_handler(logger)
