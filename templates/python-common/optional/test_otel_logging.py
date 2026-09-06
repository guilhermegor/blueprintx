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
