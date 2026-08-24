#!/usr/bin/env python3
"""Re-ask for a review on any open PR whose reviewer was RATE LIMITED, not absent.

The review gate (``bin/check_review_threads.py``) correctly fails a PR that no declared
reviewer has looked at. But one cause of that state is transient and self-clearing: the
reviewer answered *"Review rate limited"* and will accept the request again in a few
minutes. Measured upstream over 112 PRs: **19 hit a rate limit and 18 of them were reviewed
in the end** — so a rate limit is a DELAY, not an unavailability.

That single number decides the design. An unavailability would need an escape hatch in the
gate; a delay needs the *asking* automated. So this script leaves the gate's verdict exactly
as strict as it was and removes the only part a human was doing by hand: waiting for the
window to pass, then re-typing the request. The PR then goes green on its own — the stale red
runs are cleared by ``bin/rerun_stale_gate_runs.sh`` (blueprintx#263), which already runs
from the passing gate.

⚠️ WHY A RATE-LIMIT DETECTOR IS SOUND HERE WHEN THE "ALREADY REVIEWED" ONE WAS NOT.
blueprintx#259 established that a reviewer notice's TEXT cannot decide a verdict: the
"already reviewed / does not re-review" sentence is a standing footnote about the product,
appended to every outcome. Re-measured over 132 notices before writing this file, and the
two phrases behave oppositely:

    phrase              performed   failed   not-completed
    "already reviewed"      24/25      3/3           55/59   <- useless, every outcome
    "rate limit"             0/25      0/3           57/59   <- clean separation

So keying on the rate-limit wording really does isolate one outcome. It is used here anyway
in the safest possible position: this script's only action is to ASK FOR A REVIEW. A false
positive costs one redundant request; it can never pass a gate or merge anything. Nothing in
this file is allowed to become an input to a verdict — that is what #259 forbids.

⚠️ IT NEEDS THE USER PAT, NOT ``GITHUB_TOKEN`` — same measurement as
``.github/workflows/coderabbit_trigger.yaml``. CodeRabbit IGNORES bot-authored comments: a
comment posted with ``GITHUB_TOKEN`` is authored by ``github-actions[bot]`` and is silently
dropped. Only a user PAT produces a comment the reviewer answers.

⚠️ IT IS A JANITOR, SO IT EXITS 0 EVEN WHEN IT CANNOT DO ITS JOB — see the section in
``bin/CLAUDE.md``. If this fails, the PR stays blocked behind a red gate, which is the status
quo and fully visible; nothing is hidden. Failing the step would only add a red run to a
board whose point is to tell a human where to look.
"""

from __future__ import annotations

from collections.abc import Callable
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import types


# The marker makes our own request recognisable, so a scheduled run asks ONCE per window
# instead of every tick. It is an HTML comment, so it renders as nothing.
_STR_MARKER = "<!-- retry-rate-limited-review -->"

# The command, not a plain `review`: an incremental reviewer answers "already reviewed" for
# commits it has seen, and only the full form disregards that. Same reasoning as the gate's
# own remedy text — keep the two spellings identical.
_STR_REQUEST = f"@coderabbitai full review\n\n{_STR_MARKER}"

# Deliberately broad: any spelling of the reviewer saying it is throttled. Being generous here
# is the safe direction, because the only consequence is one extra review request.
_RE_RATE_LIMIT = re.compile(r"rate[\s-]?limit", re.IGNORECASE)


def _gh_json(list_args: list[str]) -> object:
	"""Run a ``gh`` command and parse its stdout as JSON, or return ``None`` on any failure.

	Parameters
	----------
	list_args : list of str
		Arguments after ``gh``.

	Returns
	-------
	object
		The parsed JSON, or ``None`` when the call or the parse failed.
	"""
	# A constant, trusted argv assembled from this file's own literals plus repo/PR
	# identifiers supplied by the workflow — no shell, so nothing to quote.
	str_gh = shutil.which("gh") or "gh"
	cls_done = subprocess.run(  # noqa: S603
		[str_gh, *list_args], capture_output=True, text=True, check=False
	)
	if cls_done.returncode != 0:
		print(f"::warning::gh {' '.join(list_args[:2])} failed: {cls_done.stderr.strip()[:200]}")
		return None
	try:
		return json.loads(cls_done.stdout or "null")
	except json.JSONDecodeError:
		print(f"::warning::gh {' '.join(list_args[:2])} returned unparsable JSON")
		return None


def load_gate(path_bin: pathlib.Path) -> types.ModuleType | None:
	"""Import ``check_review_threads.py`` by path, to reuse its roster and review helpers.

	The gate is a script rather than a package, so it is loaded the way
	``bin/check_backlog_ledger.py`` already loads ``bin/pr_gate.py``. Reusing it is the point:
	the roster format, the ``[bot]`` login normalisation and "did anyone review THIS commit"
	must not be re-implemented here, or the two files answer the same question differently.

	Parameters
	----------
	path_bin : pathlib.Path
		The ``bin/`` directory holding both scripts.

	Returns
	-------
	types.ModuleType or None
		The imported module, or ``None`` when it cannot be loaded.
	"""
	path_gate = path_bin / "check_review_threads.py"
	cls_spec = importlib.util.spec_from_file_location("check_review_threads", path_gate)
	if cls_spec is None or cls_spec.loader is None:
		print(f"::warning::cannot load the review gate from {path_gate}")
		return None
	cls_module = importlib.util.module_from_spec(cls_spec)
	cls_spec.loader.exec_module(cls_module)
	return cls_module


# ⚠️ NOT `summarise_reviewer_notice` — that helper's own docstring says DISPLAY ONLY, and it
# truncates to 200 characters after stripping markup, which can cut the very sentence being
# matched. Deciding anything from a display string is how a truncation becomes a logic bug.
def newest_roster_notice(
	list_comments: list[dict], set_roster: set[str], fn_norm: Callable[[str], str]
) -> str:
	"""Return the newest roster-authored comment body, untruncated.

	Parameters
	----------
	list_comments : list of dict
		The PR's issue comments, oldest first.
	set_roster : set of str
		Already-normalised reviewer logins.
	fn_norm : Callable[[str], str]
		The gate's ``normalise_login``.

	Returns
	-------
	str
		The newest roster comment's body, or ``""`` when the roster has said nothing.
	"""
	for dict_comment in reversed(list_comments):
		if fn_norm((dict_comment.get("author") or {}).get("login") or "") in set_roster:
			return dict_comment.get("body") or ""
	return ""


# Walking NEWEST-FIRST and stopping at whichever comes first is what makes a scheduled run
# idempotent without reading a single timestamp: our marker above the notice means we have
# already asked since it was posted, so asking again would just be noise every tick.
def already_asked_since_notice(
	list_comments: list[dict], set_roster: set[str], fn_norm: Callable[[str], str]
) -> bool:
	"""Return whether our request is newer than the reviewer's newest rate-limit notice.

	Parameters
	----------
	list_comments : list of dict
		The PR's issue comments, oldest first.
	set_roster : set of str
		Already-normalised reviewer logins.
	fn_norm : Callable[[str], str]
		The gate's ``normalise_login``.

	Returns
	-------
	bool
		``True`` when a marker comment appears after the newest roster notice.
	"""
	for dict_comment in reversed(list_comments):
		str_body = dict_comment.get("body") or ""
		if _STR_MARKER in str_body:
			return True
		if fn_norm((dict_comment.get("author") or {}).get("login") or "") in set_roster:
			return False
	return False


def pr_needs_retry(dict_pr: dict, set_reviewers: set[str], cls_gate: types.ModuleType) -> bool:
	"""Return whether this PR is waiting on a rate-limited reviewer and should be re-asked.

	Parameters
	----------
	dict_pr : dict
		The ``pullRequest`` node from the gate's own query.
	set_reviewers : set of str
		Logins that can actually submit a review.
	cls_gate : types.ModuleType
		The imported gate module.

	Returns
	-------
	bool
		``True`` when nothing has reviewed the head commit and the reviewer's newest word is
		a rate limit that we have not already answered.
	"""
	list_reviews = ((dict_pr.get("reviews") or {}).get("nodes")) or []
	str_head = dict_pr.get("headRefOid") or ""
	if cls_gate.reviewers_who_reported(list_reviews, set_reviewers, str_head):
		return False

	list_comments = ((dict_pr.get("comments") or {}).get("nodes")) or []
	str_notice = newest_roster_notice(list_comments, set_reviewers, cls_gate.normalise_login)
	if not _RE_RATE_LIMIT.search(str_notice):
		return False

	return not already_asked_since_notice(list_comments, set_reviewers, cls_gate.normalise_login)


def request_review(str_repo: str, int_number: int) -> bool:
	"""Post the full-review request on one PR.

	Parameters
	----------
	str_repo : str
		``owner/repo``.
	int_number : int
		The PR number.

	Returns
	-------
	bool
		``True`` when the comment was posted.
	"""
	dict_posted = _gh_json(
		[
			"api",
			f"repos/{str_repo}/issues/{int_number}/comments",
			"-f",
			f"body={_STR_REQUEST}",
			"--jq",
			"{login: .user.login, type: .user.type}",
		]
	)
	if not isinstance(dict_posted, dict):
		print(f"::warning::could not request a review on #{int_number}")
		return False

	# The author TYPE is the whole point: a `Bot` comment is silently ignored by the reviewer,
	# so posting one and reporting success would be a no-op wearing a success message.
	if dict_posted.get("type") == "Bot":
		print(
			f"::warning::the request on #{int_number} was authored by "
			f"{dict_posted.get('login')} [Bot], which the reviewer IGNORES — set "
			"GH_PAT_REVIEW_TRIGGER to a user PAT (see coderabbit_trigger)."
		)
		return False

	print(f"requested a full review on #{int_number} as {dict_posted.get('login')}")
	return True


def main() -> int:
	"""Re-ask for a review on every open PR whose reviewer is rate limited.

	Returns
	-------
	int
		Always ``0`` — this is a janitor, and failing the step would add noise to the very
		signal it exists to clear. Problems are reported as workflow warnings.
	"""
	str_repo = os.environ.get("GITHUB_REPOSITORY", "")
	if not str_repo:
		print("::warning::GITHUB_REPOSITORY is unset — nothing to do.")
		return 0

	path_bin = pathlib.Path(__file__).resolve().parent
	cls_gate = load_gate(path_bin)
	if cls_gate is None:
		return 0

	dict_roster = cls_gate.load_roster(pathlib.Path.cwd())
	set_reviewers = cls_gate.reviewer_logins(dict_roster)
	if not set_reviewers:
		print("no reviewer in the roster can submit a review — nothing to re-ask.")
		return 0

	list_open = _gh_json(
		["api", f"repos/{str_repo}/pulls?state=open&per_page=100", "--jq", "[.[].number]"]
	)
	if not isinstance(list_open, list):
		return 0

	str_owner, _, str_name = str_repo.partition("/")
	int_asked = 0
	for int_number in list_open:
		dict_pr = cls_gate.fetch_pull_request(str_owner, str_name, int(int_number))
		if pr_needs_retry(dict_pr, set_reviewers, cls_gate) and request_review(
			str_repo, int(int_number)
		):
			int_asked += 1

	print(f"open PRs checked: {len(list_open)}; review re-requested on {int_asked}.")
	return 0


if __name__ == "__main__":
	# Windows' stdout defaults to cp1252 and cannot encode the glyphs this family of scripts
	# prints; same seam fix as the gate itself.
	for cls_stream in (sys.stdout, sys.stderr):
		if hasattr(cls_stream, "reconfigure"):
			cls_stream.reconfigure(encoding="utf-8", errors="replace")

	sys.exit(main())
