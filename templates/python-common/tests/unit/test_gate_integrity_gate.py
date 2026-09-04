"""Unit tests for the local-commit-time escape hatch (blueprintx#354).

The gate's OTHER two justification sources — the PR body and a commit trailer — already have
should-fail/should-pass coverage in ``test_backlog_ledger.py`` (where ``check_gate_integrity``
was first loaded for its assertion-integrity tests). This file covers only what #354 added: the
``GATE_CHANGE_OK`` environment variable, the one source reachable at the moment the gate fires
locally — a ``pre-commit`` run, before the commit exists and before any PR does.
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


_BIN = Path(__file__).resolve().parents[2] / "bin"


def _load(str_name: str) -> ModuleType:
	"""Load a ``bin/`` script by path (``bin/`` is not a package).

	Parameters
	----------
	str_name : str
		Module stem under ``bin/``.

	Returns
	-------
	ModuleType
		The imported module.
	"""
	cls_spec = importlib.util.spec_from_file_location(str_name, _BIN / f"{str_name}.py")
	cls_module = importlib.util.module_from_spec(cls_spec)
	sys.modules[str_name] = cls_module
	cls_spec.loader.exec_module(cls_module)
	return cls_module


gate_integrity = _load("check_gate_integrity")


def test_env_reason_is_blank_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
	"""No ``GATE_CHANGE_OK`` set means no local justification."""
	monkeypatch.delenv("GATE_CHANGE_OK", raising=False)
	assert gate_integrity.env_reason() == ""


def test_env_reason_returns_the_stripped_value(monkeypatch: pytest.MonkeyPatch) -> None:
	"""A real reason satisfies the hatch, whitespace and all — stripped for the caller."""
	monkeypatch.setenv("GATE_CHANGE_OK", "  reviewed, main's own ignores  ")
	assert gate_integrity.env_reason() == "reviewed, main's own ignores"


def test_env_reason_rejects_whitespace_only(monkeypatch: pytest.MonkeyPatch) -> None:
	"""⚠️ A blank reason must NOT satisfy the hatch — same rule as `# complexity-ok: <reason>`."""
	monkeypatch.setenv("GATE_CHANGE_OK", "   ")
	assert gate_integrity.env_reason() == ""


def test_justification_reason_prefers_env_without_calling_git(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""⚠️ THE SHOULD-PASS WITNESS: reachable with NEITHER a finished commit NOR a PR.

	`_git` and `pr_body_text` are the two sources measured unreachable at local `pre-commit`
	time (blueprintx#354) — this asserts the env source satisfies the gate WITHOUT reaching
	either, matching what is actually available at that moment.
	"""
	monkeypatch.setenv("GATE_CHANGE_OK", "local merge from main, ignores already reviewed there")
	monkeypatch.setattr(
		gate_integrity, "_git", lambda _args: (_ for _ in ()).throw(AssertionError("git called"))
	)
	monkeypatch.setattr(
		gate_integrity,
		"pr_body_text",
		lambda: (_ for _ in ()).throw(AssertionError("pr_body_text called")),
	)
	assert (
		gate_integrity.justification_reason("deadbeef")
		== "local merge from main, ignores already reviewed there"
	)


def test_justification_reason_falls_back_when_env_is_blank(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""NEGATIVE CONTROL: an unset/blank env var must not mask a real trailer/PR-body reason."""
	monkeypatch.delenv("GATE_CHANGE_OK", raising=False)
	monkeypatch.setattr(gate_integrity, "_git", lambda _args: "gate-change-ok: from trailer")
	monkeypatch.setattr(gate_integrity, "pr_body_text", lambda: "")
	assert gate_integrity.justification_reason("deadbeef") == "from trailer"


def test_report_fails_a_real_weakening_with_no_local_justification(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Both directions, part 1: a weakening with nothing set must still FAIL at commit time."""
	monkeypatch.delenv("GATE_CHANGE_OK", raising=False)
	monkeypatch.setattr(gate_integrity, "_git", lambda _args: "")
	monkeypatch.setattr(gate_integrity, "pr_body_text", lambda: "")
	assert gate_integrity.report(["ruff.toml: rule 'S608' added to [lint] ignore"], "base", 1) == 1


def test_report_passes_the_same_weakening_with_gate_change_ok_set(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Both directions, part 2: the SAME finding, justified only via GATE_CHANGE_OK, must PASS."""
	monkeypatch.setenv("GATE_CHANGE_OK", "reviewed with the team")
	monkeypatch.setattr(gate_integrity, "_git", lambda _args: "")
	monkeypatch.setattr(gate_integrity, "pr_body_text", lambda: "")
	assert gate_integrity.report(["ruff.toml: rule 'S608' added to [lint] ignore"], "base", 1) == 0


def test_report_rejects_a_whitespace_only_gate_change_ok(monkeypatch: pytest.MonkeyPatch) -> None:
	"""A blank-looking reason must still FAIL — matching the trailer/PR-body rule exactly."""
	monkeypatch.setenv("GATE_CHANGE_OK", "   ")
	monkeypatch.setattr(gate_integrity, "_git", lambda _args: "")
	monkeypatch.setattr(gate_integrity, "pr_body_text", lambda: "")
	assert gate_integrity.report(["ruff.toml: rule 'S608' added to [lint] ignore"], "base", 1) == 1
