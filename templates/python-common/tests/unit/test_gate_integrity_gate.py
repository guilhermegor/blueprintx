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

import functools
import importlib.util
import os
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
    """NEGATIVE CONTROL: an unset/blank env var must not mask a real trailer/PR-body reason.

    Runs as CI: locally a bare trailer is a claim anyone can type, so it justifies nothing by
    itself (see the ``branch_justified`` tests below).
    """
    _bare_shell(monkeypatch)
    monkeypatch.setenv("CI", "true")
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


_SET_SCRUBBED_ENV = frozenset(
    {
        "CI",
        "GITHUB_ACTIONS",
        "GITHUB_BASE_REF",
        "GITHUB_EVENT_PATH",
        "GITHUB_REPOSITORY",
        "PR_NUMBER",
        "GATE_CHANGE_OK",
    }
)


def _hermetic_env() -> dict:
    """Return a copy of ``os.environ`` that cannot steer git or the gate.

    Returns
    -------
    dict
        The environment minus CI markers, PR context, the local escape hatch and every
        ``GIT_*`` key, with the operator's global and system git config disabled.
    """
    dict_env = {
        str_key: str_val
        for str_key, str_val in os.environ.items()
        if str_key not in _SET_SCRUBBED_ENV and not str_key.startswith("GIT_")
    }
    dict_env["GIT_CONFIG_GLOBAL"] = os.devnull
    dict_env["GIT_CONFIG_NOSYSTEM"] = "1"
    return dict_env


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
        env=_hermetic_env(),
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
_STR_THIRD_JOB = "  third:\n    name: Third\n    steps:\n      - run: echo there\n"
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
        "    outputs:\n      out: *gate_step\n",
        '    "needs": [build]\n',
        "    'needs': [build]\n",
        "    outputs: {out: *gate_step}\n",
        "    env: !!map &shared\n      A: '1'\n",
    ],
)
def test_workflow_job_moved_with_outside_dependency_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_extra: str
) -> None:
    """``needs:`` and YAML anchors point outside the block, so an identical text is no proof."""
    str_job = _STR_MOVED_JOB.replace("ubuntu-latest\n", f"ubuntu-latest\n{str_extra}")
    str_defs = "x-defs:\n  shared: &shared {A: '1'}\n  gate_step: &gate_step {run: a}\n" * (
        "&" not in str_extra
    )
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"{str_defs}jobs:\n{str_job}{_STR_KEPT_JOB}"},
        dict_new={
            _STR_SOURCE: f"{str_defs}jobs:\n{_STR_KEPT_JOB}",
            _STR_SIBLING: f"{str_defs}jobs:\n{str_job}",
        },
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert list_findings == [f"{_STR_SOURCE}: workflow job 'gate-integrity' removed"]


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


@pytest.mark.parametrize(
    ("str_source", "str_target"),
    [
        (
            "concurrency:\n  group: ci-${{ github.ref }}\n",
            "concurrency: {group: ci-${{ github.ref }}, cancel-in-progress: true}\n",
        ),
        (
            "concurrency: {group: ci}\n",
            "concurrency:\n  group: ci\n",
        ),
        (
            "concurrency:\n  group: ci-${{ github.ref }}\n",
            "concurrency:\n  group: ci-${{github.ref}}\n",
        ),
        (
            "concurrency:\n  group: ci-${{ github.ref }}\n",
            "concurrency:\n  group: ci-${{ GitHub.Ref }}\n",
        ),
        (
            "name: CI\nconcurrency:\n  group: ${{ github.workflow }}\n",
            "name: CI\nconcurrency:\n  group: ${{GitHub.Workflow}}\n",
        ),
    ],
)
def test_workflow_job_moved_into_an_unparsed_or_respelled_same_group_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_source: str, str_target: str
) -> None:
    """A flow mapping is never excused, and expression spelling does not change the group."""
    list_findings = _move_under_concurrency(
        monkeypatch, str_source=str_source, str_target=str_target
    )

    assert len(list_findings) == 1


@pytest.mark.parametrize(
    ("str_source", "str_target"),
    [
        ("concurrency:\n  group: CI-x\n", "concurrency:\n  group: ci-x\n"),
        (
            "name: CI\nconcurrency:\n  group: ${{ github.workflow }}\n",
            "name: ci\nconcurrency:\n  group: ${{ github.workflow }}\n",
        ),
        ('"concurrency":\n  group: ci\n', '"concurrency":\n  group: ci\n'),
        ("concurrency:\n  group: ci\n", "'concurrency':\n  \"group\": ci\n"),
        ("concurrency:\n  group: ci\n", "concurrency : { group: ci }\n"),
        ("concurrency:\n  group: ci\n", "concurrency:\n  group: |\n    ci\n"),
        (
            "concurrency:\n  cancel-in-progress: true\n",
            "concurrency:\n  cancel-in-progress: true\n",
        ),
    ],
)
def test_workflow_job_moved_into_a_group_the_parser_must_not_excuse_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_source: str, str_target: str
) -> None:
    """Case, quoted keys, a spaced flow key, block scalars and group-less blocks stay reported."""
    list_findings = _move_under_concurrency(
        monkeypatch, str_source=str_source, str_target=str_target
    )

    assert len(list_findings) == 1


def test_workflow_job_moved_into_flow_concurrency_from_none_is_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no source group there is nothing to collide with, flow style or not."""
    list_findings = _move_under_concurrency(
        monkeypatch, str_source="", str_target="concurrency: {group: ci}\n"
    )

    assert list_findings == []


@pytest.mark.parametrize(
    ("str_source", "str_target"),
    [
        ("concurrency:\n  group : ci\n", "concurrency:\n  group: ci\n"),
        ("concurrency:\n  group:\n    ci-x\n", "concurrency:\n  group: ci-x\n"),
        ("concurrency:\n  group: ci-x\n", "concurrency:\n  group:\n    ci-x\n"),
    ],
)
def test_workflow_job_moved_into_a_spaced_or_multiline_group_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_source: str, str_target: str
) -> None:
    """A spaced key parses to an equal group; a multi-line value is unparsed. Both are reported."""
    list_findings = _move_under_concurrency(
        monkeypatch, str_source=str_source, str_target=str_target
    )

    assert len(list_findings) == 1


def test_workflow_job_moved_into_the_group_the_source_takes_in_the_same_change_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Judging the source by its base group alone misses a group both files share afterwards."""
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={
            _STR_SOURCE: f"concurrency:\n  group: ci\njobs:\n{_STR_MOVED_JOB}{_STR_KEPT_JOB}"
        },
        dict_new={
            _STR_SOURCE: f"concurrency:\n  group: gate\njobs:\n{_STR_KEPT_JOB}",
            _STR_SIBLING: f"concurrency:\n  group: gate\njobs:\n{_STR_MOVED_JOB}",
        },
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert len(list_findings) == 1


def test_workflow_ref_group_is_a_plain_group_not_a_name_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``github.workflow_ref`` is not the name: a distinct group on it is a clean move."""
    list_findings = _move_under_concurrency(
        monkeypatch,
        str_source="concurrency:\n  group: ci\n",
        str_target="concurrency:\n  group: ${{ github.workflow_ref }}\n",
    )

    assert list_findings == []


def test_workflow_job_reading_the_name_through_an_index_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``github['workflow']`` reads the workflow name like ``github.workflow``."""
    str_job = _STR_MOVED_JOB + "      - run: echo ${{ github['workflow'] }}\n"
    list_findings = _move_findings(
        monkeypatch, str_target=_STR_SIBLING, str_job_new=str_job, str_job_old=str_job
    )

    assert len(list_findings) == 1


@pytest.mark.parametrize(
    ("str_source", "str_target"),
    [
        ("concurrency:\n  group: ci- x\n", "concurrency:\n  group: ci-\n    x\n"),
        ("concurrency:\n  group: ci- x\n", 'concurrency:\n  group: "ci-\n    x"\n'),
        ("concurrency:\n  group: ci\n", "concurrency: !!map { group: ci }\n"),
        ("concurrency:\n  group: ci\n", "concurrency: &c { group: ci }\n"),
        (
            '"name": CI\nconcurrency:\n  group: ${{ github.workflow }}\n',
            "name: CI\nconcurrency:\n  group: ${{ github.workflow }}\n",
        ),
        (
            '"name": CI\nconcurrency:\n  group: ${{ github.workflow }}\n',
            '"name": CI\nconcurrency:\n  group: ${{ github.workflow }}\n',
        ),
        (
            "concurrency:\n  group: ${{ github.workflow }}\n",
            "concurrency:\n  group: ${{ github.workflow }}\n",
        ),
    ],
)
def test_workflow_job_moved_into_a_continued_tagged_or_unnamed_group_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_source: str, str_target: str
) -> None:
    """A continued value, a tagged flow mapping or an unread name never excuses a move."""
    list_findings = _move_under_concurrency(
        monkeypatch, str_source=str_source, str_target=str_target
    )

    assert len(list_findings) == 1


def test_workflow_job_with_a_flow_body_on_the_line_after_its_id_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A job whose body is a flow mapping can hide ``needs:`` and is never excused."""
    str_job = "  gate-integrity:\n    {needs: [other], runs-on: ubuntu-latest}\n"
    list_findings = _move_findings(
        monkeypatch, str_target=_STR_SIBLING, str_job_new=str_job, str_job_old=str_job
    )

    assert len(list_findings) == 1


@pytest.mark.parametrize(
    ("str_source", "str_target"),
    [
        ("concurrency:\n  group: ci\n", "concurrency: *c\n"),
        ("concurrency:\n  group: ci\n", "concurrency:\n  group: !!str ci\n"),
        ("concurrency:\n  group: ci- abc:\n", 'concurrency:\n  group: "ci-\n    abc:"\n'),
        (
            "name: CI\nconcurrency:\n  group: ${{ github.workflow }}\n",
            "name: CI\nconcurrency:\n  group: ${{ github['workflow'] }}\n",
        ),
        (
            "name: CI\nconcurrency:\n  group: ${{ github.workflow }}\n",
            "name: CI\nconcurrency:\n  group: ${{ format('{0}', github.workflow) }}\n",
        ),
    ],
)
def test_workflow_job_moved_into_an_alias_or_respelled_name_group_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_source: str, str_target: str
) -> None:
    """An alias, a tag, an unbalanced quote or another spelling of the name read is unparsed."""
    list_findings = _move_under_concurrency(
        monkeypatch, str_source=str_source, str_target=str_target
    )

    assert len(list_findings) == 1


def test_workflow_job_moved_under_a_group_with_a_hash_inside_a_word_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only a space-preceded ``#`` starts a comment, so ``pr#x`` is the whole group."""
    list_findings = _move_under_concurrency(
        monkeypatch,
        str_source="concurrency:\n  group: pr#x\n",
        str_target="concurrency:\n  group: pr#x\n",
    )

    assert len(list_findings) == 1


def test_workflow_job_moved_under_groups_differing_after_a_hash_in_a_word_is_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The text after an in-word ``#`` is part of the group, so these two differ."""
    list_findings = _move_under_concurrency(
        monkeypatch,
        str_source="concurrency:\n  group: pr#x\n",
        str_target="concurrency:\n  group: pr#y\n",
    )

    assert list_findings == []


def test_workflow_job_moved_under_a_group_named_in_a_trailing_comment_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``group:`` inside a trailing comment is not the group, so equal real groups collide."""
    str_comment = "concurrency:\n  cancel-in-progress: true  # old group: zzz\n  group: ci\n"

    list_findings = _move_under_concurrency(
        monkeypatch, str_source=str_comment, str_target="concurrency:\n  group: ci\n"
    )

    assert len(list_findings) == 1


def _move_with_headers(
    monkeypatch: pytest.MonkeyPatch, *, str_source: str, str_target: str
) -> list[str]:
    """Move the job between two workflows whose text outside ``jobs:`` is given.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Fixture used to stub ``gate.show``.
    str_source : str
        The source workflow's text before ``jobs:``.
    str_target : str
        The target workflow's text before ``jobs:``.

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


def test_workflow_with_a_quoted_jobs_key_still_reports_a_removed_job() -> None:
    """A quoted ``"jobs":`` key is the same key, so a job dropped under it is reported."""
    str_old = f'"jobs":\n{_STR_KEPT_JOB}{_STR_MOVED_JOB}'

    assert gate.workflow_problems(str_old, str_new='"jobs":\n' + _STR_KEPT_JOB, str_shown="w") == [
        "w: workflow job 'gate-integrity' removed"
    ]


def test_workflow_that_no_longer_parses_is_a_finding() -> None:
    """A file whose jobs cannot be read is reported, never read as having none to lose."""
    str_new = f"jobs:\n{_STR_KEPT_JOB}  broken: [\n"

    assert gate.workflow_problems(f"jobs:\n{_STR_KEPT_JOB}", str_new=str_new, str_shown="w") == [
        "w: workflow YAML does not parse, so its jobs cannot be compared"
    ]


def test_workflow_job_moved_beside_a_comment_between_jobs_is_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A comment is not a value, so the one left between jobs does not block a move."""
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"jobs:\n{_STR_MOVED_JOB}{_STR_KEPT_JOB}{_STR_THIRD_JOB}"},
        dict_new={
            _STR_SOURCE: f"jobs:\n{_STR_KEPT_JOB}# gate-integrity moved\n{_STR_THIRD_JOB}",
            _STR_SIBLING: f"jobs:\n{_STR_MOVED_JOB}",
        },
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert list_findings == []


def test_workflow_job_moved_under_a_setting_with_another_trailing_comment_is_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comments on a top-level setting are not part of its value."""
    list_findings = _move_with_headers(
        monkeypatch, str_source="on: push\n", str_target="on: push  # moved\n"
    )

    assert list_findings == []


@pytest.mark.parametrize(
    "str_run",
    ["echo *.py", "|\n          { echo hi; }", "|\n          [ -f x ] && echo hi"],
)
def test_workflow_job_whose_script_holds_a_star_or_bracket_is_a_clean_move(
    monkeypatch: pytest.MonkeyPatch, *, str_run: str
) -> None:
    """A ``*word`` or a leading ``[``/``{`` in a script is text, not an alias or flow body."""
    str_job = _STR_MOVED_JOB + f"      - run: {str_run}\n"

    list_findings = _move_findings(
        monkeypatch, str_target=_STR_SIBLING, str_job_new=str_job, str_job_old=str_job
    )

    assert list_findings == []


def test_workflow_job_moved_with_a_needs_key_nested_in_a_matrix_is_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only a top-level ``needs`` is a dependency; one inside ``strategy.matrix`` is data."""
    str_job = _STR_MOVED_JOB + "    strategy:\n      matrix:\n        needs: [x]\n"

    list_findings = _move_findings(
        monkeypatch, str_target=_STR_SIBLING, str_job_new=str_job, str_job_old=str_job
    )

    assert list_findings == []


@pytest.mark.parametrize(
    "str_extra",
    [
        "    ? needs\n    : [build]\n",
        "    !!str needs: [build]\n",
        "    env: &a_b\n      A: '1'\n",
    ],
)
def test_workflow_job_moved_with_an_exotic_dependency_or_anchor_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_extra: str
) -> None:
    """An explicit ``? needs`` key or a non-word anchor name is still a parsed key or anchor."""
    str_job = _STR_MOVED_JOB.replace("ubuntu-latest\n", f"ubuntu-latest\n{str_extra}")
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"jobs:\n{str_job}{_STR_KEPT_JOB}"},
        dict_new={_STR_SOURCE: f"jobs:\n{_STR_KEPT_JOB}", _STR_SIBLING: f"jobs:\n{str_job}"},
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert list_findings == [f"{_STR_SOURCE}: workflow job 'gate-integrity' removed"]


@pytest.mark.parametrize("str_on", ["on: [workflow_call]\n", "on:\n  push:\n  workflow_call:\n"])
def test_workflow_job_moved_between_reusable_workflows_in_list_or_map_form_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_on: str
) -> None:
    """``workflow_call`` among several triggers still makes the source a reusable workflow."""
    list_findings = _move_with_headers(monkeypatch, str_source=str_on, str_target=str_on)

    assert list_findings == [f"{_STR_SOURCE}: workflow job 'gate-integrity' removed"]


@pytest.mark.parametrize(
    "str_target",
    [
        "concurrency:\n  group: [ci]\n",
        "concurrency:\n  group: {a: b}\n",
        "concurrency:\n",
    ],
)
def test_workflow_job_moved_into_a_non_string_group_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_target: str
) -> None:
    """A group that is not a string cannot be evaluated here, so it never excuses a move."""
    list_findings = _move_under_concurrency(
        monkeypatch, str_source="concurrency:\n  group: ci\n", str_target=str_target
    )

    assert list_findings == [f"{_STR_SOURCE}: workflow job 'gate-integrity' removed"]


def test_workflow_read_keeps_the_on_key_and_empty_values_as_text() -> None:
    """The loader resolves no bool or null, so ``on`` is the string key and ``jobs:`` is ``""``."""
    assert gate.read_workflow("on: push\njobs:\n")[0] == {"on": "push", "jobs": ""}


def test_workflow_read_rejects_a_self_referential_alias() -> None:
    """A recursive alias cannot be walked, so it is unparsed rather than a crash."""
    assert gate.read_workflow("a: &x [*x]\njobs:\n") is None


@pytest.mark.parametrize(
    ("str_from", "str_to"),
    [("~", "null"), ("2026-01-01T00:00:00", "2026-01-01 00:00:00"), ("=", "x")],
)
def test_workflow_job_moved_with_a_respelled_null_date_or_value_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_from: str, str_to: str
) -> None:
    """The null, timestamp and ``=`` resolvers are off, so these stay different text."""
    list_findings = _move_findings(
        monkeypatch,
        str_target=_STR_SIBLING,
        str_job_new=_STR_MOVED_JOB + f"    env:\n      X: {str_to}\n",
        str_job_old=_STR_MOVED_JOB + f"    env:\n      X: {str_from}\n",
    )

    assert list_findings == [f"{_STR_SOURCE}: workflow job 'gate-integrity' removed"]


def test_workflow_repair_of_an_unparseable_base_reports_nothing() -> None:
    """A base that did not parse has no comparable jobs, so its repair is not a finding."""
    assert (
        gate.workflow_problems("jobs: [\n", str_new=f"jobs:\n{_STR_KEPT_JOB}", str_shown="w") == []
    )


@pytest.mark.parametrize(
    "str_text",
    [
        "x: &a\n  gate:\n    runs-on: u\njobs:\n  <<: *a\n  other:\n    runs-on: u\n",
        "x: &j\n  gate:\n    runs-on: u\njobs: *j\n",
    ],
)
def test_workflow_read_rejects_a_merge_key_or_alias_supplying_jobs(str_text: str) -> None:
    """Jobs merged or aliased into ``jobs:`` have no key to flag, so the file is unparsed."""
    assert gate.read_workflow(str_text) is None


def test_workflow_base_with_a_merge_key_under_jobs_reports_instead_of_passing() -> None:
    """A base that is YAML but unreadable is a finding, not a free deletion of every job."""
    str_old = "x: &a\n  gate:\n    runs-on: u\njobs:\n  <<: *a\n"

    assert gate.workflow_problems(str_old, str_new="jobs:\n  keep:\n", str_shown="w") == [
        "w: base workflow uses YAML the gate refuses to read, so its jobs are unchecked"
    ]


@pytest.mark.parametrize("str_body", ["", " ~", " foo"])
def test_workflow_with_a_scalar_job_body_reports_instead_of_crashing(str_body: str) -> None:
    """A job whose value is a scalar is read, not an ``AttributeError``."""
    str_old = f"jobs:\n  x:{str_body}\n  keep:\n    runs-on: ubuntu-latest\n"

    assert gate.workflow_problems(str_old, str_new="jobs:\n  keep:\n", str_shown="w") == [
        "w: workflow job 'x' removed"
    ]


@pytest.mark.parametrize(
    ("str_from", "str_to"),
    [("on", "true"), ("yes", "true"), ("1", "1.0"), ("1:20", "80")],
)
def test_workflow_job_moved_with_a_respelled_scalar_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_from: str, str_to: str
) -> None:
    """YAML 1.1 reads these as equal values; GitHub passes them through as different text."""
    list_findings = _move_findings(
        monkeypatch,
        str_target=_STR_SIBLING,
        str_job_new=_STR_MOVED_JOB + f"    env:\n      X: {str_to}\n",
        str_job_old=_STR_MOVED_JOB + f"    env:\n      X: {str_from}\n",
    )

    assert list_findings == [f"{_STR_SOURCE}: workflow job 'gate-integrity' removed"]


def test_workflow_with_a_second_document_does_not_parse() -> None:
    """Only one document is a workflow; a second ``---`` document is a parse failure."""
    assert gate.read_workflow("jobs:\n---\njobs:\n") is None


def test_workflow_flow_style_job_with_a_boolean_looking_id_is_not_movable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The flow-style check keys ``yes`` like the job table, so an identical copy is refused."""
    str_job = "  yes: {runs-on: ubuntu-latest}\n"
    list_findings = _collect_workflows(
        monkeypatch,
        dict_old={_STR_SOURCE: f"jobs:\n{str_job}{_STR_KEPT_JOB}"},
        dict_new={_STR_SOURCE: f"jobs:\n{_STR_KEPT_JOB}", _STR_SIBLING: f"jobs:\n{str_job}"},
        list_changed=[("M", _STR_SOURCE), ("A", _STR_SIBLING)],
    )

    assert len(list_findings) == 1


@pytest.mark.parametrize("str_value", ["!!int x", "!!float x", "!!bool x", "!!timestamp x"])
def test_workflow_with_a_bad_explicit_tag_is_read_as_text(str_value: str) -> None:
    """An explicit core tag constructs text, so a bad value cannot crash a constructor."""
    assert gate.read_workflow(f"X: {str_value}\njobs:\n")[0]["X"] == "x"


@pytest.mark.parametrize(
    ("str_from", "str_to"),
    [("!!int 1", "!!float 1.0"), ("!!bool true", "!!int 1")],
)
def test_workflow_job_moved_with_a_retagged_scalar_is_removed(
    monkeypatch: pytest.MonkeyPatch, *, str_from: str, str_to: str
) -> None:
    """Tags do not make ``1``, ``1.0`` and ``true`` equal: each is the text it spells."""
    list_findings = _move_findings(
        monkeypatch,
        str_target=_STR_SIBLING,
        str_job_new=_STR_MOVED_JOB + f"    env:\n      X: {str_to}\n",
        str_job_old=_STR_MOVED_JOB + f"    env:\n      X: {str_from}\n",
    )

    assert list_findings == [f"{_STR_SOURCE}: workflow job 'gate-integrity' removed"]


def test_workflow_with_a_root_level_merge_key_does_not_parse() -> None:
    """A root merge key can supply ``jobs`` unseen, so the file is unparsed, not trusted."""
    assert gate.read_workflow("<<: {jobs: {}}\n") is None


def test_workflow_with_a_shared_alias_chain_is_read_without_blowing_up() -> None:
    """A node shared by many aliases is walked once, so the strings walk stays linear."""
    str_text = "a: &a [x, x]\nb: &b [*a, *a]\nc: &c [*b, *b]\nd: &d [*c, *c]\ne: [*d, *d]\n"

    assert len(list(gate.iter_strings(gate.read_workflow(str_text)[0]))) == 7


_STR_RUFF_BASE = '[lint]\nselect = ["E", "F"]\nignore = []\n'
_STR_RUFF_WEAKER = '[lint]\nselect = ["E", "F"]\nignore = ["E501"]\n'
_STR_RUFF_WEAKEST = '[lint]\nselect = ["E", "F"]\nignore = ["E501", "E402"]\n'
_STR_RUFF_STRICTER = '[lint]\nselect = ["E", "F", "W"]\nignore = []\n'
_STR_TRAILER = "feat: x\n\ngate-change-ok: owner reviewed the ignore\n"


def _stage(path_repo: Path, *, str_name: str, str_text: str) -> None:
    """Write a file under the repo and stage it.

    Parameters
    ----------
    path_repo : pathlib.Path
        The repository.
    str_name : str
        Repository-relative file name.
    str_text : str
        File content.
    """
    (path_repo / str_name).parent.mkdir(parents=True, exist_ok=True)
    (path_repo / str_name).write_text(str_text, encoding="utf-8")
    _git_in(path_repo, "add", str_name)


def _commit_staged(path_repo: Path, *, str_message: str) -> None:
    """Commit the index, as the pre-commit run that already passed would let it.

    Parameters
    ----------
    path_repo : pathlib.Path
        The repository.
    str_message : str
        Full commit message.
    """
    _git_in(path_repo, "commit", "-q", "-m", str_message)


@pytest.fixture
def path_branch(tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a repo on ``feature`` forked from a ``main`` that carries a strict ``ruff.toml``.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided scratch directory.
    monkeypatch : pytest.MonkeyPatch
        Puts the gate in a local shell, with no ``GATE_CHANGE_OK``, inside the repo.

    Returns
    -------
    pathlib.Path
        The repository, checked out on ``feature``.
    """
    _local_shell(monkeypatch)
    monkeypatch.delenv("GATE_CHANGE_OK", raising=False)
    _git_in(tmp_path, "init", "-q", "--initial-branch=main")
    _git_in(tmp_path, "config", "user.email", "t@example.com")
    _git_in(tmp_path, "config", "user.name", "t")
    _stage(tmp_path, str_name="ruff.toml", str_text=_STR_RUFF_BASE)
    _commit_staged(tmp_path, str_message="seed")
    _git_in(tmp_path, "checkout", "-q", "-b", "feature")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def path_weakened(path_branch: Path, *, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return ``path_branch`` after the owner's justified, interactive weakening commit.

    The commit is made with ``GATE_CHANGE_OK`` set and no trailer in its message.

    Parameters
    ----------
    path_branch : pathlib.Path
        The branch fixture.
    monkeypatch : pytest.MonkeyPatch
        Sets then clears ``GATE_CHANGE_OK``.

    Returns
    -------
    pathlib.Path
        The repository after the weakening commit.
    """
    _stage(path_branch, str_name="ruff.toml", str_text=_STR_RUFF_WEAKER)
    monkeypatch.setenv("GATE_CHANGE_OK", "owner reviewed the ignore")
    _commit_staged(path_branch, str_message="feat: x")
    monkeypatch.delenv("GATE_CHANGE_OK")
    return path_branch


@pytest.fixture
def path_recorded(path_branch: Path, *, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return ``path_branch`` after an interactive approval and its commit.

    Parameters
    ----------
    path_branch : pathlib.Path
        The branch fixture.
    monkeypatch : pytest.MonkeyPatch
        Sets then clears ``GATE_CHANGE_OK``.

    Returns
    -------
    pathlib.Path
        The repository after the weakening commit.
    """
    _stage(path_branch, str_name="ruff.toml", str_text=_STR_RUFF_WEAKER)
    monkeypatch.setenv("GATE_CHANGE_OK", "owner reviewed the ignore")
    gate.main([])
    _commit_staged(path_branch, str_message=_STR_TRAILER)
    monkeypatch.delenv("GATE_CHANGE_OK")
    return path_branch


def test_branch_justified_without_a_trailer_still_refuses_a_later_commit(
    path_weakened: Path,
) -> None:
    """The defect as measured on #1321: a later tests-only commit is refused again."""
    _stage(path_weakened, str_name="tests/unit/test_a.py", str_text="X = 1\n")

    assert gate.main([]) == 1


def test_branch_justified_by_recorded_trailer_passes_a_tests_only_commit(
    path_recorded: Path,
) -> None:
    """SHOULD PASS: the finding was justified on this branch, so a test-only commit is clean."""
    _stage(path_recorded, str_name="tests/unit/test_a.py", str_text="X = 1\n")

    assert gate.main([]) == 0


def test_branch_justified_by_recorded_trailer_passes_with_nothing_new_staged(
    path_recorded: Path,
) -> None:
    """SHOULD PASS: the merge-with-main shape — nothing of this branch's own changes."""
    assert gate.main([]) == 0


def test_branch_justified_by_recorded_trailer_refuses_a_new_weakening(
    path_recorded: Path,
    *,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SHOULD FAIL: a NEW weakening on a justified branch still needs a fresh override."""
    _stage(path_recorded, str_name="ruff.toml", str_text=_STR_RUFF_WEAKEST)

    int_code = gate.main([])

    assert (int_code, "E402" in capsys.readouterr().out) == (1, True)


def test_branch_justified_forged_trailer_on_a_clean_commit_justifies_nothing(
    path_branch: Path,
    *,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SHOULD FAIL: an agent-typed trailer on a commit with no findings of its own is void."""
    _stage(path_branch, str_name="tests/unit/test_a.py", str_text="X = 1\n")
    _commit_staged(path_branch, str_message=_STR_TRAILER)
    _stage(path_branch, str_name="ruff.toml", str_text=_STR_RUFF_WEAKER)

    int_code = gate.main([])

    assert (int_code, "E501" in capsys.readouterr().out) == (1, True)


def test_branch_justified_trailer_without_an_approval_record_justifies_nothing(
    path_branch: Path,
    *,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SHOULD FAIL: a weakening committed with a typed trailer but no interactive run is void."""
    _stage(path_branch, str_name="ruff.toml", str_text=_STR_RUFF_WEAKER)
    _commit_staged(path_branch, str_message=_STR_TRAILER)
    _stage(path_branch, str_name="tests/unit/test_a.py", str_text="X = 1\n")

    int_code = gate.main([])

    assert (int_code, "E501" in capsys.readouterr().out) == (1, True)


def test_branch_justified_recorded_findings_do_not_widen_with_the_checker(
    path_recorded: Path, *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SHOULD FAIL: a check added after the approval is not covered by the frozen record."""
    str_base = _git_in(path_recorded, "rev-parse", "main").strip()
    set_before = gate.recorded_findings(str_base)
    monkeypatch.setattr(gate, "collect_problems", lambda *_, **__: ["a newer check fired"])

    assert (gate.recorded_findings(str_base), bool(set_before)) == (set_before, True)


def test_branch_justified_cherry_pick_onto_a_new_tree_loses_the_approval(
    path_recorded: Path,
    *,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SHOULD FAIL: a replay that changes the tree finds no record, so it needs the owner."""
    str_sha = _git_in(path_recorded, "rev-parse", "HEAD").strip()
    _git_in(path_recorded, "checkout", "-q", "main")
    _stage(path_recorded, str_name="other.txt", str_text="x\n")
    _commit_staged(path_recorded, str_message="chore: main moves on")
    _git_in(path_recorded, "checkout", "-q", "-b", "replayed")
    _git_in(path_recorded, "cherry-pick", str_sha)

    int_code = gate.main([])

    assert (int_code, "E501" in capsys.readouterr().out) == (1, True)


def test_ci_approval_is_published_with_finding_reason_and_pr_body(
    path_branch: Path, *, monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A PR-body approval accepted in CI lands in the job summary naming the finding."""
    path_summary = tmp_path_factory.mktemp("summary") / "summary.md"
    monkeypatch.setattr(gate, "is_ci", lambda: True)
    monkeypatch.setattr(gate, "pr_body_text", lambda: "gate-change-ok: reviewed by owner")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(path_summary))
    _stage(path_branch, str_name="ruff.toml", str_text=_STR_RUFF_WEAKER)

    gate.main([])

    str_text = path_summary.read_text(encoding="utf-8")
    assert all(str_part in str_text for str_part in ("E501", "reviewed by owner", "PR body"))


def test_ci_approval_comment_names_the_commit_carrying_the_line(
    path_branch: Path, *, monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A trailer approval accepted in CI is written to the comment file with its commit."""
    path_comment = tmp_path_factory.mktemp("comment") / "comment.md"
    monkeypatch.setattr(gate, "is_ci", lambda: True)
    monkeypatch.setattr(gate, "pr_body_text", lambda: "")
    monkeypatch.setenv("GATE_APPROVAL_COMMENT", str(path_comment))
    _stage(path_branch, str_name="ruff.toml", str_text=_STR_RUFF_WEAKER)
    _commit_staged(path_branch, str_message=_STR_TRAILER)
    str_sha = _git_in(path_branch, "rev-parse", "HEAD").strip()

    gate.main([])

    assert f"commit {str_sha[:12]}" in path_comment.read_text(encoding="utf-8")


def test_branch_justified_after_main_adds_a_gate_does_not_record_it(
    path_recorded: Path,
    *,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SHOULD FAIL: a gate main added after the trailer commit is not justified by it."""
    _git_in(path_recorded, "checkout", "-q", "main")
    _stage(path_recorded, str_name="ruff.toml", str_text=_STR_RUFF_STRICTER)
    _commit_staged(path_recorded, str_message="chore: main adds rule W")
    _git_in(path_recorded, "checkout", "-q", "feature")
    _git_in(path_recorded, "merge", "-q", "-s", "ours", "main", "-m", "merge main")

    int_code = gate.main([])

    assert (int_code, "ruff.toml" in capsys.readouterr().out) == (1, True)


@pytest.mark.parametrize(
    "str_text",
    [
        "jobs:\n  a:\n    steps: [1]\n    steps: [2]\n",
        "jobs:\n  a:\n    steps: [1]\n  a:\n    steps: [1]\n",
        "a: 1\x0b\njobs:\n",
    ],
    ids=["duplicate-steps", "duplicate-job", "control-character"],
)
def test_read_workflow_invalid_yaml_is_unparsed_not_a_crash(str_text: str) -> None:
    """A repeated key or a control character is a workflow that does not parse."""
    assert gate.read_workflow(str_text) is None


def test_branch_justified_trailer_on_a_merge_commit_justifies_nothing(
    path_branch: Path,
    *,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SHOULD FAIL: a merge skips pre-commit, so a trailer on it is not a recorded approval."""
    _git_in(path_branch, "checkout", "-q", "-b", "side", "main")
    _stage(path_branch, str_name="ruff.toml", str_text=_STR_RUFF_WEAKER)
    _commit_staged(path_branch, str_message="feat: side")
    _git_in(path_branch, "checkout", "-q", "feature")
    _git_in(path_branch, "merge", "-q", "--no-ff", "side", "-m", _STR_TRAILER)
    _stage(path_branch, str_name="tests/unit/test_a.py", str_text="X = 1\n")
    int_code = gate.main([])

    assert (int_code, "ruff.toml" in capsys.readouterr().out) == (1, True)


def test_local_run_ignores_a_bare_trailer_in_history(
    path_branch: Path, *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A local run reads no trailer as a blanket reason; only CI keeps that source."""
    monkeypatch.setattr(gate, "pr_body_text", lambda: "")
    _stage(path_branch, str_name="tests/unit/test_a.py", str_text="X = 1\n")
    _commit_staged(path_branch, str_message=_STR_TRAILER)

    assert gate.justification_reason(_git_in(path_branch, "rev-parse", "main")) == ""


def test_workflow_job_number_and_string_matrix_values_differ() -> None:
    """``[16]`` and ``["16"]`` are a number and a string to ``toJSON``, so the jobs differ."""
    str_head = "jobs:\n  a:\n    runs-on: ubuntu-latest\n    strategy:\n      matrix:\n        n: "
    dict_number = gate.workflow_jobs_of(gate.read_workflow(f"{str_head}[16]\n")[0])["a"]
    dict_string = gate.workflow_jobs_of(gate.read_workflow(f'{str_head}["16"]\n')[0])["a"]

    assert dict_number != dict_string


def test_workflow_typed_copy_is_not_text_a_job_id_is_searched_in() -> None:
    """A job id ``typed`` is not referenced just because each job carries a typed copy."""
    dict_document = gate.read_workflow("jobs:\n  other:\n    runs-on: ubuntu-latest\n")[0]

    assert gate.id_is_referenced("typed", dict_document=dict_document) is False


def _raise_recursion(*_tuple_args: object, **_dict_kwargs: object) -> None:
    """Stand in for ``yaml.compose`` on a document nested past the recursion limit."""
    raise RecursionError


def test_workflow_base_that_exhausts_the_recursion_limit_reports_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A base the composer cannot walk is a finding, not a ``RecursionError`` out of the gate."""
    monkeypatch.setattr(gate.yaml, "compose", _raise_recursion)

    assert gate.base_unreadable_problems("jobs:\n", str_shown="w") == [
        "w: base workflow nests too deeply for the gate, so its jobs are unchecked"
    ]


@pytest.fixture
def path_first_commit(tmp_path: Path) -> Path:
    """Build a clone on a fresh branch whose HEAD still equals the default branch tip.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest's per-test directory.

    Returns
    -------
    pathlib.Path
        The clone, checked out on ``feat/x``.
    """
    path_src = tmp_path / "src"
    path_src.mkdir()
    _git_in(path_src, "init", "-q", "-b", "main")
    (path_src / "ruff.toml").write_text('[lint]\nselect = ["E", "F", "S"]\n', encoding="utf-8")
    _git_in(path_src, "add", ".")
    _git_in(path_src, "-c", "user.email=a@b.c", "-c", "user.name=t", "commit", "-qm", "init")
    path_work = tmp_path / "work"
    _git_in(tmp_path, "clone", "-q", str(path_src), str(path_work))
    _git_in(path_work, "checkout", "-q", "-b", "feat/x")
    return path_work


def _run_gate(path_repo: Path, *, dict_env: dict) -> subprocess.CompletedProcess:
    """Run the gate script as a subprocess in ``path_repo`` with CI markers scrubbed.

    Parameters
    ----------
    path_repo : pathlib.Path
        Working directory of the run.
    dict_env : dict
        Extra environment entries layered over a copy of ``os.environ`` minus the CI markers.

    Returns
    -------
    subprocess.CompletedProcess
        The finished run, stdout and stderr captured.
    """
    return subprocess.run(  # noqa: S603
        [sys.executable, str(_BIN / "check_gate_integrity.py"), "--root", "."],
        cwd=path_repo,
        env={**_hermetic_env(), **dict_env},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_first_commit_on_a_branch_that_weakens_a_gate_fails(path_first_commit: Path) -> None:
    """HEAD equal to the merge-base must still diff the staged change (blueprintx#1333)."""
    (path_first_commit / "ruff.toml").write_text('[lint]\nselect = ["E", "F"]\n', encoding="utf-8")
    _git_in(path_first_commit, "add", "ruff.toml")

    cls_run = _run_gate(path_first_commit, dict_env={})

    str_out = cls_run.stdout + cls_run.stderr

    assert (cls_run.returncode, "rule 'S' removed" in str_out) == (1, True), str_out


@pytest.mark.parametrize("dict_env", [{}, {"CI": "true", "GITHUB_ACTIONS": "true"}])
def test_clean_first_commit_branch_passes(path_first_commit: Path, *, dict_env: dict) -> None:
    """A clean branch whose HEAD is the merge-base exits 0, locally and under CI."""
    assert _run_gate(path_first_commit, dict_env=dict_env).returncode == 0


@pytest.mark.parametrize("dict_env", [{}, {"CI": "true", "GITHUB_ACTIONS": "true"}])
def test_clean_checkout_of_the_default_branch_passes(
    path_first_commit: Path, *, dict_env: dict
) -> None:
    """A clean checkout of the default branch itself exits 0, locally and under CI."""
    _git_in(path_first_commit, "checkout", "-q", "main")

    assert _run_gate(path_first_commit, dict_env=dict_env).returncode == 0


def test_workflow_new_side_merge_key_under_jobs_says_the_gate_refuses_it() -> None:
    """Valid YAML the gate refuses is named as such, not reported as a parse failure."""
    str_new = "x: &a\n  gate:\n    runs-on: u\njobs:\n  <<: *a\n"

    assert gate.workflow_problems("jobs:\n  keep:\n", str_new=str_new, str_shown="w") == [
        "w: workflow uses YAML the gate refuses to read, so its jobs cannot be compared"
    ]


def test_workflow_read_reports_a_nul_character_instead_of_crashing() -> None:
    """PyYAML's reader rejects U+0000 before parsing, which must read as an unparsed file."""
    assert gate.read_workflow("# a\x00b\njobs:\n  k:\n    runs-on: u\n") is None


def test_workflow_concurrency_group_with_a_multiline_expression_matches_the_inline_one() -> None:
    """GitHub ignores newlines between expression tokens, so both spellings name one group."""
    dict_inline = {"name": "w", "concurrency": {"group": "ci-${{ github.ref }}"}}
    dict_split = {"name": "w", "concurrency": {"group": "ci-${{ github.\n   ref }}"}}

    assert gate.workflow_concurrency(dict_split) == gate.workflow_concurrency(dict_inline)


_LIST_LEAF_COMPARISONS: list = []


class _CountedLeaf(str):
    """A string that records each equality test made against it."""

    def __eq__(self, cls_other: object) -> bool:
        _LIST_LEAF_COMPARISONS.append(1)
        return str.__eq__(self, cls_other)

    def __hash__(self) -> int:
        return str.__hash__(self)


def _shared_chain(int_levels: int) -> list:
    """Build a value whose every level holds the previous one twice, as aliases do."""
    return functools.reduce(
        lambda list_node, _int_level: [list_node, list_node],
        range(int_levels),
        [_CountedLeaf("x")],
    )


def test_values_equal_compares_each_shared_node_pair_once() -> None:
    """Plain ``==`` on two separate 12-level chains tests the leaf 4096 times."""
    _LIST_LEAF_COMPARISONS.clear()
    gate.values_equal(_shared_chain(12), cls_right=_shared_chain(12))

    assert 0 < len(_LIST_LEAF_COMPARISONS) < 50


def test_consume_candidate_does_not_compare_earlier_candidates() -> None:
    """Removing the match by equality would test the earlier candidate's chain 4096 times."""
    tuple_first = (_shared_chain(12), {"runs-on": "a"}, "")
    tuple_match = (_shared_chain(12), {"runs-on": "b"}, "")
    list_candidates = [tuple_first, tuple_match]
    _LIST_LEAF_COMPARISONS.clear()
    gate.consume_candidate(list_candidates, tuple_found=tuple_match)

    assert not _LIST_LEAF_COMPARISONS


def test_consume_candidate_removes_only_the_match() -> None:
    """An equal but distinct candidate stays, so one new job still covers one removal."""
    tuple_first = ({"a": "1"}, {}, "")
    tuple_match = ({"a": "1"}, {}, "")
    list_candidates = [tuple_first, tuple_match]
    gate.consume_candidate(list_candidates, tuple_found=tuple_match)

    assert [id(tuple_cand) for tuple_cand in list_candidates] == [id(tuple_first)]


def test_find_move_matches_headers_that_share_nodes() -> None:
    """The move comparison goes through ``values_equal``, so a long chain still matches."""
    tuple_candidate = ({"x-a": _shared_chain(60)}, {}, "")

    assert (
        gate.find_move(
            [tuple_candidate],
            tuple_pair=({"x-a": _shared_chain(60)}, {}),
            tuple_concurrency=("", ""),
        )
        == tuple_candidate
    )


def test_values_equal_tells_apart_values_that_differ_only_deep_inside() -> None:
    """The pair memo must not make unequal values equal."""
    assert not gate.values_equal({"a": [{"b": "1"}]}, cls_right={"a": [{"b": "2"}]})


@pytest.mark.parametrize(
    "str_old",
    [
        "x: &a [1]\ny: &a [2]\njobs:\n  gate:\n    runs-on: u\n",
        "jobs:\n  gate:\n    runs-on: u\n---\njobs: {}\n",
    ],
)
def test_workflow_base_with_a_composer_error_reports_instead_of_passing(str_old: str) -> None:
    """Other YAML tools accept a repeated anchor or a second document, so no free deletion."""
    assert gate.workflow_problems(str_old, str_new="jobs:\n  keep:\n", str_shown="w") == [
        "w: base workflow uses YAML the gate refuses to read, so its jobs are unchecked"
    ]


def test_workflow_new_side_too_deep_to_compose_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """A file the composer cannot walk is not called unparseable or refused YAML."""
    monkeypatch.setattr(gate, "read_workflow", lambda _str_text: None)
    monkeypatch.setattr(gate.yaml, "compose", _raise_recursion)

    assert gate.workflow_problems("jobs:\n", str_new="jobs:\n", str_shown="w") == [
        "w: workflow nests too deeply for the gate, so its jobs cannot be compared"
    ]


def test_workflow_base_with_an_undefined_alias_reports_nothing() -> None:
    """GitHub refuses an undefined alias too, so repairing such a base weakens nothing."""
    str_old = "jobs:\n  gate:\n    steps: *missing\n"

    assert gate.workflow_problems(str_old, str_new="jobs:\n  keep:\n", str_shown="w") == []


@pytest.mark.parametrize(("cls_left", "cls_right"), [(1, True), (1, 1.0)])
def test_values_equal_tells_apart_equal_values_of_different_types(
    *, cls_left: object, cls_right: object
) -> None:
    """Python equates ``1``, ``1.0`` and ``True``; a typed read must not."""
    assert not gate.values_equal([cls_left], cls_right=[cls_right])


def test_workflow_blob_that_is_not_utf8_is_a_finding_not_a_skip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``show`` returns ``None`` for an undecodable blob, which must not read as absent."""
    monkeypatch.setattr(gate, "show", lambda _str_ref, *, str_path: None)
    monkeypatch.setattr(gate, "blob_exists", lambda _str_ref, *, str_path: True)

    assert gate.collect_problems([("M", _STR_SOURCE)], str_base="base") == [
        f"{_STR_SOURCE}: workflow is not valid UTF-8, so its jobs cannot be compared"
    ]


@pytest.mark.parametrize(
    "str_path",
    [
        "bin/check_thing.py",
        "bin/ci/check_thing.sh",
        ".pre-commit-config.yaml",
        "ruff.toml",
        "enable_repo_rules.sh",
        "tests/unit/test_thing.py",
    ],
)
def test_modified_analysed_file_that_is_not_utf8_is_a_finding(
    monkeypatch: pytest.MonkeyPatch, *, str_path: str
) -> None:
    """A gate script, config or test that cannot be decoded is reported, never skipped."""
    monkeypatch.setattr(gate, "show", lambda _str_ref, *, str_path: None)
    monkeypatch.setattr(gate, "blob_exists", lambda _str_ref, *, str_path: True)

    assert gate.collect_problems([("M", str_path)], str_base="base") == [
        f"{str_path}: file is not valid UTF-8, so the gate cannot compare it with its base"
    ]


@pytest.mark.parametrize("str_path", ["bin/check_thing.py", ".pre-commit-config.yaml"])
def test_added_analysed_file_that_is_not_utf8_is_not_a_finding(
    monkeypatch: pytest.MonkeyPatch, *, str_path: str
) -> None:
    """An added file has no base to weaken, so its encoding is nothing to report."""
    monkeypatch.setattr(gate, "show", lambda _str_ref, *, str_path: None)
    monkeypatch.setattr(
        gate, "blob_exists", lambda str_ref, *, str_path: str_ref == gate.STR_INDEX_REF
    )

    assert gate.collect_problems([("A", str_path)], str_base="base") == []


def test_modified_unanalysed_file_that_is_not_utf8_is_not_a_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A binary the gate never reads (an image) stays out of scope."""
    monkeypatch.setattr(gate, "show", lambda _str_ref, *, str_path: None)
    monkeypatch.setattr(gate, "blob_exists", lambda _str_ref, *, str_path: True)

    assert gate.collect_problems([("M", "docs/logo.png")], str_base="base") == []


_LIST_ANALYSED_PATHS = [
    "bin/check_thing.py",
    "templates/python-common/bin/lint_thing.sh",
    "bin/ci/check_thing.sh",
    "templates/foo/ruff.toml",
    ".github/workflows/ci.yml",
    ".github/workflows/ci.yaml",
    "tests/unit/test_thing.py",
    "tests/integration/test_thing.py",
    *gate._DICT_DISPATCH,
]
_LIST_UNANALYSED_PATHS = [
    "docs/logo.png",
    "README.md",
    "src/thing.py",
    "tests/fixtures/test_thing.py",
    "bin/helper.py",
]


@pytest.mark.parametrize("str_path", _LIST_ANALYSED_PATHS)
def test_is_analysed_path_accepts_a_path_the_gate_reads(str_path: str) -> None:
    """Every gate script, watched config (at any depth), workflow and test counts as analysed."""
    assert gate.is_analysed_path(str_path)


@pytest.mark.parametrize("str_path", _LIST_UNANALYSED_PATHS)
def test_is_analysed_path_rejects_a_path_the_gate_never_reads(str_path: str) -> None:
    """An image, a README, source and a stray script are out of scope."""
    assert not gate.is_analysed_path(str_path)


@pytest.mark.parametrize("str_path", [*_LIST_ANALYSED_PATHS, *_LIST_UNANALYSED_PATHS])
def test_is_analysed_path_agrees_with_deletion_problems_when_the_test_stem_is_touched(
    str_path: str,
) -> None:
    """Gate scripts, watched configs and workflows route alike; a test is checked with its stem."""
    set_stems = frozenset({gate.test_module_stem(str_path)})

    assert bool(gate.deletion_problems([("D", str_path)], set_touched_stems=set_stems)) == (
        gate.is_analysed_path(str_path)
    )


def test_deleted_analysed_file_gets_only_the_deletion_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deleted path is read by ``deletion_problems`` alone; no encoding finding is added."""
    monkeypatch.setattr(gate, "show", lambda _str_ref, *, str_path: None)
    monkeypatch.setattr(gate, "blob_exists", lambda _str_ref, *, str_path: True)

    assert gate.collect_problems([("D", "bin/check_thing.py")], str_base="base") == [
        "bin/check_thing.py: quality-check script deleted"
    ]


def test_gate_script_renamed_and_reencoded_is_reported_as_deleted(
    tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Renames read as delete plus add, so a rename plus re-encode cannot dodge the gate."""
    _git_in(tmp_path, "init", "-q", "--initial-branch=main")
    _git_in(tmp_path, "config", "user.email", "t@example.com")
    _git_in(tmp_path, "config", "user.name", "t")
    _git_in(tmp_path, "config", "commit.gpgsign", "false")
    _git_in(tmp_path, "config", "core.hooksPath", os.devnull)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/check_x.py").write_bytes(b"assert True\n")
    _git_in(tmp_path, "add", "bin/check_x.py")
    _git_in(tmp_path, "commit", "-q", "-m", "seed")
    str_base = _git_in(tmp_path, "rev-parse", "main")
    _git_in(tmp_path, "mv", "bin/check_x.py", "bin/check_y.py")
    (tmp_path / "bin/check_y.py").write_bytes(b"pass  # \xe9\n")
    _git_in(tmp_path, "add", "bin/check_y.py")
    monkeypatch.chdir(tmp_path)

    assert "bin/check_x.py: quality-check script deleted" in gate.collect_problems(
        gate.changed_paths(str_base), str_base=str_base
    )


def test_decodable_analysed_file_is_not_a_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    """``undecodable_problems`` re-checks decodability, so a readable file never reports."""
    monkeypatch.setattr(gate, "show", lambda _str_ref, *, str_path: "assert True\n")
    monkeypatch.setattr(gate, "blob_exists", lambda _str_ref, *, str_path: True)

    assert gate.undecodable_problems("bin/check_thing.py", str_base="base") == []


@pytest.mark.parametrize("str_side", ["index", "base"])
def test_analysed_file_undecodable_on_one_side_only_is_a_finding(
    monkeypatch: pytest.MonkeyPatch, *, str_side: str
) -> None:
    """Either ref being undecodable is enough, whichever side it is."""
    str_bad = gate.STR_INDEX_REF if str_side == "index" else "base"
    monkeypatch.setattr(
        gate, "show", lambda str_ref, *, str_path: None if str_ref == str_bad else "ok\n"
    )
    monkeypatch.setattr(gate, "blob_exists", lambda _str_ref, *, str_path: True)

    assert gate.undecodable_problems("bin/check_thing.py", str_base="base") != []


def test_workflow_added_without_a_base_blob_is_not_a_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A path with no blob at the base is an addition, which has no jobs to lose."""
    monkeypatch.setattr(gate, "show", lambda _str_ref, *, str_path: None)
    monkeypatch.setattr(
        gate, "blob_exists", lambda str_ref, *, str_path: str_ref == gate.STR_INDEX_REF
    )

    assert gate.collect_problems([("A", _STR_SOURCE)], str_base="base") == []
