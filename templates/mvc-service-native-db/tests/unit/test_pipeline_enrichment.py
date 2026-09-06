"""Unit tests for ``PipelineOrchestrator._enrich`` (native DB).

Covers issue #151: a documented graceful degradation is a contract, not a docstring claim —
it holds only if EVERY failure mode that can prevent the enrichment reaches the same explicit
degraded value. Five modes are exercised here (missing config, absent file, malformed file,
permission error, an unforeseen failure); each gets its own test so a fix that only guards one
mode cannot pass by accident. Modes 1-3 exercise the real read; permission error and the
unforeseen-failure mode are mocked because they cannot be reproduced deterministically as real
I/O. ``test_enrich_degrades_on_permission_error`` is the canonical regression: it is RED
against the pre-#151 shape (the read call unwrapped) and GREEN once the call is wrapped — see
docs/architecture.md#enrichment-degradation-contract.
"""

from pathlib import Path

import pandas as pd
from pytest_mock import MockerFixture

from src.controller._pipeline import PipelineOrchestrator


# --------------------------
# Helpers
# --------------------------
def _build_orchestrator(tmp_path: Path, path_labels: Path | None) -> PipelineOrchestrator:
	"""Build a minimal orchestrator for exercising ``_enrich`` in isolation.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest-provided temporary directory, used for the unused JSON summary path.
	path_labels : pathlib.Path | None
		The labels path to inject via ``dict_context`` (``None`` to exercise the
		missing-config mode).

	Returns
	-------
	PipelineOrchestrator
		An orchestrator wired only with what ``_enrich`` needs.
	"""
	return PipelineOrchestrator(
		logger=None,
		fn_build_connection=lambda: None,
		fn_output_path=lambda str_key: tmp_path / str_key,
		path_json=tmp_path / "summary.json",
		dict_context={"path_labels": path_labels} if path_labels is not None else {},
	)


def _report() -> pd.DataFrame:
	"""Build the minimal report frame ``_enrich`` merges labels onto.

	Returns
	-------
	pandas.DataFrame
		One row, matching ``model.example_entity``'s ``id``/``title`` schema.
	"""
	return pd.DataFrame({"id": [1], "title": ["Hello from MVC native-db service!"]})


# --------------------------
# Tests — the five degradation modes
# --------------------------
def test_enrich_degrades_when_path_labels_not_configured(
	tmp_path: Path, mocker: MockerFixture
) -> None:
	"""Mode 1: no ``path_labels`` configured — no call attempted, report returned unchanged."""
	mock_log = mocker.patch("src.controller._pipeline.log_message")
	df_report = _report()
	df_result = _build_orchestrator(tmp_path, path_labels=None)._enrich(df_report)
	pd.testing.assert_frame_equal(df_result, df_report)
	str_log = "\n".join(call.args[1] for call in mock_log.call_args_list)
	assert "Label enrichment skipped" in str_log


def test_enrich_degrades_on_absent_file(tmp_path: Path, mocker: MockerFixture) -> None:
	"""Mode 2: the configured file does not exist on disk (real read attempt)."""
	mock_log = mocker.patch("src.controller._pipeline.log_message")
	df_report = _report()
	path_labels = tmp_path / "does-not-exist.json"
	df_result = _build_orchestrator(tmp_path, path_labels)._enrich(df_report)
	pd.testing.assert_frame_equal(df_result, df_report)
	str_log = "\n".join(call.args[1] for call in mock_log.call_args_list)
	assert "FileNotFoundError" in str_log


def test_enrich_degrades_on_malformed_file(tmp_path: Path, mocker: MockerFixture) -> None:
	"""Mode 3: the file exists but is not valid JSON (real read attempt)."""
	mock_log = mocker.patch("src.controller._pipeline.log_message")
	df_report = _report()
	path_labels = tmp_path / "labels.json"
	path_labels.write_text("{not valid json")
	df_result = _build_orchestrator(tmp_path, path_labels)._enrich(df_report)
	pd.testing.assert_frame_equal(df_result, df_report)
	str_log = "\n".join(call.args[1] for call in mock_log.call_args_list)
	assert "JSONDecodeError" in str_log


def test_enrich_degrades_on_permission_error(tmp_path: Path, mocker: MockerFixture) -> None:
	"""Mode 4 (canonical regression, #151): the file exists but cannot be read.

	This is the exact shape of the measured incident: an unreadable file must degrade, not
	raise and kill a run whose upstream read already succeeded.
	"""
	mock_log = mocker.patch("src.controller._pipeline.log_message")
	path_labels = tmp_path / "labels.json"
	path_labels.write_text('{"1": "demo"}')
	mocker.patch.object(Path, "open", side_effect=PermissionError("labels.json"))
	df_report = _report()
	df_result = _build_orchestrator(tmp_path, path_labels)._enrich(df_report)
	pd.testing.assert_frame_equal(df_result, df_report)
	str_log = "\n".join(call.args[1] for call in mock_log.call_args_list)
	assert "PermissionError" in str_log


def test_enrich_degrades_on_unforeseen_failure(tmp_path: Path, mocker: MockerFixture) -> None:
	"""Mode 5: an unforeseen error unrelated to the file's existence or shape."""
	mock_log = mocker.patch("src.controller._pipeline.log_message")
	mocker.patch(
		"src.controller._pipeline.json.load",
		side_effect=RuntimeError("unexpected failure"),
	)
	df_report = _report()
	path_labels = tmp_path / "labels.json"
	path_labels.write_text('{"1": "demo"}')
	df_result = _build_orchestrator(tmp_path, path_labels)._enrich(df_report)
	pd.testing.assert_frame_equal(df_result, df_report)
	str_log = "\n".join(call.args[1] for call in mock_log.call_args_list)
	assert "RuntimeError" in str_log


# --------------------------
# Tests — the happy path and phase ordering
# --------------------------
def test_enrich_merges_labels_when_file_is_valid(tmp_path: Path) -> None:
	"""When the labels file is present and well-formed, the merge actually runs."""
	df_report = _report()
	path_labels = tmp_path / "labels.json"
	path_labels.write_text('{"1": "demo-label"}')
	df_result = _build_orchestrator(tmp_path, path_labels)._enrich(df_report)
	assert df_result.loc[0, "label"] == "demo-label"


def test_run_sequences_enrich_before_render(tmp_path: Path, mocker: MockerFixture) -> None:
	"""Phase ordering: ``_enrich`` runs before ``_render``, i.e. before persistence.

	A failure inside ``_enrich`` must never be able to invalidate an already-persisted
	report — which is only guaranteed if enrichment runs strictly before render.
	"""
	cls_orchestrator = _build_orchestrator(tmp_path, path_labels=None)
	mocker.patch.object(cls_orchestrator, "_log_context")
	mocker.patch.object(cls_orchestrator, "_open_connection", return_value=mocker.MagicMock())
	df_report = _report()
	mocker.patch.object(cls_orchestrator, "_read", return_value=df_report)
	mocker.patch.object(cls_orchestrator, "_write_summary")
	mocker.patch.object(cls_orchestrator, "_notify")
	list_call_order: list[str] = []
	mocker.patch.object(
		cls_orchestrator,
		"_enrich",
		side_effect=lambda df: list_call_order.append("_enrich") or df,
	)
	mocker.patch.object(
		cls_orchestrator,
		"_render",
		side_effect=lambda df: list_call_order.append("_render") or (tmp_path / "r.xlsx"),
	)
	cls_orchestrator.run()
	assert list_call_order == ["_enrich", "_render"]
