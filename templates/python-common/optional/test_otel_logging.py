"""Unit tests for ``configure_otel_logging`` (blueprintx#438).

Layout-agnostic import shim — the same file serves the chassis (DDD) and utils (MVC)
placements, mirroring ``tests/unit/test_typing.py``.
"""

from collections.abc import Iterator
import logging

import pytest


try:
    from utils.otel_logging import (
        _is_cleartext_with_credentials,
        _reject_credential_forwarding_redirects,
        _signal_override,
        configure_otel_logging,
    )
except ModuleNotFoundError:
    from chassis.otel_logging import (
        _is_cleartext_with_credentials,
        _reject_credential_forwarding_redirects,
        _signal_override,
        configure_otel_logging,
    )


def test_signal_override_prefers_a_set_but_empty_signal_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A present-but-empty signal variable wins over the generic one.

    The negative control for the `or`-chain defect: `""` is falsy, so an `or` fell through to
    the generic value while the SDK — which keys on presence — used the empty override. The
    two then disagreed about which endpoint was in play.
    """
    monkeypatch.setenv("BX_TEST_SIGNAL", "")
    monkeypatch.setenv("BX_TEST_GENERIC", "http://generic.example:4318")

    assert _signal_override("BX_TEST_SIGNAL", str_generic_var="BX_TEST_GENERIC") == ""


def test_signal_override_falls_back_when_the_signal_variable_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absent signal variable defers to the generic one."""
    monkeypatch.delenv("BX_TEST_SIGNAL", raising=False)
    monkeypatch.setenv("BX_TEST_GENERIC", "http://generic.example:4318")

    assert (
        _signal_override("BX_TEST_SIGNAL", str_generic_var="BX_TEST_GENERIC")
        == "http://generic.example:4318"
    )


def test_reject_redirects_sets_max_redirects_to_zero() -> None:
    """The exporter's session is hardened so a 3xx cannot forward credential headers."""
    cls_exporter = type("FakeExporter", (), {"_session": type("FakeSession", (), {})()})()

    _reject_credential_forwarding_redirects(cls_exporter)

    assert cls_exporter._session.max_redirects == 0


def test_reject_redirects_raises_when_the_session_is_absent() -> None:
    """A renamed vendor internal must fail closed, never export unprotected."""
    with pytest.raises(RuntimeError, match="CWE-319"):
        _reject_credential_forwarding_redirects(object())


def test_configure_otel_logging_no_endpoint_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """No OTEL_EXPORTER_OTLP_ENDPOINT -> no handler is added, no OTel import is attempted.

    This is the witness-the-negative-direction case blueprintx#438 asks for: a project
    that never opted into a collector must run — and stay silent over the network — exactly
    as it did before this seam existed.
    """
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", raising=False)
    cls_logger = logging.getLogger("test_otel_logging_no_endpoint")
    cls_logger.handlers.clear()

    configure_otel_logging(cls_logger)

    assert cls_logger.handlers == []


@pytest.fixture
def tuple_endpoint_logger(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[logging.Logger, logging.Handler]]:
    """Configure a logger that already has a local handler, with an endpoint set.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest-provided environment patcher.

    Yields
    ------
    tuple[logging.Logger, logging.Handler]
        The configured logger and the handler it carried before OTel was attached.
    """
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    cls_logger = logging.getLogger("test_otel_logging_with_endpoint")
    cls_logger.handlers.clear()
    cls_existing_handler = logging.NullHandler()
    cls_logger.addHandler(cls_existing_handler)
    configure_otel_logging(cls_logger)
    yield cls_logger, cls_existing_handler
    cls_logger.handlers.clear()


def test_configure_otel_logging_with_endpoint_keeps_the_existing_handler(
    tuple_endpoint_logger: tuple[logging.Logger, logging.Handler],
) -> None:
    """An endpoint configured -> the project's existing local handler is untouched."""
    cls_logger, cls_existing_handler = tuple_endpoint_logger
    assert cls_existing_handler in cls_logger.handlers


def test_configure_otel_logging_with_endpoint_adds_exactly_one_handler(
    tuple_endpoint_logger: tuple[logging.Logger, logging.Handler],
) -> None:
    """An endpoint configured -> the OTLP handler is attached beside the existing one."""
    cls_logger, _ = tuple_endpoint_logger
    assert len(cls_logger.handlers) == 2


def _configure_cleartext_with_headers(
    monkeypatch: pytest.MonkeyPatch, *, caplog: pytest.LogCaptureFixture
) -> logging.Logger:
    """Configure a logger against an off-host http:// endpoint that carries credentials.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest-provided environment patcher.
    caplog : pytest.LogCaptureFixture
        Pytest-provided log capture.

    Returns
    -------
    logging.Logger
        The logger after ``configure_otel_logging`` ran.
    """
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_HEADERS", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.example.com:4318")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "authorization=Bearer secret-token")
    cls_logger = logging.getLogger("test_otel_logging_cleartext")
    cls_logger.handlers.clear()
    with caplog.at_level(logging.WARNING):
        configure_otel_logging(cls_logger)
    return cls_logger


def test_cleartext_endpoint_with_headers_is_refused(
    monkeypatch: pytest.MonkeyPatch, *, caplog: pytest.LogCaptureFixture
) -> None:
    """Credentials + an off-host http:// endpoint -> no handler is attached."""
    cls_logger = _configure_cleartext_with_headers(monkeypatch, caplog=caplog)
    assert cls_logger.handlers == []


def test_cleartext_endpoint_with_headers_warns(
    monkeypatch: pytest.MonkeyPatch, *, caplog: pytest.LogCaptureFixture
) -> None:
    """The refusal is announced: a silent refusal looks like an exporter that never delivers."""
    _configure_cleartext_with_headers(monkeypatch, caplog=caplog)
    assert "cleartext" in caplog.text


def test_cleartext_endpoint_with_headers_never_logs_the_secret(
    monkeypatch: pytest.MonkeyPatch, *, caplog: pytest.LogCaptureFixture
) -> None:
    """The warning names the problem without echoing the credential."""
    _configure_cleartext_with_headers(monkeypatch, caplog=caplog)
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


def test_unparseable_endpoint_with_credentials_is_refused_not_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🔴 The should-fail witness: a malformed endpoint must be REFUSED, never raise.

    `urlsplit("http://[").hostname` raises ValueError ("Invalid IPv6 URL"), and this guard runs
    BEFORE `_install_otel_handler`'s own exception handler — so the crash reached
    `configure_otel_logging`'s callers, which the generated startup code invokes directly.
    Refusing (no handler) is the safe direction: credentials must never ride an endpoint we
    could not even parse.
    """
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_HEADERS", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://[")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "authorization=Bearer secret-token")
    cls_logger = logging.getLogger("test_otel_logging_unparseable_endpoint")
    cls_logger.handlers.clear()

    configure_otel_logging(cls_logger)

    assert cls_logger.handlers == []


@pytest.mark.parametrize(
    ("str_endpoint", "bool_has_headers", "bool_expected"),
    [
        ("http://collector.example:4318", True, True),
        ("http://localhost:4318", True, False),
        ("http://127.0.0.1:4318", True, False),
        ("http://[::1]:4318", True, False),
        ("https://collector.example:4318", True, False),
        ("http://collector.example:4318", False, False),
        ("", True, False),
        ("", False, False),
        ("http://[", True, True),
        ("https://[", True, True),
        ("http://[", False, False),
    ],
)
def test_is_cleartext_with_credentials_truth_table(
    str_endpoint: str, *, bool_has_headers: bool, bool_expected: bool
) -> None:
    """Pin the predicate: off-host cleartext or unparseable endpoint, with headers, is refused."""
    assert (
        _is_cleartext_with_credentials(str_endpoint, bool_has_headers=bool_has_headers)
        is bool_expected
    )
