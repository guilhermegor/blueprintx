"""Unit tests for ``check_gate_integrity.py``.

Covers two independent regressions guarded by the same gate:

**The local ``GATE_CHANGE_OK`` escape hatch (blueprintx#354).** The gate's OTHER two
justification sources — the PR body and a commit trailer — already have should-fail/should-pass
coverage in ``test_backlog_ledger.py`` (where ``check_gate_integrity`` was first loaded for its
assertion-integrity tests). This half covers only what #354 added: the ``GATE_CHANGE_OK``
environment variable, the one source reachable at the moment the gate fires locally — a
``pre-commit`` run, before the commit exists and before any PR does.

**The gate-count-never-decreases regression (blueprintx#359).** THE DEFECT THIS PINS: resolving
a merge conflict in a WIRING file (``.pre-commit-config.yaml``, a ``.github/workflows/*.yml``) by
keeping one side's newly-added entry silently drops the other side's — producing a valid,
parseable, plausible file with one gate missing. Measured twice on this repo (blueprintx#312
dropped ``gate-integrity`` from ``scaffold_checks.yml`` while keeping ``docs-code-refs``;
blueprintx#310 dropped it from ``.pre-commit-config.yaml`` while keeping ``check-secrets``) — both
found BY HAND, because ``check_gate_integrity.py`` (blueprintx#313) did not exist yet when either
PR merged. ``gate-integrity`` is itself a REQUIRED status check, so either resolution would have
removed a required check from main's wiring while every other signal stayed green.

``check_gate_integrity.py`` already carries the SET comparison this class of defect needs —
``precommit_problems``/``workflow_problems`` diff hook ids / job keys between two versions of one
file and report exactly what is MISSING BY NAME, matching blueprintx#359's own requirement ("a set
comparison, not a count" — a renamed hook changes membership without changing the count, and a
bare "one fewer hook" sends the reader hunting). What was missing was proof: this module is the
should-fail/should-pass witness, replaying the literal #312/#310 shape (one side's addition
survives, the other's silently disappears), confirming an unrelated addition alone stays clean, and
confirming the ``gate-change-ok:`` escape hatch still lets a genuinely justified removal (a
deliberate rename) through ``report()``.
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
		The imported module — importing the file the project actually ships, not a copy.
	"""
	cls_spec = importlib.util.spec_from_file_location(str_name, _BIN / f"{str_name}.py")
	cls_module = importlib.util.module_from_spec(cls_spec)
	sys.modules[str_name] = cls_module
	cls_spec.loader.exec_module(cls_module)
	return cls_module


gate = _load("check_gate_integrity")


# --------------------------
# Tests — the GATE_CHANGE_OK local escape hatch (blueprintx#354)
# --------------------------


def _local_shell(monkeypatch: pytest.MonkeyPatch) -> None:  # complexity-ok: clears N markers
	"""Clear the CI markers so the GATE_CHANGE_OK hatch is live (it is local-only).

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		The fixture whose ``delenv`` is applied to every marker.
	"""
	for str_marker in gate.TUPLE_CI_MARKERS:
		monkeypatch.delenv(str_marker, raising=False)


def test_env_reason_is_blank_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
	"""No ``GATE_CHANGE_OK`` set means no local justification."""
	_local_shell(monkeypatch)
	monkeypatch.delenv("GATE_CHANGE_OK", raising=False)
	assert gate.env_reason() == ""


def test_env_reason_returns_the_stripped_value(monkeypatch: pytest.MonkeyPatch) -> None:
	"""A real reason satisfies the hatch, whitespace and all — stripped for the caller."""
	_local_shell(monkeypatch)
	monkeypatch.setenv("GATE_CHANGE_OK", "  reviewed, main's own ignores  ")
	assert gate.env_reason() == "reviewed, main's own ignores"


def test_env_reason_rejects_whitespace_only(monkeypatch: pytest.MonkeyPatch) -> None:
	"""⚠️ A blank reason must NOT satisfy the hatch — same rule as `# complexity-ok: <reason>`."""
	_local_shell(monkeypatch)
	monkeypatch.setenv("GATE_CHANGE_OK", "   ")
	assert gate.env_reason() == ""


def test_justification_reason_prefers_env_without_calling_git(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""⚠️ THE SHOULD-PASS WITNESS: reachable with NEITHER a finished commit NOR a PR.

	`_git` and `pr_body_text` are the two sources measured unreachable at local `pre-commit`
	time (blueprintx#354) — this asserts the env source satisfies the gate WITHOUT reaching
	either, matching what is actually available at that moment.
	"""
	_local_shell(monkeypatch)
	monkeypatch.setenv("GATE_CHANGE_OK", "local merge from main, ignores already reviewed there")
	monkeypatch.setattr(
		gate, "_git", lambda _args: (_ for _ in ()).throw(AssertionError("git called"))
	)
	monkeypatch.setattr(
		gate,
		"pr_body_text",
		lambda: (_ for _ in ()).throw(AssertionError("pr_body_text called")),
	)
	assert (
		gate.justification_reason("deadbeef")
		== "local merge from main, ignores already reviewed there"
	)


def test_justification_reason_falls_back_when_env_is_blank(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""NEGATIVE CONTROL: an unset/blank env var must not mask a real trailer/PR-body reason."""
	_local_shell(monkeypatch)
	monkeypatch.delenv("GATE_CHANGE_OK", raising=False)
	monkeypatch.setattr(gate, "_git", lambda _args: "gate-change-ok: from trailer")
	monkeypatch.setattr(gate, "pr_body_text", lambda: "")
	assert gate.justification_reason("deadbeef") == "from trailer"


def test_report_fails_a_real_weakening_with_no_local_justification(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Both directions, part 1: a weakening with nothing set must still FAIL at commit time."""
	_local_shell(monkeypatch)
	monkeypatch.delenv("GATE_CHANGE_OK", raising=False)
	monkeypatch.setattr(gate, "_git", lambda _args: "")
	monkeypatch.setattr(gate, "pr_body_text", lambda: "")
	assert gate.report(["ruff.toml: rule 'S608' added to [lint] ignore"], "base", 1) == 1


def test_report_passes_the_same_weakening_with_gate_change_ok_set(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Both directions, part 2: the SAME finding, justified only via GATE_CHANGE_OK, must PASS."""
	_local_shell(monkeypatch)
	monkeypatch.setenv("GATE_CHANGE_OK", "reviewed with the team")
	monkeypatch.setattr(gate, "_git", lambda _args: "")
	monkeypatch.setattr(gate, "pr_body_text", lambda: "")
	assert gate.report(["ruff.toml: rule 'S608' added to [lint] ignore"], "base", 1) == 0


def test_report_rejects_a_whitespace_only_gate_change_ok(monkeypatch: pytest.MonkeyPatch) -> None:
	"""A blank-looking reason must still FAIL — matching the trailer/PR-body rule exactly."""
	_local_shell(monkeypatch)
	monkeypatch.setenv("GATE_CHANGE_OK", "   ")
	monkeypatch.setattr(gate, "_git", lambda _args: "")
	monkeypatch.setattr(gate, "pr_body_text", lambda: "")
	assert gate.report(["ruff.toml: rule 'S608' added to [lint] ignore"], "base", 1) == 1


@pytest.mark.parametrize("str_marker", ["CI", "GITHUB_ACTIONS"])
def test_env_reason_is_ignored_under_ci(monkeypatch: pytest.MonkeyPatch, str_marker: str) -> None:
	"""The hatch is LOCAL-ONLY: a CI runner exposing it must not be able to justify anything."""
	_local_shell(monkeypatch)
	monkeypatch.setenv("GATE_CHANGE_OK", "set by a workflow env: line, not by a reviewer")
	monkeypatch.setenv(str_marker, "true")
	assert gate.env_reason() == ""


def test_report_rejects_a_ci_set_gate_change_ok(monkeypatch: pytest.MonkeyPatch) -> None:
	"""The end-to-end half: the SAME weakening that PASSES locally must FAIL under CI.

	Paired with ``test_report_passes_the_same_weakening_with_gate_change_ok_set`` — the two
	differ only in whether a CI marker is set, so neither can pass with the guard removed.
	"""
	_local_shell(monkeypatch)
	monkeypatch.setenv("GATE_CHANGE_OK", "reviewed with the team")
	monkeypatch.setenv("GITHUB_ACTIONS", "true")
	monkeypatch.setattr(gate, "_git", lambda _args: "")
	monkeypatch.setattr(gate, "pr_body_text", lambda: "")
	assert gate.report(["ruff.toml: rule 'S608' added to [lint] ignore"], "base", 1) == 1


# --------------------------
# Fixtures — minimal wiring-file shapes, real anchors from this repo's own files
# (blueprintx#359 — gate-count-never-decreases regression)
# --------------------------

_STR_PRECOMMIT_BASE = (
	"repos:\n"
	"  - repo: local\n"
	"    hooks:\n"
	"      - id: gate-integrity\n"
	"        name: gate integrity\n"
	"        entry: python3 check_gate_integrity.py\n"
	"      - id: some-other-hook\n"
	"        name: some other hook\n"
)

_STR_WORKFLOW_BASE = (
	"jobs:\n"
	"  gate-integrity:\n"
	"    name: Gate integrity\n"
	"    runs-on: ubuntu-latest\n"
	"  some-other-job:\n"
	"    name: Some other job\n"
	"    runs-on: ubuntu-latest\n"
)


# --------------------------
# Tests — precommit_problems (blueprintx#310's own shape)
# --------------------------


def test_precommit_conflict_resolution_drops_gate_integrity_310_shape() -> None:
	"""Replay #310: keeping ``check-secrets`` while dropping ``gate-integrity`` is caught."""
	str_new = (
		"repos:\n"
		"  - repo: local\n"
		"    hooks:\n"
		"      - id: check-secrets\n"
		"        name: secret scan (gitleaks)\n"
		"      - id: some-other-hook\n"
		"        name: some other hook\n"
	)

	str_shown = ".pre-commit-config.yaml"
	list_problems = gate.precommit_problems(_STR_PRECOMMIT_BASE, str_new, str_shown)

	assert len(list_problems) == 1
	assert "gate-integrity" in list_problems[0]
	assert "removed" in list_problems[0]


def test_precommit_both_sides_kept_is_clean() -> None:
	"""Keeping BOTH concurrently-added hooks (the correct resolution) reports nothing."""
	str_new = (
		"repos:\n"
		"  - repo: local\n"
		"    hooks:\n"
		"      - id: gate-integrity\n"
		"        name: gate integrity\n"
		"        entry: python3 check_gate_integrity.py\n"
		"      - id: check-secrets\n"
		"        name: secret scan (gitleaks)\n"
		"      - id: some-other-hook\n"
		"        name: some other hook\n"
	)

	assert gate.precommit_problems(_STR_PRECOMMIT_BASE, str_new, ".pre-commit-config.yaml") == []


def test_precommit_unrelated_addition_alone_is_clean() -> None:
	"""Adding a hook without touching any existing one reports nothing (no false positive)."""
	str_new = _STR_PRECOMMIT_BASE + "      - id: brand-new-hook\n        name: brand new\n"

	assert gate.precommit_problems(_STR_PRECOMMIT_BASE, str_new, ".pre-commit-config.yaml") == []


# --------------------------
# Tests — workflow_problems (blueprintx#312's own shape)
# --------------------------


def test_workflow_conflict_resolution_drops_gate_integrity_312_shape() -> None:
	"""Replay #312: keeping ``docs-code-refs`` while dropping ``gate-integrity`` is caught."""
	str_new = (
		"jobs:\n"
		"  docs-code-refs:\n"
		"    name: Docs code references\n"
		"    runs-on: ubuntu-latest\n"
		"  some-other-job:\n"
		"    name: Some other job\n"
		"    runs-on: ubuntu-latest\n"
	)

	list_problems = gate.workflow_problems(_STR_WORKFLOW_BASE, str_new, "scaffold_checks.yml")

	assert len(list_problems) == 1
	assert "gate-integrity" in list_problems[0]
	assert "removed" in list_problems[0]


def test_workflow_both_sides_kept_is_clean() -> None:
	"""Keeping BOTH concurrently-added jobs (the correct resolution) reports nothing."""
	str_new = (
		"jobs:\n"
		"  gate-integrity:\n"
		"    name: Gate integrity\n"
		"    runs-on: ubuntu-latest\n"
		"  docs-code-refs:\n"
		"    name: Docs code references\n"
		"    runs-on: ubuntu-latest\n"
		"  some-other-job:\n"
		"    name: Some other job\n"
		"    runs-on: ubuntu-latest\n"
	)

	assert gate.workflow_problems(_STR_WORKFLOW_BASE, str_new, "scaffold_checks.yml") == []


def test_workflow_unrelated_addition_alone_is_clean() -> None:
	"""Adding a job without touching any existing one reports nothing (no false positive)."""
	str_new = (
		_STR_WORKFLOW_BASE + "  brand-new-job:\n    name: Brand new\n    runs-on: ubuntu-latest\n"
	)

	assert gate.workflow_problems(_STR_WORKFLOW_BASE, str_new, "scaffold_checks.yml") == []


# --------------------------
# Tests — report() + the gate-change-ok escape hatch (a legitimate rename must stay payable)
# --------------------------


def test_report_unjustified_gate_drop_fails(monkeypatch: pytest.MonkeyPatch) -> None:
	"""A dropped id with no ``gate-change-ok:`` trailer/PR-body reason fails the run."""
	monkeypatch.setattr(gate, "justification_reason", lambda str_base: "")
	str_finding = "scaffold_checks.yml: workflow job 'gate-integrity' removed"

	int_code = gate.report([str_finding], "base", 1)

	assert int_code == 1


def test_report_justified_gate_drop_passes(monkeypatch: pytest.MonkeyPatch) -> None:
	"""The SAME finding passes once a non-empty ``gate-change-ok:`` reason resolves.

	This is the escape hatch a legitimate rename (rather than a silent drop) relies on — the
	gate must stay payable for real work, not merely loud on the defect it was built for.
	"""
	monkeypatch.setattr(gate, "justification_reason", lambda str_base: "renamed, see PR body")
	str_finding = "scaffold_checks.yml: workflow job 'gate-integrity' removed"

	int_code = gate.report([str_finding], "base", 1)

	assert int_code == 0


def test_report_no_findings_passes() -> None:
	"""An empty findings list passes without consulting the justification hatch at all."""
	assert gate.report([], "base", 3) == 0
