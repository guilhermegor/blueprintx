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
from datetime import datetime, timedelta, timezone
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

# Comfortably above the longest window measured on this repo (10-25 minutes), because the
# costs are asymmetric: asking early buys one declined request and one more ack comment,
# while asking late only delays a PR that is already waiting. Prefer the quiet error.
_INT_COOLDOWN_MIN = 30


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
		Normalised comments (``login``/``body``/``created_at``), oldest first.
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
		if fn_norm(dict_comment.get("login") or "") in set_roster:
			return dict_comment.get("body") or ""
	return ""


# 🔴 A COOLDOWN, NOT AN ORDERING TEST — AND THE ORDERING VERSION SHIPPED A LOOP.
#
# The first implementation asked "is our marker newer than the reviewer's newest notice?", which
# reads as obviously right and is wrong against the real system. Measured live on blueprintx#270:
#
#     23:50:41  <us>          @coderabbitai full review <!-- marker -->
#     23:50:54  coderabbitai  <auto-generated acknowledgement>      <- 13 SECONDS LATER
#     23:53:00  <us>          @coderabbitai full review <!-- marker -->   <- asked AGAIN
#
# The reviewer ACKNOWLEDGES every request within seconds, and that acknowledgement is a roster
# comment newer than our marker. So the newest-first scan always met the ack first, concluded
# "not asked yet", and asked again — every ten minutes, for ever, while the ack itself carried
# the rate-limit wording that made the outer predicate true. An unattended comment loop.
#
# ⚠️ The unit test for the ordering version PASSED, because it was written from the same mental
# model as the code: it asserted that a roster notice after our marker means a NEW window. That
# is precisely the case the reviewer's own ack occupies, so the test asserted the defect. A test
# built on the same assumption as the code is the assumption agreeing with itself, never
# evidence — only running it against the live PR distinguished them.
#
# Time cannot be confused this way. We asked recently or we did not.
def asked_recently(
	list_comments: list[dict],
	str_self_login: str,
	fn_norm: Callable[[str], str],
	dt_now: datetime,
	int_cooldown_min: int = _INT_COOLDOWN_MIN,
) -> bool:
	"""Return whether we posted a request within the cooldown window.

	Parameters
	----------
	list_comments : list of dict
		Normalised comments (``login``/``body``/``created_at``), oldest first.
	str_self_login : str
		The login the retry posts as. A marker from any other author is ignored; an empty
		value trusts no marker at all, so the worst case is asking twice.
	fn_norm : Callable[[str], str]
		The gate's ``normalise_login``.
	dt_now : datetime.datetime
		The current time, timezone-aware. Passed in rather than read, so a test states the
		moment it is testing instead of depending on the clock.
	int_cooldown_min : int, optional
		Minutes to wait between requests.

	Returns
	-------
	bool
		``True`` when our own marker comment is younger than the cooldown.
	"""
	str_self = fn_norm(str_self_login)
	if not str_self:
		return False

	for dict_comment in reversed(list_comments):
		if _STR_MARKER not in (dict_comment.get("body") or ""):
			continue
		if fn_norm(dict_comment.get("login") or "") != str_self:
			continue
		dt_posted = parse_timestamp(dict_comment.get("created_at") or "")
		if dt_posted is None:
			# An unreadable timestamp on OUR OWN marker: treat it as recent. Asking again on a
			# comment we cannot date is how the loop above started.
			return True
		return (dt_now - dt_posted) < timedelta(minutes=int_cooldown_min)
	return False


def parse_timestamp(str_stamp: str) -> datetime | None:
	"""Parse a GitHub ISO-8601 timestamp into an aware datetime.

	Parameters
	----------
	str_stamp : str
		A timestamp such as ``2026-08-24T23:50:41Z``.

	Returns
	-------
	datetime.datetime or None
		The parsed value, or ``None`` when it cannot be read.
	"""
	try:
		return datetime.fromisoformat(str_stamp.replace("Z", "+00:00"))
	except ValueError:
		return None


# ⚠️ THE COMMENTS COME FROM REST, NOT FROM THE GATE'S GRAPHQL QUERY, AND THAT IS THE POINT.
# The gate's query returns `{author, body}` with no timestamps — it never needed them. This
# script does, because ordering cannot tell our request's own acknowledgement from a new window
# (see the block above `asked_recently`). Rather than widen a shared query for one consumer,
# the retry reads what it needs itself.
def fetch_comments(str_repo: str, int_number: int) -> list[dict]:
	"""Return one PR's issue comments, oldest first, normalised with timestamps.

	Parameters
	----------
	str_repo : str
		``owner/repo``.
	int_number : int
		The PR number.

	Returns
	-------
	list of dict
		Comments as ``{"login", "body", "created_at"}``, oldest first; empty when unreadable.
	"""
	list_raw = _gh_json(
		[
			"api",
			"--paginate",
			"--slurp",
			f"repos/{str_repo}/issues/{int_number}/comments?per_page=100",
		]
	)
	if not isinstance(list_raw, list):
		return []
	return [
		{
			"login": (dict_c.get("user") or {}).get("login") or "",
			"body": dict_c.get("body") or "",
			"created_at": dict_c.get("created_at") or "",
		}
		for list_page in list_raw
		if isinstance(list_page, list)
		for dict_c in list_page
		if isinstance(dict_c, dict)
	]


def pr_needs_retry(
	dict_pr: dict,
	list_comments: list[dict],
	set_reviewers: set[str],
	cls_gate: types.ModuleType,
	str_self_login: str = "",
	dt_now: datetime | None = None,
) -> bool:
	"""Return whether this PR is waiting on a rate-limited reviewer and should be re-asked.

	Parameters
	----------
	dict_pr : dict
		The ``pullRequest`` node from the gate's own query, for reviews and the head oid.
	list_comments : list of dict
		Normalised comments (``login``/``body``/``created_at``), oldest first.
	set_reviewers : set of str
		Logins that can actually submit a review.
	cls_gate : types.ModuleType
		The imported gate module.
	str_self_login : str, optional
		The login the retry posts as, used to tell OUR marker from anyone else's. Defaults to
		empty, which trusts no marker: the safe default is to ask twice, never to fall silent.
	dt_now : datetime.datetime or None, optional
		The current time; defaults to now in UTC.

	Returns
	-------
	bool
		``True`` when nothing has reviewed the head commit, the reviewer's newest word is a
		rate limit, and we have not asked within the cooldown.
	"""
	list_reviews = ((dict_pr.get("reviews") or {}).get("nodes")) or []
	str_head = dict_pr.get("headRefOid") or ""
	if cls_gate.reviewers_who_reported(list_reviews, set_reviewers, str_head):
		return False

	str_notice = newest_roster_notice(list_comments, set_reviewers, cls_gate.normalise_login)
	if not _RE_RATE_LIMIT.search(str_notice):
		return False

	return not asked_recently(
		list_comments,
		str_self_login,
		cls_gate.normalise_login,
		dt_now or datetime.now(timezone.utc),
	)


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


# `--slurp` yields a list of PAGES, each a list of PR objects — so the flattening is one level
# deeper than the obvious `[d["number"] for d in result]`, which would silently iterate PAGES
# and yield nothing. Kept a pure function so the multi-page shape can be tested without a network.
def flatten_pr_numbers(list_pages: list) -> list[int]:
	"""Flatten ``gh api --paginate --slurp`` output into a flat list of PR numbers.

	Parameters
	----------
	list_pages : list
		A list of pages, each a list of pull-request objects.

	Returns
	-------
	list of int
		Every PR number across every page, in order.
	"""
	return [
		dict_pr["number"]
		for list_page in list_pages
		if isinstance(list_page, list)
		for dict_pr in list_page
		if isinstance(dict_pr, dict) and dict_pr.get("number")
	]


# Whoever the PAT authenticates as is who our request will be authored by, so it is also the
# only author whose marker may be trusted. Resolving it from the token rather than configuring
# it means the two can never disagree — a configured login would silently stop matching the day
# the PAT is reissued on another account.
def resolve_self_login() -> str:
	"""Return the login the configured token authenticates as, or ``""`` when unknown.

	Returns
	-------
	str
		The login, or ``""`` when it cannot be resolved — which trusts no marker at all.
	"""
	dict_user = _gh_json(["api", "user", "--jq", "{login: .login}"])
	if not isinstance(dict_user, dict) or not dict_user.get("login"):
		print(
			"::warning::could not resolve the token's own login, so no marker is trusted — "
			"a review may be requested more than once per window."
		)
		return ""
	return str(dict_user["login"])


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

	# ⚠️ `--paginate`, not a bare `per_page=100`: without it only the first page is read, and a
	# rate-limited PR on page two is never retried — a silent partial pass, which is the exact
	# failure shape this family of scripts exists to prevent.
	#
	# ⚠️ AND NO `--jq` HERE, measured against gh 2.96.0: `--slurp` is REJECTED when combined
	# with `--jq` ("the `--slurp` option is not supported with `--jq` or `--template`"). Without
	# `--slurp`, `--paginate` emits one JSON array PER PAGE, which is not parseable as a single
	# document — so the parse would fail, this function would take its early return, and the
	# janitor would quietly do nothing on every tick. Slurp into pages and flatten in Python.
	list_pages = _gh_json(
		["api", "--paginate", "--slurp", f"repos/{str_repo}/pulls?state=open&per_page=100"]
	)
	if not isinstance(list_pages, list):
		return 0
	list_open = flatten_pr_numbers(list_pages)

	str_self_login = resolve_self_login()
	str_owner, _, str_name = str_repo.partition("/")
	int_asked = 0
	for int_number in list_open:
		dict_pr = cls_gate.fetch_pull_request(str_owner, str_name, int(int_number))
		list_comments = fetch_comments(str_repo, int(int_number))
		if pr_needs_retry(
			dict_pr, list_comments, set_reviewers, cls_gate, str_self_login
		) and request_review(str_repo, int(int_number)):
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
