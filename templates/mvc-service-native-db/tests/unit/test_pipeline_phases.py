"""Unit tests for the ``PipelineOrchestrator`` phases not covered elsewhere (native DB).

``test_pipeline.py`` covers ``_notify`` and ``test_pipeline_enrichment.py`` covers ``_enrich``
and the enrich/render ordering. This file covers the remaining phases — ``_log_context``,
``_open_connection``, ``_read``, ``_render``, ``_write_summary`` and the whole ``run()`` —
against a throwaway SQLite file, so the read phase proves a row really comes back through the
model instead of asserting that a mock was called.
"""

import contextlib
import json
from pathlib import Path
import sqlite3
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from src.controller._pipeline import PipelineOrchestrator, WebhookNotifier


STR_SEED_TITLE = "Hello from MVC native-db service!"


# --------------------------
# Helpers and fixtures
# --------------------------
@pytest.fixture
def cls_connection(tmp_path: Path) -> sqlite3.Connection:
    """Provide a connection to a throwaway SQLite database file.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided temporary directory.

    Returns
    -------
    sqlite3.Connection
        Connection for ``tmp_path / "pipeline.db"``.
    """
    return sqlite3.connect(tmp_path / "pipeline.db")


def _build_orchestrator(
    tmp_path: Path, cls_connection: sqlite3.Connection, **kwargs: object
) -> PipelineOrchestrator:
    """Build an orchestrator wired to a real connection and ``tmp_path`` outputs.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided temporary directory, used for the report and the summary.
    cls_connection : sqlite3.Connection
        Connection returned by ``fn_build_connection``.
    **kwargs : object
        Extra ``PipelineOrchestrator`` keyword arguments (``dict_context``, ...).

    Returns
    -------
    PipelineOrchestrator
        Orchestrator whose phases run against ``cls_connection`` and write into ``tmp_path``.
    """
    return PipelineOrchestrator(
        logger=None,
        fn_build_connection=lambda: cls_connection,
        fn_output_path=lambda str_key: tmp_path / f"{str_key}.xlsx",
        path_json=tmp_path / "summary.json",
        **{"dict_context": {}, **kwargs},
    )


def _logged(mock_log: Mock) -> str:
    """Join every message passed to a patched ``log_message``.

    Parameters
    ----------
    mock_log : unittest.mock.Mock
        The patched ``log_message``.

    Returns
    -------
    str
        One line per logged message.
    """
    return "\n".join(call.args[1] for call in mock_log.call_args_list)


# --------------------------
# _log_context
# --------------------------
def test_log_context_logs_one_line_per_context_item(
    tmp_path: Path, cls_connection: sqlite3.Connection, mocker: MockerFixture
) -> None:
    """Every ``dict_context`` entry is logged as ``key: value`` (a self-describing log)."""
    mock_log = mocker.patch("src.controller._pipeline.log_message")
    _build_orchestrator(tmp_path, cls_connection, dict_context={"App": "demo"})._log_context()

    assert "App: demo" in _logged(mock_log)


def test_log_context_reports_no_handlers_when_none_are_wired(
    tmp_path: Path, cls_connection: sqlite3.Connection, mocker: MockerFixture
) -> None:
    """With no e-mail handler and no webhook, both lines say ``none``."""
    mock_log = mocker.patch("src.controller._pipeline.log_message")
    _build_orchestrator(tmp_path, cls_connection)._log_context()

    assert "Email handler: none\nWebhook notifier: none" in _logged(mock_log)


def test_log_context_reports_a_configured_webhook(
    tmp_path: Path, cls_connection: sqlite3.Connection, mocker: MockerFixture
) -> None:
    """A wired webhook is reported as ``configured``."""
    mock_log = mocker.patch("src.controller._pipeline.log_message")
    _build_orchestrator(
        tmp_path, cls_connection, cls_webhook=Mock(spec=WebhookNotifier)
    )._log_context()

    assert "Webhook notifier: configured" in _logged(mock_log)


# --------------------------
# _open_connection and _read
# --------------------------
def test_open_connection_returns_what_the_factory_builds(
    tmp_path: Path, cls_connection: sqlite3.Connection
) -> None:
    """``_open_connection`` hands back the connection the injected factory built."""
    assert _build_orchestrator(tmp_path, cls_connection)._open_connection() is cls_connection


def test_read_returns_the_seeded_row_through_the_model(
    tmp_path: Path, cls_connection: sqlite3.Connection
) -> None:
    """The read phase creates the table, seeds one row and returns it as a frame."""
    df_report = _build_orchestrator(tmp_path, cls_connection)._read(cls_connection)

    assert df_report["title"].tolist() == [STR_SEED_TITLE]


# --------------------------
# _render and _write_summary
# --------------------------
def test_render_writes_the_report_at_the_resolved_path(
    tmp_path: Path, cls_connection: sqlite3.Connection
) -> None:
    """``_render`` asks the resolver for ``xlsx_name`` and writes the workbook there."""
    cls_orchestrator = _build_orchestrator(tmp_path, cls_connection)
    path_report = cls_orchestrator._render(cls_orchestrator._read(cls_connection))

    assert path_report == tmp_path / "xlsx_name.xlsx"


def test_render_leaves_the_workbook_on_disk(
    tmp_path: Path, cls_connection: sqlite3.Connection
) -> None:
    """The path ``_render`` returns is a file that exists."""
    cls_orchestrator = _build_orchestrator(tmp_path, cls_connection)

    assert cls_orchestrator._render(cls_orchestrator._read(cls_connection)).exists()


def test_write_summary_persists_the_summary_as_json(
    tmp_path: Path, cls_connection: sqlite3.Connection
) -> None:
    """``_write_summary`` round-trips the summary through ``summary.json``."""
    dict_summary = {"rows_read": 1, "report_path": "r.xlsx"}
    _build_orchestrator(tmp_path, cls_connection)._write_summary(dict_summary)

    assert json.loads((tmp_path / "summary.json").read_text()) == dict_summary


# --------------------------
# The whole run
# --------------------------
def test_run_returns_the_summary_of_the_rows_read(
    tmp_path: Path, cls_connection: sqlite3.Connection
) -> None:
    """``run()`` end to end reads the seeded row and reports it in the summary."""
    dict_summary = _build_orchestrator(tmp_path, cls_connection).run()

    assert dict_summary["rows_read"] == 1


def test_run_closes_the_connection_even_when_the_read_fails(
    tmp_path: Path, cls_connection: sqlite3.Connection, mocker: MockerFixture
) -> None:
    """The connection is closed in a ``finally``, so a failing read cannot leak it."""
    cls_orchestrator = _build_orchestrator(tmp_path, cls_connection)
    mocker.patch.object(cls_orchestrator, "_read", side_effect=RuntimeError("boom"))
    mock_connection = Mock()
    cls_orchestrator.fn_build_connection = lambda: mock_connection
    with contextlib.suppress(RuntimeError):
        cls_orchestrator.run()

    mock_connection.close.assert_called_once_with()
