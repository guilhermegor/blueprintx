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
    assert (
        gate.report(
            ["ruff.toml: rule 'S608' added to [lint] ignore"], str_base="base", int_changed_count=1
        )
        == 1
    )


def test_report_passes_the_same_weakening_with_gate_change_ok_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both directions, part 2: the SAME finding, justified only via GATE_CHANGE_OK, must PASS."""
    _local_shell(monkeypatch)
    monkeypatch.setenv("GATE_CHANGE_OK", "reviewed with the team")
    monkeypatch.setattr(gate, "_git", lambda _args: "")
    monkeypatch.setattr(gate, "pr_body_text", lambda: "")
    assert (
        gate.report(
            ["ruff.toml: rule 'S608' added to [lint] ignore"], str_base="base", int_changed_count=1
        )
        == 0
    )


def test_report_rejects_a_whitespace_only_gate_change_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank-looking reason must still FAIL — matching the trailer/PR-body rule exactly."""
    _local_shell(monkeypatch)
    monkeypatch.setenv("GATE_CHANGE_OK", "   ")
    monkeypatch.setattr(gate, "_git", lambda _args: "")
    monkeypatch.setattr(gate, "pr_body_text", lambda: "")
    assert (
        gate.report(
            ["ruff.toml: rule 'S608' added to [lint] ignore"], str_base="base", int_changed_count=1
        )
        == 1
    )


@pytest.mark.parametrize("str_marker", ["CI", "GITHUB_ACTIONS"])
def test_env_reason_is_ignored_under_ci(
    monkeypatch: pytest.MonkeyPatch, *, str_marker: str
) -> None:
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
    assert (
        gate.report(
            ["ruff.toml: rule 'S608' added to [lint] ignore"], str_base="base", int_changed_count=1
        )
        == 1
    )


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

    return gate.precommit_problems(
        _STR_PRECOMMIT_BASE, str_new=str_new, str_shown=".pre-commit-config.yaml"
    )


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
    list_precommit_310_problems: list[str], *, str_needle: str
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

    assert (
        gate.precommit_problems(
            _STR_PRECOMMIT_BASE, str_new=str_new, str_shown=".pre-commit-config.yaml"
        )
        == []
    )


def test_precommit_unrelated_addition_alone_is_clean() -> None:
    """Adding a hook without touching any existing one reports nothing (no false positive)."""
    str_new = _STR_PRECOMMIT_BASE + "      - id: brand-new-hook\n        name: brand new\n"

    assert (
        gate.precommit_problems(
            _STR_PRECOMMIT_BASE, str_new=str_new, str_shown=".pre-commit-config.yaml"
        )
        == []
    )


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

    return gate.workflow_problems(
        _STR_WORKFLOW_BASE, str_new=str_new, str_shown="scaffold_checks.yml"
    )


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
    list_workflow_312_problems: list[str], *, str_needle: str
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

    assert (
        gate.workflow_problems(
            _STR_WORKFLOW_BASE, str_new=str_new, str_shown="scaffold_checks.yml"
        )
        == []
    )


def test_workflow_unrelated_addition_alone_is_clean() -> None:
    """Adding a job without touching any existing one reports nothing (no false positive)."""
    str_new = (
        _STR_WORKFLOW_BASE + "  brand-new-job:\n    name: Brand new\n    runs-on: ubuntu-latest\n"
    )

    assert (
        gate.workflow_problems(
            _STR_WORKFLOW_BASE, str_new=str_new, str_shown="scaffold_checks.yml"
        )
        == []
    )


def test_report_unjustified_gate_drop_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dropped id with no ``gate-change-ok:`` trailer/PR-body reason fails the run."""
    monkeypatch.setattr(gate, "justification_reason", lambda str_base: "")
    str_finding = "scaffold_checks.yml: workflow job 'gate-integrity' removed"

    int_code = gate.report([str_finding], str_base="base", int_changed_count=1)

    assert int_code == 1


def test_report_justified_gate_drop_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The SAME finding passes once a non-empty ``gate-change-ok:`` reason resolves.

    This is the escape hatch a legitimate rename (rather than a silent drop) relies on — the
    gate must stay payable for real work, not merely loud on the defect it was built for.
    """
    monkeypatch.setattr(gate, "justification_reason", lambda str_base: "renamed, see PR body")
    str_finding = "scaffold_checks.yml: workflow job 'gate-integrity' removed"

    int_code = gate.report([str_finding], str_base="base", int_changed_count=1)

    assert int_code == 0


def test_report_no_findings_passes() -> None:
    """An empty findings list passes without consulting the justification hatch at all."""
    assert gate.report([], str_base="base", int_changed_count=3) == 0


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
        encoding="utf-8",
        check=True,
    )
    return cls_proc.stdout.strip()


def _commit_file(path_repo: Path, *, str_name: str) -> None:
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
def path_mid_merge(tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch) -> Path:
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
    _commit_file(tmp_path, str_name="seed")
    _git_in(tmp_path, "branch", "side")
    _git_in(tmp_path, "checkout", "-q", "-b", "feature")
    _commit_file(tmp_path, str_name="own")
    _git_in(tmp_path, "checkout", "-q", "main")
    _commit_file(tmp_path, str_name="main_moves_on")
    _git_in(tmp_path, "checkout", "-q", "side")
    _commit_file(tmp_path, str_name="side_moves_on")
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
    tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
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


@pytest.mark.parametrize(
    "tuple_old",
    [("test_parse_v1", "test_parse_v2"), ("test_parse_v2", "test_parse_v1")],
    ids=["forward", "reversed"],
)
def test_pairing_is_independent_of_input_order(tuple_old: tuple[str, str]) -> None:
    """Two renames that each clear the threshold against both candidates pair the same way."""
    dict_expected = {"test_parse_v1": "test_parse_w1", "test_parse_v2": "test_parse_w2"}
    dict_added = _funcs("test_parse_w1", "test_parse_w2")
    assert gate_rename.rename_pairs(_funcs(*tuple_old), dict_added=dict_added) == dict_expected


def test_a_better_later_match_is_not_stolen_by_an_earlier_name() -> None:
    """NEGATIVE CONTROL: both old names clear 0.8; the weaker one listed first must lose."""
    dict_pairs = gate_rename.rename_pairs(
        _funcs("test_parse_v10", "test_parse_v1"), dict_added=_funcs("test_parse_v11")
    )
    assert dict_pairs == {"test_parse_v1": "test_parse_v11"}


def test_a_dissimilar_name_is_not_paired() -> None:
    """NEGATIVE CONTROL: below the name threshold nothing pairs, so the deletion stays visible."""
    assert (
        gate_rename.rename_pairs(
            _funcs("test_rejects_negative_amounts"), dict_added=_funcs("test_x")
        )
        == {}
    )


def test_a_similar_name_with_an_unrelated_body_is_not_paired() -> None:
    """NEGATIVE CONTROL: sibling names alone never absorb a deletion; the bodies must agree too."""
    dict_old = _funcs("test_parse_v1", str_body="assert f() == 1")
    dict_new = _funcs("test_parse_v2", str_body="assert sorted(load(path)) == [3, 4, 5, 6, 7]")
    assert gate_rename.rename_pairs(dict_old, dict_added=dict_new) == {}


def test_integrity_gate_reports_a_deletion_beside_a_similarly_named_unrelated_test() -> None:
    """Delete one test, add a near-named test with a different body: still a deletion."""
    list_problems = gate.deleted_or_gutted_tests(
        _STR_RENAME_OLD, str_new=_STR_RENAME_OTHER, str_shown="x"
    )
    assert list_problems == [
        "x: test 'test_rejects_negative_amounts' deleted"
        " (possible rename to 'test_rejects_negative_dates', bodies differ)"
    ]


def test_weakening_gate_reports_a_deletion_beside_a_similarly_named_unrelated_test() -> None:
    """The weakening gate agrees with the integrity gate on the same diff."""
    list_problems = weakening._file_findings(
        "x", str_old_text=_STR_RENAME_OLD, str_new_text=_STR_RENAME_OTHER, bool_prod_changed=False
    )
    assert list_problems == [
        "x: test 'test_rejects_negative_amounts' deleted"
        " (possible rename to 'test_rejects_negative_dates', bodies differ)"
    ]


def test_weakening_finding_names_the_renamed_test() -> None:
    """A finding on a renamed test uses the name that exists in the change."""
    str_old = "def test_rejects_negative_amounts() -> None:\n    assert f() == 1\n    assert g()\n"
    str_new = "def test_rejects_negative_amount() -> None:\n    assert f() == 1\n"
    list_problems = weakening._file_findings(
        "x", str_old_text=str_old, str_new_text=str_new, bool_prod_changed=False
    )
    assert list_problems == [
        "x: test_rejects_negative_amount() lost 1 assertion(s) (had 2, now 1)"
    ]


def test_a_sibling_differing_only_in_a_literal_is_not_paired() -> None:
    """NEGATIVE CONTROL: v1 replaced by v2 with other inputs is a deletion, not a rename."""
    dict_old = _funcs("test_parse_v1", str_body="assert parse('a') == 1")
    dict_new = _funcs("test_parse_v2", str_body="assert parse('b') == 2")
    assert gate_rename.rename_pairs(dict_old, dict_added=dict_new) == {}


def test_a_long_renamed_body_still_pairs() -> None:
    """A ten-statement body renamed unchanged pairs, so #1073 holds beyond tiny tests."""
    str_body = "\n    ".join(f"assert parse({int_i}) == {int_i}" for int_i in range(10))
    dict_old = _funcs("test_has_six_pages", str_body=str_body)
    dict_new = _funcs("test_has_seven_pages", str_body=str_body)
    assert gate_rename.rename_pairs(dict_old, dict_added=dict_new) == {
        "test_has_six_pages": "test_has_seven_pages"
    }


def test_a_rename_that_also_edits_a_literal_is_a_hinted_deletion() -> None:
    """The #1073 shape with a changed literal stays a finding but names the likely target."""
    str_old = "def test_has_six_pages() -> None:\n    assert count() == 6\n"
    str_new = "def test_has_seven_pages() -> None:\n    assert count() == 7\n"
    list_problems = gate.deleted_or_gutted_tests(str_old, str_new=str_new, str_shown="x")
    assert list_problems == [
        "x: test 'test_has_six_pages' deleted"
        " (possible rename to 'test_has_seven_pages', bodies differ)"
    ]


def test_a_docstring_only_test_is_never_paired() -> None:
    """NEGATIVE CONTROL: two bodies with no statements are not evidence of a rename."""
    str_src = 'def test_a_{s}() -> None:\n    """Doc."""\n'
    dict_old = gate.test_functions(str_src.format(s="v1"))
    dict_new = gate.test_functions(str_src.format(s="v2"))
    assert gate_rename.rename_pairs(dict_old, dict_added=dict_new) == {}


def test_a_docstring_does_not_count_as_a_statement_when_pairing() -> None:
    """A renamed test that also gained a docstring still pairs on its real statements."""
    dict_old = gate.test_functions("def test_has_six_pages() -> None:\n    assert count() == 6\n")
    dict_new = gate.test_functions(
        'def test_has_seven_pages() -> None:\n    """Doc."""\n    assert count() == 6\n'
    )
    assert gate_rename.rename_pairs(dict_old, dict_added=dict_new) == {
        "test_has_six_pages": "test_has_seven_pages"
    }


def test_a_renamed_test_newly_marked_skip_is_detected() -> None:
    """NEGATIVE CONTROL: renaming a test and skipping it in one change is still a finding."""
    str_old = "def test_has_six_pages() -> None:\n    assert count() == 6\n"
    str_new = "@pytest.mark.skip\ndef test_has_seven_pages() -> None:\n    assert count() == 6\n"
    assert gate.newly_skipped_tests(str_old, str_new=str_new, str_shown="x") == [
        "x: test 'test_has_seven_pages' newly decorated @pytest.mark.skip"
    ]


def test_a_renamed_test_keeping_its_xfail_is_not_flagged() -> None:
    """A marker already present on the old test is not new after a rename."""
    str_old = "@pytest.mark.xfail\ndef test_has_six_pages() -> None:\n    assert count() == 6\n"
    str_new = "@pytest.mark.xfail\ndef test_has_seven_pages() -> None:\n    assert count() == 6\n"
    assert gate.newly_skipped_tests(str_old, str_new=str_new, str_shown="x") == []


def test_gate_env_note_names_a_person_when_no_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a readable ``/dev/tty`` the hint says a person must run the commit."""
    monkeypatch.setattr(gate_env, "has_terminal", lambda: False)

    assert "a person must run that commit" in gate_env.no_terminal_note()


def test_gate_env_note_is_empty_with_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """With a terminal the hint is empty, so the message keeps its current text."""
    monkeypatch.setattr(gate_env, "has_terminal", lambda: True)

    assert gate_env.no_terminal_note() == ""


def test_report_says_interactive_terminal_only_when_no_terminal(
    monkeypatch: pytest.MonkeyPatch, *, capsys: pytest.CaptureFixture[str]
) -> None:
    """The unjustified failure says the override is honored only in an interactive terminal."""
    _local_shell(monkeypatch)
    monkeypatch.setattr(gate_env, "has_terminal", lambda: False)
    monkeypatch.delenv("GATE_CHANGE_OK", raising=False)
    monkeypatch.setattr(gate, "_git", lambda _args: "")
    monkeypatch.setattr(gate, "pr_body_text", lambda: "")
    gate.report(["some finding"], str_base="base", int_changed_count=1)

    assert "honored only in an interactive terminal" in capsys.readouterr().out


def test_report_omits_the_terminal_hint_with_a_terminal(
    monkeypatch: pytest.MonkeyPatch, *, capsys: pytest.CaptureFixture[str]
) -> None:
    """With a terminal the unjustified failure keeps its current text."""
    _local_shell(monkeypatch)
    monkeypatch.delenv("GATE_CHANGE_OK", raising=False)
    monkeypatch.setattr(gate, "_git", lambda _args: "")
    monkeypatch.setattr(gate, "pr_body_text", lambda: "")
    gate.report(["some finding"], str_base="base", int_changed_count=1)

    assert "interactive terminal" not in capsys.readouterr().out


_STR_MOVED_JOB = (
    "  gate-integrity:\n"
    "    name: Gate integrity\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - run: python3 bin/check_gate_integrity.py\n"
)
_STR_KEPT_JOB = "  other:\n    name: Other\n    steps:\n      - run: echo hi\n"
_STR_SOURCE = "templates/python-common/.github/workflows/scaffold_checks.yml"
_STR_SIBLING = "templates/python-common/.github/workflows/gate_integrity.yml"
_STR_ROOT_SIBLING = ".github/workflows/gate_integrity.yml"


def _collect_workflows(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dict_old: dict[str, str],
    dict_new: dict[str, str],
    list_changed: list[tuple[str, str]],
) -> list[str]:
    """Run ``collect_problems`` over in-memory workflow blobs.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Fixture used to stub ``gate.show``.
    dict_old : dict[str, str]
        Path to content at the merge-base.
    dict_new : dict[str, str]
        Path to content in the index.
    list_changed : list[tuple[str, str]]
        ``(status_letter, path)`` rows.

    Returns
    -------
    list[str]
        The gate's findings.
    """
    dict_blobs = {("base", str_k): str_v for str_k, str_v in dict_old.items()}
    dict_blobs.update({(gate.STR_INDEX_REF, str_k): str_v for str_k, str_v in dict_new.items()})
    monkeypatch.setattr(
        gate, "show", lambda str_ref, *, str_path: dict_blobs.get((str_ref, str_path))
    )
    return gate.collect_problems(list_changed, str_base="base")


def _move_findings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    str_target: str,
    str_job_new: str,
    str_target_old: str = "",
    str_job_old: str = _STR_MOVED_JOB,
) -> list[str]:
    """Move a job out of the template's ``scaffold_checks.yml`` into ``str_target``.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Fixture used to stub ``gate.show``.
    str_target : str
        Path of the workflow file that receives the job.
    str_job_new : str
        The job block as it appears in the target.
    str_target_old : str
        The target's ``jobs:`` body at the merge-base; empty when the file is new.
    str_job_old : str
        The job block as it appeared in the source.

    Returns
    -------
    list[str]
        The gate's findings.
    """
    return _collect_workflows(
        monkeypatch,
        dict_old={
            _STR_SOURCE: f"jobs:\n{str_job_old}{_STR_KEPT_JOB}",
            str_target: f"jobs:\n{str_target_old}",
        },
        dict_new={
            _STR_SOURCE: f"jobs:\n{_STR_KEPT_JOB}",
            str_target: f"jobs:\n{str_job_new}",
        },
        list_changed=[("M", _STR_SOURCE), ("M", str_target)],
    )


def test_workflow_job_moved_within_the_tree_is_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same id, name and steps in another workflow of the same tree is a move."""
    assert _move_findings(monkeypatch, str_target=_STR_SIBLING, str_job_new=_STR_MOVED_JOB) == []


def test_workflow_job_moved_within_the_root_tree_is_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """The root tree is judged like a template tree."""
    dict_old = {".github/workflows/a.yml": f"jobs:\n{_STR_MOVED_JOB}{_STR_KEPT_JOB}"}
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old=dict_old,
        dict_new={
            ".github/workflows/a.yml": f"jobs:\n{_STR_KEPT_JOB}",
            _STR_ROOT_SIBLING: f"jobs:\n{_STR_MOVED_JOB}",
        },
        list_changed=[("M", ".github/workflows/a.yml"), ("A", _STR_ROOT_SIBLING)],
    )

    assert list_findings == []


def test_workflow_job_moved_with_a_renamed_name_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A changed ``name:`` breaks the required status-check context, so it is a removal."""
    str_job = _STR_MOVED_JOB.replace("Gate integrity", "Gate integrity check")

    assert len(_move_findings(monkeypatch, str_target=_STR_SIBLING, str_job_new=str_job)) == 1


def test_workflow_job_moved_with_changed_steps_is_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Changed steps would hide a weakened command behind a move."""
    str_job = _STR_MOVED_JOB.replace("check_gate_integrity.py", "check_gate_integrity.py || true")

    assert len(_move_findings(monkeypatch, str_target=_STR_SIBLING, str_job_new=str_job)) == 1


@pytest.mark.parametrize(
    "str_extra",
    [
        "    if: false\n",
        "    continue-on-error: true\n",
        "    env:\n      LINT_REQUIRED: '0'\n",
        "    timeout-minutes: 1\n",
        "    needs: [noop]\n",
        '    "continue-on-error": true\n',
        "    if : false\n",
    ],
)
def test_workflow_job_moved_with_a_softening_key_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_extra: str
) -> None:
    """A key that skips or softens the job is not a faithful move."""
    str_job = _STR_MOVED_JOB.replace("ubuntu-latest\n", f"ubuntu-latest\n{str_extra}")

    assert len(_move_findings(monkeypatch, str_target=_STR_SIBLING, str_job_new=str_job)) == 1


@pytest.mark.parametrize(
    "str_extra",
    [
        "    needs: [build]\n",
        "    env: &shared\n      A: '1'\n",
        "    env: *shared\n",
        "    env:\n      <<: *shared\n",
        "    steps:\n      - *gate_step\n",
        '    "needs": [build]\n',
        "    'needs': [build]\n",
        "    steps: [*gate_step]\n",
        "    env: !!map &shared\n      A: '1'\n",
    ],
)
def test_workflow_job_moved_with_outside_dependency_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_extra: str
) -> None:
    """``needs:`` and YAML anchors point outside the block, so an identical text is no proof."""
    str_job = _STR_MOVED_JOB.replace("ubuntu-latest\n", f"ubuntu-latest\n{str_extra}")
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"jobs:\n{str_job}{_STR_KEPT_JOB}"},
        dict_new={_STR_SOURCE: f"jobs:\n{_STR_KEPT_JOB}", _STR_SIBLING: f"jobs:\n{str_job}"},
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert len(list_findings) == 1


@pytest.mark.parametrize(
    "str_id_line",
    ["  gate: {name: G, steps: [{run: real}]}\n", '  "gate": {name: G, steps: [{run: real}]}\n'],
)
def test_workflow_flow_style_job_moved_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_id_line: str
) -> None:
    """A value on the id line, quoted id or not, makes the job unmovable even when unchanged.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Used to stub the base and working-tree reads.
    str_id_line : str
        The flow-style job line, identical in the source and the target.
    """
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"jobs:\n{str_id_line}"},
        dict_new={_STR_SOURCE: "jobs:\n", _STR_SIBLING: f"jobs:\n{str_id_line}"},
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert len(list_findings) == 1


def test_workflow_job_moved_under_the_same_settings_is_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only ``name:`` and comments may differ in the target's top-level settings."""
    str_on = "on:\n  pull_request:\n"
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"name: A\n{str_on}jobs:\n{_STR_MOVED_JOB}{_STR_KEPT_JOB}"},
        dict_new={
            _STR_SOURCE: f"name: A\n{str_on}jobs:\n{_STR_KEPT_JOB}",
            _STR_SIBLING: f"# moved\nname: B\n{str_on}jobs:\n{_STR_MOVED_JOB}",
        },
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert list_findings == []


@pytest.mark.parametrize(
    "str_header", ["on: workflow_dispatch\n", "permissions: {}\n", "env:\n  STRICT: '0'\n"]
)
def test_workflow_job_moved_under_other_settings_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_header: str
) -> None:
    """A target whose ``on:`` or other top-level settings differ may never run the job."""
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"jobs:\n{_STR_MOVED_JOB}{_STR_KEPT_JOB}"},
        dict_new={
            _STR_SOURCE: f"jobs:\n{_STR_KEPT_JOB}",
            _STR_SIBLING: f"name: Other\n{str_header}jobs:\n{_STR_MOVED_JOB}",
        },
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert len(list_findings) == 1


@pytest.mark.parametrize(
    "str_runner",
    [
        "windows-latest",
        "self-hosted",
        "[self-hosted, gpu]",
        "\n      - self-hosted",
        "ubuntu-latest-64core",
        "ubuntu-nonexistent",
        "ubuntu-latest-arm",
        "ubuntu-20.04",
        "ubuntu-99.99",
        "ubuntu-latest#x",
    ],
)
def test_workflow_job_moved_to_a_non_ubuntu_runner_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_runner: str
) -> None:
    """Only a one-line ``ubuntu-*`` runner may change: another can change the shell or hang."""
    str_job = _STR_MOVED_JOB.replace("ubuntu-latest", str_runner)

    assert len(_move_findings(monkeypatch, str_target=_STR_SIBLING, str_job_new=str_job)) == 1


def test_workflow_job_moved_between_reusable_workflows_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Callers still ``uses:`` the source file, so a job moved out of it stops running."""
    str_on = "on:\n  workflow_call:\n"
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"{str_on}jobs:\n{_STR_MOVED_JOB}{_STR_KEPT_JOB}"},
        dict_new={
            _STR_SOURCE: f"{str_on}jobs:\n{_STR_KEPT_JOB}",
            _STR_SIBLING: f"{str_on}jobs:\n{_STR_MOVED_JOB}",
        },
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert len(list_findings) == 1


def test_workflow_job_removed_after_a_column_zero_comment_is_reported() -> None:
    """A comment at column 0 inside ``jobs:`` must not end the parse and hide later jobs."""
    str_old = f"jobs:\n{_STR_KEPT_JOB}# section\n{_STR_MOVED_JOB}"

    assert gate.workflow_problems(str_old, str_new=f"jobs:\n{_STR_KEPT_JOB}", str_shown="w") == [
        "w: workflow job 'gate-integrity' removed"
    ]


def test_workflow_job_moved_while_its_id_is_still_a_word_in_the_source_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reference search is whole-word over the source file and errs toward reporting."""
    str_kept = _STR_KEPT_JOB.replace("echo hi", "make gate-integrity")
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"jobs:\n{_STR_MOVED_JOB}{str_kept}"},
        dict_new={_STR_SOURCE: f"jobs:\n{str_kept}", _STR_SIBLING: f"jobs:\n{_STR_MOVED_JOB}"},
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert len(list_findings) == 1


def test_workflow_job_moved_without_runs_on_is_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hosted runner may change, never vanish."""
    str_job = _STR_MOVED_JOB.replace("    runs-on: ubuntu-latest\n", "")

    assert len(_move_findings(monkeypatch, str_target=_STR_SIBLING, str_job_new=str_job)) == 1


def test_workflow_job_moved_away_from_its_dependents_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A job left behind that still ``needs:`` the moved one breaks the source workflow."""
    str_dependent = "  report:\n    needs: [gate-integrity]\n    runs-on: ubuntu-latest\n"
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"jobs:\n{_STR_MOVED_JOB}{str_dependent}"},
        dict_new={
            _STR_SOURCE: f"jobs:\n{str_dependent}",
            _STR_SIBLING: f"jobs:\n{_STR_MOVED_JOB}",
        },
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert len(list_findings) == 1


def test_workflow_job_moved_without_a_folded_blank_line_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blank line inside a folded scalar changes what runs, so it is compared."""
    str_job = f"{_STR_MOVED_JOB}      - run: >\n          check\n\n          --strict\n"
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"jobs:\n{str_job}{_STR_KEPT_JOB}"},
        dict_new={
            _STR_SOURCE: f"jobs:\n{_STR_KEPT_JOB}",
            _STR_SIBLING: f"jobs:\n{str_job.replace(chr(10) * 2, chr(10))}",
        },
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert len(list_findings) == 1


def test_workflow_quoted_job_id_removal_is_reported() -> None:
    """A quoted id is a job of its own, so dropping it is a removal."""
    str_old = f'jobs:\n{_STR_KEPT_JOB}  "gate":\n    runs-on: ubuntu-latest\n'

    assert (
        len(gate.workflow_problems(str_old, str_new=f"jobs:\n{_STR_KEPT_JOB}", str_shown="w")) == 1
    )


def test_workflow_job_moved_with_a_different_runner_is_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``runs-on`` is the one key a move may change."""
    str_job = _STR_MOVED_JOB.replace("ubuntu-latest", "ubuntu-24.04")

    assert _move_findings(monkeypatch, str_target=_STR_SIBLING, str_job_new=str_job) == []


def test_workflow_job_moved_to_another_architecture_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An x86_64 job moved onto an arm64 image is compared, not excused as a runner swap."""
    str_job = _STR_MOVED_JOB.replace("ubuntu-latest", "ubuntu-24.04-arm")

    assert len(_move_findings(monkeypatch, str_target=_STR_SIBLING, str_job_new=str_job)) == 1


def test_changed_paths_reports_a_rename_as_a_delete_and_an_add(
    tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A staged ``git mv`` must surface its old path, or its removed jobs go unreported.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided scratch directory.
    monkeypatch : pytest.MonkeyPatch
        Used to run the gate's git helper inside the repo.
    """
    _git_in(tmp_path, "init", "-q", "--initial-branch=main")
    _git_in(tmp_path, "config", "user.email", "t@example.com")
    _git_in(tmp_path, "config", "user.name", "t")
    _commit_file(tmp_path, str_name="checks.yml")
    str_base = _git_in(tmp_path, "rev-parse", "HEAD")
    _git_in(tmp_path, "mv", "checks.yml", "renamed.yml")
    monkeypatch.chdir(tmp_path)

    assert sorted(gate.changed_paths(str_base)) == [("A", "renamed.yml"), ("D", "checks.yml")]


def test_workflow_job_moved_with_unindented_changed_steps_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The non-indented sequence style must not collapse the steps out of the comparison."""
    str_old = "  gate-integrity:\n    name: G\n    steps:\n    - run: a\n"
    str_new = "  gate-integrity:\n    name: G\n    steps:\n    - run: b\n"
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"jobs:\n{str_old}{_STR_KEPT_JOB}"},
        dict_new={_STR_SOURCE: f"jobs:\n{_STR_KEPT_JOB}", _STR_SIBLING: f"jobs:\n{str_new}"},
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert len(list_findings) == 1


def test_workflow_job_dropped_everywhere_is_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    """An id absent from every workflow of the tree is still a removal."""
    list_findings = _move_findings(monkeypatch, str_target=_STR_SIBLING, str_job_new=_STR_KEPT_JOB)

    assert len(list_findings) == 1


def test_workflow_job_moved_from_template_to_root_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each tree is judged on its own: a template job cannot move into the repo's own CI."""
    list_findings = _move_findings(
        monkeypatch, str_target=_STR_ROOT_SIBLING, str_job_new=_STR_MOVED_JOB
    )

    assert len(list_findings) == 1


def test_workflow_job_moved_into_a_subdirectory_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GitHub runs no workflow below ``.github/workflows/``, so that is not a move."""
    str_target = "templates/python-common/.github/workflows/archive/gate_integrity.yml"

    assert len(_move_findings(monkeypatch, str_target=str_target, str_job_new=_STR_MOVED_JOB)) == 1


def test_workflow_job_matching_a_preexisting_target_job_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The target's own older job of that id is not a destination: only a new id is."""
    str_old_target = _STR_MOVED_JOB.replace("Gate integrity", "Other meaning")

    list_findings = _move_findings(
        monkeypatch,
        str_target=_STR_SIBLING,
        str_job_new=_STR_MOVED_JOB,
        str_target_old=str_old_target,
    )

    assert len(list_findings) == 1


def test_workflow_job_removal_names_the_job(monkeypatch: pytest.MonkeyPatch) -> None:
    """The finding names the removed job and its source file."""
    list_findings = _move_findings(monkeypatch, str_target=_STR_SIBLING, str_job_new=_STR_KEPT_JOB)

    assert list_findings == [f"{_STR_SOURCE}: workflow job 'gate-integrity' removed"]


def test_workflow_one_new_job_covers_one_removal_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two removed copies of a job cannot both be excused by one new copy."""
    str_other = "templates/python-common/.github/workflows/other.yml"
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={
            _STR_SOURCE: f"jobs:\n{_STR_MOVED_JOB}{_STR_KEPT_JOB}",
            str_other: f"jobs:\n{_STR_MOVED_JOB}",
        },
        dict_new={
            _STR_SOURCE: f"jobs:\n{_STR_KEPT_JOB}",
            str_other: "jobs:\n  keep:\n    name: k\n",
            _STR_SIBLING: f"jobs:\n{_STR_MOVED_JOB}",
        },
        list_changed=[("M", _STR_SOURCE), ("M", str_other), ("A", _STR_SIBLING)],
    )

    assert len(list_findings) == 1


@pytest.mark.parametrize(
    "str_extra",
    [
        "      needs: [x]\n",
        "    if: github.workflow == 'Scaffold checks'\n",
        "    env:\n      N: $GITHUB_WORKFLOW\n",
    ],
)
def test_workflow_job_moved_with_a_hidden_dependency_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_extra: str
) -> None:
    """A deeper-indented ``needs:`` or a ``github.workflow`` read is judged unmovable."""
    str_job = _STR_MOVED_JOB + str_extra

    list_findings = _move_findings(
        monkeypatch, str_target=_STR_SIBLING, str_job_new=str_job, str_job_old=str_job
    )

    assert len(list_findings) == 1


def test_workflow_job_moved_from_a_file_deriving_env_from_the_workflow_name_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A header ``env:`` built from ``github.workflow`` changes value when the name does."""
    str_header = "env:\n  WF: ${{ github.workflow }}\n"
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"name: A\n{str_header}jobs:\n{_STR_MOVED_JOB}{_STR_KEPT_JOB}"},
        dict_new={
            _STR_SOURCE: f"name: A\n{str_header}jobs:\n{_STR_KEPT_JOB}",
            _STR_SIBLING: f"name: B\n{str_header}jobs:\n{_STR_MOVED_JOB}",
        },
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert len(list_findings) == 1


def test_deletion_of_a_renamed_test_file_reports_when_its_code_changed() -> None:
    """A renamed test file reads as delete plus add, so renaming it can not hide a gutting."""
    list_changed = [
        ("D", "tests/unit/test_a.py"),
        ("A", "tests/unit/test_b.py"),
        ("M", "src/a.py"),
    ]

    list_findings = gate.deletion_problems(
        list_changed, set_touched_stems=gate.touched_code_stems(list_changed)
    )

    assert list_findings == [
        "tests/unit/test_a.py: test file deleted while its code under test changed"
    ]


@pytest.mark.parametrize(
    ("str_from", "str_to"),
    [
        ("ubuntu-latest", "ubuntu-24.04"),
        ("ubuntu-22.04-arm", "ubuntu-24.04-arm"),
        ("ubuntu-latest", '"ubuntu-latest"'),
        ("ubuntu-latest", "ubuntu-latest  # pinned"),
    ],
)
def test_workflow_job_moved_between_hosted_runners_is_clean(
    monkeypatch: pytest.MonkeyPatch, *, str_from: str, str_to: str
) -> None:
    """Hosted images of one architecture, quoted or commented, are the same runner."""
    list_findings = _move_findings(
        monkeypatch,
        str_target=_STR_SIBLING,
        str_job_new=_STR_MOVED_JOB.replace("ubuntu-latest", str_to),
        str_job_old=_STR_MOVED_JOB.replace("ubuntu-latest", str_from),
    )

    assert list_findings == []


def _move_under_concurrency(
    monkeypatch: pytest.MonkeyPatch, *, str_source: str, str_target: str
) -> list[str]:
    """Move a job between workflows whose ``concurrency:`` blocks are given.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Fixture used to stub ``gate.show``.
    str_source : str
        The source workflow's ``concurrency:`` block, or empty.
    str_target : str
        The target workflow's ``concurrency:`` block, or empty.

    Returns
    -------
    list[str]
        The gate's findings.
    """
    return _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"{str_source}jobs:\n{_STR_MOVED_JOB}{_STR_KEPT_JOB}"},
        dict_new={
            _STR_SOURCE: f"{str_source}jobs:\n{_STR_KEPT_JOB}",
            _STR_SIBLING: f"{str_target}jobs:\n{_STR_MOVED_JOB}",
        },
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )


def test_workflow_job_moved_under_an_identical_concurrency_group_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two workflows sharing one group cancel or queue each other's required check."""
    str_block = "concurrency:\n  group: ci-${{ github.ref }}\n  cancel-in-progress: true\n"

    list_findings = _move_under_concurrency(
        monkeypatch, str_source=str_block, str_target=str_block
    )

    assert len(list_findings) == 1


def test_workflow_job_moved_under_a_different_concurrency_group_is_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A group of its own is the intended shape of a moved job's workflow."""
    str_source = "concurrency:\n  group: ci-${{ github.ref }}\n"
    str_target = "concurrency:\n  group: gate-${{ github.ref }}\n"

    list_findings = _move_under_concurrency(
        monkeypatch, str_source=str_source, str_target=str_target
    )

    assert list_findings == []


@pytest.mark.parametrize(
    "str_target",
    [
        "concurrency:\n  group: ci-${{ github.ref }}\n  cancel-in-progress: false\n",
        "concurrency: ci-${{ github.ref }}\n",
        "concurrency:\n  group: 'ci-${{ github.ref }}'  # same group\n",
    ],
)
def test_workflow_job_moved_into_the_same_group_in_another_form_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_target: str
) -> None:
    """The group decides the collision, not the block's text."""
    str_source = "concurrency:\n  group: ci-${{ github.ref }}\n  cancel-in-progress: true\n"

    list_findings = _move_under_concurrency(
        monkeypatch, str_source=str_source, str_target=str_target
    )

    assert len(list_findings) == 1


def test_workflow_job_moved_under_a_workflow_keyed_group_is_clean_when_names_differ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``github.workflow`` evaluates per workflow, so a verbatim copy is a group of its own."""
    str_block = "concurrency:\n  group: ${{ github.workflow }}-${{ github.ref }}\n"

    list_findings = _move_under_concurrency(
        monkeypatch,
        str_source=f"name: CI\n{str_block}",
        str_target=f"name: Gate\n{str_block}",
    )

    assert list_findings == []


def test_workflow_job_moved_under_a_workflow_keyed_group_is_removed_when_names_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Equal names make the evaluated groups equal."""
    str_block = "name: CI\nconcurrency:\n  group: ${{ github.workflow }}-${{ github.ref }}\n"

    list_findings = _move_under_concurrency(
        monkeypatch, str_source=str_block, str_target=str_block
    )

    assert len(list_findings) == 1


def test_workflow_job_moved_from_a_concurrency_group_into_none_is_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A target with no group cannot collide with the source's."""
    list_findings = _move_under_concurrency(
        monkeypatch, str_source="concurrency:\n  group: ci-${{ github.ref }}\n", str_target=""
    )

    assert list_findings == []


def test_workflow_job_moved_with_identical_unindented_steps_is_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Witness that the non-indented sequence style compares equal when truly identical."""
    str_job = "  gate-integrity:\n    name: G\n    steps:\n    - run: a\n"
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"jobs:\n{str_job}{_STR_KEPT_JOB}"},
        dict_new={_STR_SOURCE: f"jobs:\n{_STR_KEPT_JOB}", _STR_SIBLING: f"jobs:\n{str_job}"},
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert list_findings == []
