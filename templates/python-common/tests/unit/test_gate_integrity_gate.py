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
import subprocess
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
gate_env = sys.modules["gate_env"]
gate_rename = _load("gate_rename")
weakening = _load("check_assertion_weakening")


def _local_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a local pre-commit run so the GATE_CHANGE_OK hatch is live (it is local-only).

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The fixture whose ``delenv`` is applied to every marker.
    """
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("PRE_COMMIT", "1")
    monkeypatch.setattr(gate_env, "has_terminal", lambda: True)


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


@pytest.fixture
def list_precommit_310_problems() -> list[str]:
    """Return the findings for #310's shape: ``check-secrets`` kept, ``gate-integrity`` dropped.

    Returns
    -------
    list[str]
        The gate's findings.
    """
    str_new = (
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: check-secrets\n"
        "        name: secret scan (gitleaks)\n"
        "      - id: some-other-hook\n"
        "        name: some other hook\n"
    )

    return gate.precommit_problems(_STR_PRECOMMIT_BASE, str_new, ".pre-commit-config.yaml")


def test_precommit_conflict_resolution_drops_gate_integrity_310_shape(
    list_precommit_310_problems: list[str],
) -> None:
    """Replay #310: keeping ``check-secrets`` while dropping ``gate-integrity`` is caught.

    Parameters
    ----------
    list_precommit_310_problems : list[str]
        The gate's findings.
    """
    assert len(list_precommit_310_problems) == 1


@pytest.mark.parametrize("str_needle", ["gate-integrity", "removed"])
def test_precommit_310_finding_names_the_dropped_hook(
    list_precommit_310_problems: list[str], str_needle: str
) -> None:
    """The finding names the dropped hook and says it was removed.

    Parameters
    ----------
    list_precommit_310_problems : list[str]
        The gate's findings.
    str_needle : str
        Text the finding must contain.
    """
    assert str_needle in list_precommit_310_problems[0]


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


@pytest.fixture
def list_workflow_312_problems() -> list[str]:
    """Return the findings for #312's shape: ``docs-code-refs`` kept, ``gate-integrity`` dropped.

    Returns
    -------
    list[str]
        The gate's findings.
    """
    str_new = (
        "jobs:\n"
        "  docs-code-refs:\n"
        "    name: Docs code references\n"
        "    runs-on: ubuntu-latest\n"
        "  some-other-job:\n"
        "    name: Some other job\n"
        "    runs-on: ubuntu-latest\n"
    )

    return gate.workflow_problems(_STR_WORKFLOW_BASE, str_new, "scaffold_checks.yml")


def test_workflow_conflict_resolution_drops_gate_integrity_312_shape(
    list_workflow_312_problems: list[str],
) -> None:
    """Replay #312: keeping ``docs-code-refs`` while dropping ``gate-integrity`` is caught.

    Parameters
    ----------
    list_workflow_312_problems : list[str]
        The gate's findings.
    """
    assert len(list_workflow_312_problems) == 1


@pytest.mark.parametrize("str_needle", ["gate-integrity", "removed"])
def test_workflow_312_finding_names_the_dropped_job(
    list_workflow_312_problems: list[str], str_needle: str
) -> None:
    """The finding names the dropped job and says it was removed.

    Parameters
    ----------
    list_workflow_312_problems : list[str]
        The gate's findings.
    str_needle : str
        Text the finding must contain.
    """
    assert str_needle in list_workflow_312_problems[0]


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


def _git_in(path_repo: Path, *args: str) -> str:
    """Run ``git`` inside a throwaway repo and return its stripped stdout.

    Parameters
    ----------
    path_repo : pathlib.Path
        The repository to run in.
    *args : str
        Arguments after ``git``.

    Returns
    -------
    str
        Captured stdout, stripped.
    """
    cls_proc = subprocess.run(  # noqa: S603
        ["git", "-C", str(path_repo), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return cls_proc.stdout.strip()


def _commit_file(path_repo: Path, str_name: str) -> None:
    """Create one file and commit it.

    Parameters
    ----------
    path_repo : pathlib.Path
        The repository to commit in.
    str_name : str
        File name to create, also used as the commit message.
    """
    (path_repo / str_name).write_text(str_name, encoding="utf-8")
    _git_in(path_repo, "add", str_name)
    _git_in(path_repo, "commit", "-q", "-m", str_name)


@pytest.fixture
def path_mid_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a repo whose ``feature`` has an octopus merge of ``main`` and ``side`` in progress.

    ``main`` and ``side`` each move on after the fork, so a base resolved from the pre-merge
    HEAD (the fork point) differs from the one that excludes the incoming side.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided scratch directory.
    monkeypatch : pytest.MonkeyPatch
        Used to run the gate's git helper inside the repo.

    Returns
    -------
    pathlib.Path
        The repository, left mid-merge.
    """
    _git_in(tmp_path, "init", "-q", "--initial-branch=main")
    _git_in(tmp_path, "config", "user.email", "t@example.com")
    _git_in(tmp_path, "config", "user.name", "t")
    _commit_file(tmp_path, "seed")
    _git_in(tmp_path, "branch", "side")
    _git_in(tmp_path, "checkout", "-q", "-b", "feature")
    _commit_file(tmp_path, "own")
    _git_in(tmp_path, "checkout", "-q", "main")
    _commit_file(tmp_path, "main_moves_on")
    _git_in(tmp_path, "checkout", "-q", "side")
    _commit_file(tmp_path, "side_moves_on")
    _git_in(tmp_path, "checkout", "-q", "feature")
    _git_in(tmp_path, "merge", "-q", "--no-commit", "--no-ff", "side", "main")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_resolve_base_mid_merge_excludes_the_incoming_side(path_mid_merge: Path) -> None:
    """Mid-merge the base is main's tip, never the fork point that charges main's delta.

    Charging it made main's own gate changes (``D206``/``W191`` in ``ruff.toml``) read as the
    branch weakening them, so every "merge main into my branch" commit was rejected.
    """
    str_main_tip = _git_in(path_mid_merge, "rev-parse", "main")

    assert gate.resolve_base() == str_main_tip


def test_merge_heads_lists_every_incoming_head_of_an_octopus(path_mid_merge: Path) -> None:
    """An octopus merge reports both incoming commits, not just the first MERGE_HEAD line."""
    str_side = _git_in(path_mid_merge, "rev-parse", "side")
    str_main = _git_in(path_mid_merge, "rev-parse", "main")

    assert sorted(gate.merge_heads()) == sorted([str_side, str_main])


def test_merge_heads_is_empty_when_no_merge_is_in_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Outside a merge there is nothing to add, so the base resolves exactly as before."""
    _git_in(tmp_path, "init", "-q", "--initial-branch=main")
    monkeypatch.chdir(tmp_path)

    assert gate.merge_heads() == []


def _bare_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every CI, runner and local signal from the environment."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("JENKINS_URL", raising=False)
    monkeypatch.delenv("PRE_COMMIT", raising=False)
    monkeypatch.setattr(gate_env, "has_terminal", lambda: True)


def test_gate_env_local_pre_commit_shell_is_not_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pre-commit run with no CI marker is the one place the hatch is live."""
    _bare_shell(monkeypatch)
    monkeypatch.setenv("PRE_COMMIT", "1")

    assert gate_env.is_ci() is False


def test_gate_env_ci_false_in_a_local_shell_is_not_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """``CI=false`` is a developer's shell, not a runner."""
    _bare_shell(monkeypatch)
    monkeypatch.setenv("PRE_COMMIT", "1")
    monkeypatch.setenv("CI", "false")

    assert gate_env.is_ci() is False


def test_gate_env_empty_ci_in_a_local_shell_is_not_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """``CI=""`` is falsy, so it must not disable the local hatch."""
    _bare_shell(monkeypatch)
    monkeypatch.setenv("PRE_COMMIT", "1")
    monkeypatch.setenv("CI", "")

    assert gate_env.is_ci() is False


def test_gate_env_github_actions_is_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """GitHub Actions wins even when a local signal is also present."""
    _bare_shell(monkeypatch)
    monkeypatch.setenv("PRE_COMMIT", "1")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    assert gate_env.is_ci() is True


def test_gate_env_unknown_runner_is_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jenkins sets neither ``CI`` nor ``GITHUB_ACTIONS``; no local signal means CI."""
    _bare_shell(monkeypatch)
    monkeypatch.setenv("JENKINS_URL", "https://jenkins.example")

    assert gate_env.is_ci() is True


def test_gate_env_bare_environment_is_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no evidence either way the verdict fails closed."""
    _bare_shell(monkeypatch)

    assert gate_env.is_ci() is True


def test_gate_env_headless_runner_with_pre_commit_is_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jenkins invoking ``pre-commit`` inherits ``PRE_COMMIT`` but has no terminal."""
    _bare_shell(monkeypatch)
    monkeypatch.setenv("PRE_COMMIT", "1")
    monkeypatch.setenv("JENKINS_URL", "https://jenkins.example")
    monkeypatch.setattr(gate_env, "has_terminal", lambda: False)

    assert gate_env.is_ci() is True


_STR_RENAME_OLD = "def test_rejects_negative_amounts() -> None:\n    assert f() == 1\n"
_STR_RENAME_OTHER = (
    "def test_rejects_negative_dates() -> None:\n"
    "    list_rows = [load(str_p) for str_p in PATHS]\n"
    "    assert sorted(list_rows) == list_rows\n"
)


def _funcs(*tuple_names: str, str_body: str = "assert f() == 1") -> dict:
    """Parse one ``test_*`` function per name, all sharing ``str_body``.

    Parameters
    ----------
    *tuple_names : str
        Function names.
    str_body : str
        The single-statement body each function gets.

    Returns
    -------
    dict
        ``{name: ast.FunctionDef}``.
    """
    str_src = "".join(f"def {str_n}() -> None:\n    {str_body}\n" for str_n in tuple_names)
    return gate.test_functions(str_src)


def test_pairing_is_independent_of_input_order() -> None:
    """Two renames that each clear the threshold against both candidates pair the same way."""
    dict_expected = {"test_parse_v1": "test_parse_w1", "test_parse_v2": "test_parse_w2"}
    tuple_fwd, tuple_rev = ("test_parse_v1", "test_parse_v2"), ("test_parse_v2", "test_parse_v1")
    dict_added = _funcs("test_parse_w1", "test_parse_w2")
    assert gate_rename.rename_pairs(_funcs(*tuple_fwd), dict_added) == dict_expected
    assert gate_rename.rename_pairs(_funcs(*tuple_rev), dict_added) == dict_expected


def test_a_better_later_match_is_not_stolen_by_an_earlier_name() -> None:
    """NEGATIVE CONTROL: both old names clear 0.8; the weaker one listed first must lose."""
    dict_pairs = gate_rename.rename_pairs(
        _funcs("test_parse_v10", "test_parse_v1"), _funcs("test_parse_v11")
    )
    assert dict_pairs == {"test_parse_v1": "test_parse_v11"}


def test_a_dissimilar_name_is_not_paired() -> None:
    """NEGATIVE CONTROL: below the name threshold nothing pairs, so the deletion stays visible."""
    assert (
        gate_rename.rename_pairs(_funcs("test_rejects_negative_amounts"), _funcs("test_x")) == {}
    )


def test_a_similar_name_with_an_unrelated_body_is_not_paired() -> None:
    """NEGATIVE CONTROL: sibling names alone never absorb a deletion; the bodies must agree too."""
    dict_old = _funcs("test_parse_v1", str_body="assert f() == 1")
    dict_new = _funcs("test_parse_v2", str_body="assert sorted(load(path)) == [3, 4, 5, 6, 7]")
    assert gate_rename.rename_pairs(dict_old, dict_new) == {}


def test_integrity_gate_reports_a_deletion_beside_a_similarly_named_unrelated_test() -> None:
    """Delete one test, add a near-named test with a different body: still a deletion."""
    list_problems = gate.deleted_or_gutted_tests(_STR_RENAME_OLD, _STR_RENAME_OTHER, "x")
    assert list_problems == [
        "x: test 'test_rejects_negative_amounts' deleted"
        " (possible rename to 'test_rejects_negative_dates', bodies differ)"
    ]


def test_weakening_gate_reports_a_deletion_beside_a_similarly_named_unrelated_test() -> None:
    """The weakening gate agrees with the integrity gate on the same diff."""
    list_problems = weakening._file_findings("x", _STR_RENAME_OLD, _STR_RENAME_OTHER, False)
    assert list_problems == [
        "x: test 'test_rejects_negative_amounts' deleted"
        " (possible rename to 'test_rejects_negative_dates', bodies differ)"
    ]


def test_weakening_finding_names_the_renamed_test() -> None:
    """A finding on a renamed test uses the name that exists in the change."""
    str_old = "def test_rejects_negative_amounts() -> None:\n    assert f() == 1\n    assert g()\n"
    str_new = "def test_rejects_negative_amount() -> None:\n    assert f() == 1\n"
    list_problems = weakening._file_findings("x", str_old, str_new, False)
    assert list_problems == [
        "x: test_rejects_negative_amount() lost 1 assertion(s) (had 2, now 1)"
    ]


def test_a_sibling_differing_only_in_a_literal_is_not_paired() -> None:
    """NEGATIVE CONTROL: v1 replaced by v2 with other inputs is a deletion, not a rename."""
    dict_old = _funcs("test_parse_v1", str_body="assert parse('a') == 1")
    dict_new = _funcs("test_parse_v2", str_body="assert parse('b') == 2")
    assert gate_rename.rename_pairs(dict_old, dict_new) == {}


def test_a_long_renamed_body_still_pairs() -> None:
    """A ten-statement body renamed unchanged pairs, so #1073 holds beyond tiny tests."""
    str_body = "\n    ".join(f"assert parse({int_i}) == {int_i}" for int_i in range(10))
    dict_old = _funcs("test_has_six_pages", str_body=str_body)
    dict_new = _funcs("test_has_seven_pages", str_body=str_body)
    assert gate_rename.rename_pairs(dict_old, dict_new) == {
        "test_has_six_pages": "test_has_seven_pages"
    }


def test_a_rename_that_also_edits_a_literal_is_a_hinted_deletion() -> None:
    """The #1073 shape with a changed literal stays a finding but names the likely target."""
    str_old = "def test_has_six_pages() -> None:\n    assert count() == 6\n"
    str_new = "def test_has_seven_pages() -> None:\n    assert count() == 7\n"
    list_problems = gate.deleted_or_gutted_tests(str_old, str_new, "x")
    assert list_problems == [
        "x: test 'test_has_six_pages' deleted"
        " (possible rename to 'test_has_seven_pages', bodies differ)"
    ]


def test_a_docstring_only_test_is_never_paired() -> None:
    """NEGATIVE CONTROL: two bodies with no statements are not evidence of a rename."""
    str_src = 'def test_a_{s}() -> None:\n    """Doc."""\n'
    dict_old = gate.test_functions(str_src.format(s="v1"))
    dict_new = gate.test_functions(str_src.format(s="v2"))
    assert gate_rename.rename_pairs(dict_old, dict_new) == {}


def test_a_docstring_does_not_count_as_a_statement_when_pairing() -> None:
    """A renamed test that also gained a docstring still pairs on its real statements."""
    dict_old = gate.test_functions("def test_has_six_pages() -> None:\n    assert count() == 6\n")
    dict_new = gate.test_functions(
        'def test_has_seven_pages() -> None:\n    """Doc."""\n    assert count() == 6\n'
    )
    assert gate_rename.rename_pairs(dict_old, dict_new) == {
        "test_has_six_pages": "test_has_seven_pages"
    }


def test_a_renamed_test_newly_marked_skip_is_detected() -> None:
    """NEGATIVE CONTROL: renaming a test and skipping it in one change is still a finding."""
    str_old = "def test_has_six_pages() -> None:\n    assert count() == 6\n"
    str_new = "@pytest.mark.skip\ndef test_has_seven_pages() -> None:\n    assert count() == 6\n"
    assert gate.newly_skipped_tests(str_old, str_new, "x") == [
        "x: test 'test_has_seven_pages' newly decorated @pytest.mark.skip"
    ]


def test_a_renamed_test_keeping_its_xfail_is_not_flagged() -> None:
    """A marker already present on the old test is not new after a rename."""
    str_old = "@pytest.mark.xfail\ndef test_has_six_pages() -> None:\n    assert count() == 6\n"
    str_new = "@pytest.mark.xfail\ndef test_has_seven_pages() -> None:\n    assert count() == 6\n"
    assert gate.newly_skipped_tests(str_old, str_new, "x") == []
