"""Unit tests for the multi-intent dispatch (``pipeline_dispatch``), native DB.

Multi-intent mode removes ``src/controller/_pipeline.py`` (swapped for the
``pipeline_<intent>.py`` trio + ``pipeline_dispatch.py`` — see
``conditional_apply_multi_pipeline`` in ``bin/scaffold/python_mvc_service.sh``), so the
single-mode ``test_pipeline.py`` (which imports ``controller._pipeline``) does not apply here;
this file replaces it in multi-intent scaffolds. It covers what multi-intent mode ships
instead: intent resolution (``resolve_intent`` — bilingual, case/accent-insensitive, fail-loud
on a typo) and pipeline construction (``build_pipeline`` — one dispatch-table entry per
``pipeline_<intent>.py``), so the dispatch mechanism is not left untested in the one mode
that has it.
"""

from pathlib import Path

import pytest

from controller.pipeline_dispatch import build_pipeline, resolve_intent
from controller.pipeline_reconcile import ReconcilePipeline
from controller.pipeline_send import SendPipeline


# --------------------------
# Helpers
# --------------------------
def _build_args(tmp_path: Path) -> tuple:
    """Return the positional collaborator args every ``pipeline_<intent>`` constructor accepts.

    Positional (not keyword) on purpose: the third parameter's name differs between the
    native-DB tier (``fn_build_connection``) and the ORM tier (``fn_build_engine``), so a
    positional call is the form both tiers' copies of this test can share unchanged.

    Parameters
    ----------
    tmp_path : pathlib.Path
            Pytest-provided temporary directory.

    Returns
    -------
    tuple
            ``(logger, fn_build_connection, fn_output_path, path_json, dict_context)``.
    """
    return (
        None,
        lambda: None,
        lambda str_key: tmp_path / str_key,
        tmp_path / "summary.json",
        {},
    )


# --------------------------
# resolve_intent
# --------------------------
@pytest.mark.parametrize(
    ("str_raw", "str_expected"),
    [
        ("send", "send"),
        ("Send", "send"),
        ("ENVIO", "send"),
        ("envio", "send"),
        ("reconcile", "reconcile"),
        ("Reconcile", "reconcile"),
        ("reconciliacao", "reconcile"),
        ("Reconciliação", "reconcile"),
    ],
)
def test_resolve_intent_maps_known_spelling_to_canonical_intent(
    str_raw: str, str_expected: str
) -> None:
    """Every documented spelling (English/pt-BR, any case/accent) maps to ITS canonical intent.

    Equality, not membership: `in {"send", "reconcile"}` passes even when a spelling resolves to
    the wrong one of the two, which is the mapping this test exists to pin.

    Parameters
    ----------
    str_raw : str
            A raw ``PIPELINE_INTENT`` spelling under test.
    str_expected : str
            The canonical intent that spelling must resolve to.

    Returns
    -------
    None
    """
    assert resolve_intent(str_raw) == str_expected


def test_resolve_intent_raises_systemexit_on_unknown_spelling() -> None:
    """An unrecognised ``PIPELINE_INTENT`` value fails loud with exit code 2.

    Returns
    -------
    None
    """
    with pytest.raises(SystemExit) as cls_exc_info:
        resolve_intent("not-a-real-intent")
    assert cls_exc_info.value.code == 2


# --------------------------
# build_pipeline
# --------------------------
def test_build_pipeline_returns_send_pipeline_for_send_intent(tmp_path: Path) -> None:
    """``build_pipeline("send", ...)`` constructs the ``send`` orchestrator.

    Parameters
    ----------
    tmp_path : pathlib.Path
            Pytest-provided temporary directory.

    Returns
    -------
    None
    """
    cls_pipeline = build_pipeline("send", *_build_args(tmp_path))
    assert isinstance(cls_pipeline, SendPipeline)


def test_build_pipeline_returns_reconcile_pipeline_for_reconcile_intent(tmp_path: Path) -> None:
    """``build_pipeline("reconcile", ...)`` constructs the ``reconcile`` orchestrator.

    Parameters
    ----------
    tmp_path : pathlib.Path
            Pytest-provided temporary directory.

    Returns
    -------
    None
    """
    cls_pipeline = build_pipeline("reconcile", *_build_args(tmp_path))
    assert isinstance(cls_pipeline, ReconcilePipeline)


def test_build_pipeline_raises_systemexit_on_unregistered_intent(tmp_path: Path) -> None:
    """``build_pipeline`` fails loud (exit code 2) for an intent with no dispatch entry.

    Parameters
    ----------
    tmp_path : pathlib.Path
            Pytest-provided temporary directory.

    Returns
    -------
    None
    """
    with pytest.raises(SystemExit) as cls_exc_info:
        build_pipeline("not-a-real-intent", *_build_args(tmp_path))
    assert cls_exc_info.value.code == 2
