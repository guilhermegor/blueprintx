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
