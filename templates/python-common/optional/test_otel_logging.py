"""Unit tests for ``configure_otel_logging`` (blueprintx#438).

Layout-agnostic import shim — the same file serves the chassis (DDD) and utils (MVC)
placements, mirroring ``tests/unit/test_typing.py``.
"""

import logging

import pytest


try:
	from utils.otel_logging import configure_otel_logging
except ModuleNotFoundError:  # DDD ships the module as chassis.otel_logging
	from chassis.otel_logging import configure_otel_logging


def test_configure_otel_logging_no_endpoint_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
	"""No OTEL_EXPORTER_OTLP_ENDPOINT -> no handler is added, no OTel import is attempted.

	This is the witness-the-negative-direction case blueprintx#438 asks for: a project
	that never opted into a collector must run — and stay silent over the network — exactly
	as it did before this seam existed.
	"""
	monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
	cls_logger = logging.getLogger("test_otel_logging_no_endpoint")
	cls_logger.handlers.clear()

	configure_otel_logging(cls_logger)

	assert cls_logger.handlers == []


def test_configure_otel_logging_with_endpoint_adds_handler_without_removing_existing(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""An endpoint configured -> the OTLP handler is attached; the FileHandler stays.

	The positive-direction witness: the exporter IS invoked (a handler backed by it is
	installed), and the project's existing local logger handler is untouched — OTel adds,
	it never replaces.
	"""
	monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
	cls_logger = logging.getLogger("test_otel_logging_with_endpoint")
	cls_logger.handlers.clear()
	cls_existing_handler = logging.NullHandler()
	cls_logger.addHandler(cls_existing_handler)

	configure_otel_logging(cls_logger)

	assert cls_existing_handler in cls_logger.handlers
	assert len(cls_logger.handlers) == 2
	cls_logger.handlers.clear()  # tidy the module-global logger registry for other tests


def test_cleartext_endpoint_with_headers_is_refused_and_warns(
	monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
	"""Credentials + an off-host http:// endpoint -> no handler, and a WARNING.

	The should-fail witness for the TLS guard. Asserting only "no handler" would not
	distinguish the guard from a broken exporter, so the warning is asserted too: the install
	path is fire-and-forget, and a silent refusal is indistinguishable from an exporter that
	runs and never delivers.
	"""
	monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", raising=False)
	monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_HEADERS", raising=False)
	monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.example.com:4318")
	monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "authorization=Bearer secret-token")
	cls_logger = logging.getLogger("test_otel_logging_cleartext")
	cls_logger.handlers.clear()

	with caplog.at_level(logging.WARNING):
		configure_otel_logging(cls_logger)

	assert cls_logger.handlers == []
	assert "cleartext" in caplog.text
	# The endpoint is actionable and belongs in the message; the credential never does.
	assert "secret-token" not in caplog.text


def test_loopback_cleartext_endpoint_with_headers_is_allowed(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Credentials over http://localhost are NOT refused — the documented local-dev path.

	The guard's other direction. docker-compose.otel-collector.yml serves
	http://localhost:4318, so a blanket "https or refuse" would break this seam's own
	quickstart; the traffic never leaves the machine, so there is nothing on the path to
	read the header.
	"""
	monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", raising=False)
	monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_HEADERS", raising=False)
	monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
	monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "authorization=Bearer secret-token")
	cls_logger = logging.getLogger("test_otel_logging_loopback")
	cls_logger.handlers.clear()

	configure_otel_logging(cls_logger)

	assert cls_logger.handlers != []


def test_signal_specific_endpoint_alone_enables_export(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Only OTEL_EXPORTER_OTLP_LOGS_ENDPOINT set -> export still starts.

	The signal-specific variable OVERRIDES the generic one per the OTel spec, so a guard
	reading only the generic name returns early and the project gets no export at all while
	having configured one — a silent wrong answer with no error anywhere.
	"""
	monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
	monkeypatch.delenv("OTEL_EXPORTER_OTLP_HEADERS", raising=False)
	monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_HEADERS", raising=False)
	monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://localhost:4318")
	cls_logger = logging.getLogger("test_otel_logging_signal_specific")
	cls_logger.handlers.clear()

	configure_otel_logging(cls_logger)

	assert cls_logger.handlers != []
