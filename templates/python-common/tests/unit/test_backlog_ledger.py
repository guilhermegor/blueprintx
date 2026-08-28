"""Unit tests for the work-ledger gate's pure logic (offline; no git, no network).

Only the path-classification and ledger-validation seams are tested here — the git plumbing
(`merge-base`, `diff --cached`) belongs to an integration test, not a unit one.
"""

import importlib.util
import json
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


gate = _load("pr_gate")
ledger = _load("check_backlog_ledger")
gate_integrity = _load("check_gate_integrity")


def test_ledger_required_for_src_and_ci() -> None:
	"""A branch touching src/ or ci paths must carry a ledger."""
	assert ledger.needs_ledger(["src/model/loader.py"], gate) is True
	assert ledger.needs_ledger(["bin/venv.sh"], gate) is True


def test_ledger_not_required_for_routine_classes() -> None:
	"""docs/deps/tests-only branches are routine — a ledger there would be noise."""
	assert ledger.needs_ledger(["docs/usage.md"], gate) is False
	assert ledger.needs_ledger(["poetry.lock"], gate) is False
	assert ledger.needs_ledger(["tests/unit/test_x.py"], gate) is False


def test_membership_is_asked_per_path_not_over_the_whole_list() -> None:
	"""The regression this guards: a mixed branch must NOT escape the ledger requirement.

	``classify_risk`` returns the single most-dangerous class and ranks ``tests`` above ``ci``, so
	a branch touching both ``bin/`` and ``tests/`` collapses to ``tests`` — which is not a ledger
	class. Asking per path is what keeps the requirement honest.
	"""
	list_mixed = ["bin/venv.sh", "tests/unit/test_x.py"]
	assert gate.classify_risk(list_mixed) == "tests"  # whole-list view would escape...
	assert ledger.needs_ledger(list_mixed, gate) is True  # ...per-path view catches it


def test_a_valid_ledger_satisfies_the_branch() -> None:
	"""A correctly named ledger clears the requirement."""
	assert (
		ledger.find_ledger_problems(["src/a.py", "docs/backlog/my-topic_20260720_101500.md"]) == []
	)


def test_missing_ledger_is_reported() -> None:
	"""A src-touching branch with no ledger fails, and the message says what to create."""
	list_problems = ledger.find_ledger_problems(["src/a.py"])
	assert list_problems
	assert "docs/backlog" in list_problems[0]


def test_ledger_name_must_be_kebab_plus_timestamp() -> None:
	"""A misnamed ledger is rejected — the timestamped kebab name is the convention."""
	list_problems = ledger.find_ledger_problems(["src/a.py", "docs/backlog/BadName.md"])
	assert list_problems
	assert "kebab" in list_problems[0]


# --------------------------
# Bot exemption (#123)
# --------------------------
#
# A gate demanding a human-authored artifact permanently blocks every bot PR that trips it.
# Both directions are tested by name: an exemption is one `return 0` away from disabling the
# gate for everyone with the suite still green, so the negative control is the real assertion.


def test_bot_login_is_exempt() -> None:
	"""GitHub's own ``[bot]`` suffix identifies the author, with no allow-list to rot."""
	assert ledger.is_bot_author("dependabot[bot]") is True
	assert ledger.is_bot_author("github-actions[bot]") is True
	assert ledger.is_bot_author("renovate[bot]") is True


def test_human_login_is_not_exempt() -> None:
	"""NEGATIVE CONTROL: the gate still fires for humans, including bot-ish names."""
	assert ledger.is_bot_author("octocat") is False
	# "bot" in the name is not the suffix — only GitHub's own marker counts.
	assert ledger.is_bot_author("robotics-team") is False
	assert ledger.is_bot_author("dependabot") is False


def test_unresolved_author_is_treated_as_human() -> None:
	"""An author that cannot be resolved must fail CLOSED, never exempt."""
	assert ledger.is_bot_author("") is False


def _write_event(path_dir: Path, dict_payload: dict) -> str:
	"""Write a GitHub event payload to disk and return its path.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory to write the payload into.
	dict_payload : dict
		The event body, e.g. ``{"pull_request": {"user": {"login": "x"}}}``.

	Returns
	-------
	str
		Path to the written JSON file.
	"""
	path_event = path_dir / "event.json"
	path_event.write_text(json.dumps(dict_payload), encoding="utf-8")
	return str(path_event)


def test_pr_author_comes_from_the_payload_never_the_actor(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""⚠️ The trap: ``GITHUB_ACTOR`` is whoever TRIGGERED the run, not the PR author.

	Keying on the actor makes the exemption die the moment a human touches the bot's PR
	(update-branch, re-run, fixup) — so the very act of unblocking it defeats the fix, and
	each retry reads as "the fix doesn't work". This pins the author as authoritative even
	when a human is the actor.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir holding the event payload.
	monkeypatch : pytest.MonkeyPatch
		Used to set the GitHub Actions environment variables.
	"""
	str_event = _write_event(tmp_path, {"pull_request": {"user": {"login": "dependabot[bot]"}}})
	monkeypatch.setenv("GITHUB_EVENT_PATH", str_event)
	monkeypatch.setenv("GITHUB_ACTOR", "a-human-who-clicked-rerun")

	assert ledger.pr_author_login() == "dependabot[bot]"


def test_human_authored_pr_is_not_exempt_even_when_a_bot_is_the_actor(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""The other direction: a bot triggering a human's PR must not exempt it."""
	str_event = _write_event(tmp_path, {"pull_request": {"user": {"login": "octocat"}}})
	monkeypatch.setenv("GITHUB_EVENT_PATH", str_event)
	monkeypatch.setenv("GITHUB_ACTOR", "github-actions[bot]")

	assert ledger.is_bot_author(ledger.pr_author_login()) is False


def test_a_push_run_has_no_pr_author_and_stays_enforced(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Inside a workflow run the payload is the ONLY authority — never the actor.

	A push payload carries no ``pull_request`` object, so there is no author, and the gate must
	stay enforced rather than fall back to a possibly-bot actor.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir holding the event payload.
	monkeypatch : pytest.MonkeyPatch
		Used to set the GitHub Actions environment variables.
	"""
	str_event = _write_event(tmp_path, {"ref": "refs/heads/main"})
	monkeypatch.setenv("GITHUB_EVENT_PATH", str_event)
	monkeypatch.setenv("GITHUB_ACTOR", "dependabot[bot]")

	assert ledger.is_bot_author(ledger.pr_author_login()) is False


def test_a_missing_event_file_exempts_nobody(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""GITHUB_EVENT_PATH set but the file absent must fail CLOSED, not fall back to the actor.

	This is the narrow hole an earlier revision left: the missing-file branch skipped the
	payload entirely and returned ``GITHUB_ACTOR``, so a bot re-running or auto-merging a
	human's PR would have exempted it — the exact defect keying on the author exists to avoid.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir; the payload path deliberately points at nothing.
	monkeypatch : pytest.MonkeyPatch
		Used to set the GitHub Actions environment variables.
	"""
	monkeypatch.setenv("GITHUB_EVENT_PATH", str(tmp_path / "does_not_exist.json"))
	monkeypatch.setenv("GITHUB_ACTOR", "dependabot[bot]")

	assert ledger.pr_author_login() == ""
	assert ledger.is_bot_author(ledger.pr_author_login()) is False


def test_unreadable_payload_exempts_nobody(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A corrupt payload must fail closed rather than exempt the whole run."""
	path_event = tmp_path / "event.json"
	path_event.write_text("{not json", encoding="utf-8")
	monkeypatch.setenv("GITHUB_EVENT_PATH", str(path_event))
	monkeypatch.delenv("GITHUB_ACTOR", raising=False)

	assert ledger.is_bot_author(ledger.pr_author_login()) is False


def test_local_run_has_no_author_and_stays_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Off CI (a local pre-commit) nothing is exempt — the gate behaves exactly as before."""
	monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
	monkeypatch.delenv("GITHUB_ACTOR", raising=False)

	assert ledger.is_bot_author(ledger.pr_author_login()) is False


# --------------------------
# Gate integrity (#309) — pure logic only, offline (no git; see the module docstring for why
# check_backlog_ledger's own tests above stop at the same boundary).
# --------------------------

_RUFF_BASE = """
select = [
    "E",
    "F",
    "S",
]
ignore = [
    "D206",
]
exclude = [
    ".venv",
]

[lint.per-file-ignores]
"bin/*.py" = [
    "ERA001",
]
"""


def test_hook_removal_is_detected() -> None:
	"""The should-fail witness: a hook present at the base and gone now is reported by name."""
	str_old = "repos:\n  - hooks:\n      - id: check-complexity\n      - id: ruff\n"
	str_new = "repos:\n  - hooks:\n      - id: ruff\n"
	list_problems = gate_integrity.precommit_problems(str_old, str_new, ".pre-commit-config.yaml")
	assert list_problems == [".pre-commit-config.yaml: pre-commit hook 'check-complexity' removed"]


def test_hook_reorder_is_not_a_removal() -> None:
	"""NEGATIVE CONTROL: moving a hook must not read as deleting and re-adding it."""
	str_old = "- id: a\n- id: b\n"
	str_new = "- id: b\n- id: a\n"
	assert gate_integrity.precommit_problems(str_old, str_new, "x.yaml") == []


def test_ruff_rule_removed_from_select() -> None:
	"""A rule dropped from [lint] select is a weakening."""
	str_new = _RUFF_BASE.replace('    "S",\n', "")
	list_problems = gate_integrity.ruff_toml_problems(_RUFF_BASE, str_new, "ruff.toml")
	assert "ruff.toml: rule 'S' removed from [lint] select" in list_problems


def test_ruff_rule_added_to_ignore() -> None:
	"""A rule added to [lint] ignore is a weakening — the rule-level surface PR #306 avoided."""
	str_new = _RUFF_BASE.replace('    "D206",\n', '    "D206",\n    "S608",\n')
	list_problems = gate_integrity.ruff_toml_problems(_RUFF_BASE, str_new, "ruff.toml")
	assert "ruff.toml: rule 'S608' added to [lint] ignore" in list_problems


def test_ruff_exclude_path_added() -> None:
	"""Re-excluding a tree that was being checked is a weakening."""
	str_new = _RUFF_BASE.replace('    ".venv",\n', '    ".venv",\n    "src/chassis",\n')
	list_problems = gate_integrity.ruff_toml_problems(_RUFF_BASE, str_new, "ruff.toml")
	assert "ruff.toml: path 'src/chassis' added to exclude" in list_problems


def test_ruff_per_file_ignore_added_is_rule_level_and_flagged() -> None:
	"""A per-file-ignore is inherently rule-level for that glob — exactly what #306 avoided."""
	str_old_pfi = '"bin/*.py" = [\n    "ERA001",\n]'
	str_new_pfi = '"bin/*.py" = [\n    "ERA001",\n    "S608",\n]'
	str_new = _RUFF_BASE.replace(str_old_pfi, str_new_pfi)
	list_problems = gate_integrity.ruff_toml_problems(_RUFF_BASE, str_new, "ruff.toml")
	assert "ruff.toml: rule 'S608' added to per-file-ignores['bin/*.py']" in list_problems


def test_ruff_toml_with_no_changes_reports_nothing() -> None:
	"""NEGATIVE CONTROL: an untouched (or purely additive-to-select) file passes clean."""
	str_new = _RUFF_BASE.replace('    "S",\n', '    "S",\n    "B",\n')  # rule ADDED to select
	assert gate_integrity.ruff_toml_problems(_RUFF_BASE, str_new, "ruff.toml") == []


_MYPY_BASE = "[mypy]\nexclude = (?x)(^utils/typing/|_internal/utils/typing/)\n"


def test_mypy_exclude_path_added() -> None:
	"""A new alternative added to [mypy] exclude is a weakening."""
	str_new = _MYPY_BASE.rstrip() + "|^chassis/)\n"
	list_problems = gate_integrity.mypy_ini_problems(_MYPY_BASE, str_new, "mypy.ini")
	assert any("chassis" in str_problem for str_problem in list_problems)


def test_mypy_ignore_errors_section_added() -> None:
	"""A new [mypy-X] ignore_errors = True section re-hides a tree, same as blueprintx#190."""
	str_new = _MYPY_BASE + "\n[mypy-chassis.*]\nignore_errors = True\n"
	list_problems = gate_integrity.mypy_ini_problems(_MYPY_BASE, str_new, "mypy.ini")
	assert "mypy.ini: [mypy-chassis.*] ignore_errors = True added" in list_problems


_PYTEST_BASE = (
	"[pytest]\n"
	"filterwarnings =\n"
	"    error:Missing docstring for parameter.*:\n"
	"    ignore::DeprecationWarning:PIL\n"
)


def test_pytest_filterwarnings_escalation_removed() -> None:
	"""Dropping an error: escalation quietly downgrades a docstring check to a warning."""
	str_new = "[pytest]\nfilterwarnings =\n    ignore::DeprecationWarning:PIL\n"
	list_problems = gate_integrity.pytest_ini_problems(_PYTEST_BASE, str_new, "pytest.ini")
	assert list_problems == [
		"pytest.ini: filterwarnings escalation 'error:Missing docstring for parameter.*:' removed"
	]


def test_pytest_ignore_entries_are_not_escalations() -> None:
	"""NEGATIVE CONTROL: removing an `ignore:` line is routine noise-tuning, not a weakening."""
	str_new = _PYTEST_BASE.replace("    ignore::DeprecationWarning:PIL\n", "")
	assert gate_integrity.pytest_ini_problems(_PYTEST_BASE, str_new, "pytest.ini") == []


def test_workflow_job_removed() -> None:
	"""A job dropped from a workflow's jobs: block is a check silently switched off."""
	str_old = "jobs:\n  lint-shell:\n    runs-on: x\n  complexity:\n    runs-on: x\n"
	str_new = "jobs:\n  complexity:\n    runs-on: x\n"
	list_problems = gate_integrity.workflow_problems(str_old, str_new, "tests.yaml")
	assert list_problems == ["tests.yaml: workflow job 'lint-shell' removed"]


def test_required_status_check_removed() -> None:
	"""A context dropped from REQUIRED_CHECKS is a weakening of the branch-protection ruleset."""
	str_old = 'REQUIRED_CHECKS=(\n  "Review threads answered"\n  "lint-shell"\n)\n'
	str_new = 'REQUIRED_CHECKS=(\n  "lint-shell"\n)\n'
	list_problems = gate_integrity.required_checks_problems(
		str_old, str_new, "enable_repo_rules.sh"
	)
	assert list_problems == [
		"enable_repo_rules.sh: required status check 'Review threads answered' removed"
	]


def test_deletion_flags_a_bin_ci_script() -> None:
	"""A quality-check script deleted outright is the bluntest form of weakening."""
	list_changed = [("D", "bin/ci/check_actions.sh"), ("M", "README.md")]
	list_problems = gate_integrity.deletion_problems(list_changed)
	assert list_problems == ["bin/ci/check_actions.sh: quality-check script deleted"]


def test_deletion_flags_a_bin_check_script() -> None:
	"""The template-side equivalent: bin/check_*.py / bin/lint_*.sh, not just bin/ci/."""
	list_changed = [("D", "bin/check_typing.py")]
	assert gate_integrity.deletion_problems(list_changed) == [
		"bin/check_typing.py: quality-check script deleted"
	]


def test_ordinary_source_file_is_not_dispatched() -> None:
	"""⚠️ THE SHOULD-PASS WITNESS.

	This gate reads only the watched config basenames — an ordinary source file (where a
	`# noqa: E501` line-level suppression would live) is structurally invisible to it, by
	construction rather than by exception list.
	"""
	assert Path("src/model/foo.py").name not in gate_integrity._DICT_DISPATCH
	assert gate_integrity.RE_WORKFLOW_PATH.search("src/model/foo.py") is None


def test_justification_reason_reads_the_pr_body(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A `gate-change-ok: <reason>` line in the PR body satisfies the escape hatch."""
	str_event = _write_event(
		tmp_path, {"pull_request": {"body": "Removes a duplicate hook.\n\ngate-change-ok: dup"}}
	)
	monkeypatch.setenv("GITHUB_EVENT_PATH", str_event)
	monkeypatch.setattr(gate_integrity, "_git", lambda _args: "")

	assert gate_integrity.justification_reason("deadbeef") == "dup"


def test_bare_marker_with_no_reason_does_not_satisfy() -> None:
	"""The reason is REQUIRED, matching `# complexity-ok: <reason>` elsewhere in this repo."""
	assert gate_integrity.RE_JUSTIFICATION.search("gate-change-ok:\n") is None
	assert gate_integrity.RE_JUSTIFICATION.search("gate-change-ok:   \n") is None
