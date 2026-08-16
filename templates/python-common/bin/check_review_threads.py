"""Fail a PR whose review threads were resolved without anyone answering them.

A review finding is dealt with in **two** halves — change the code, and **reply on the thread**
— and only the first is visible from the editor. The second is what a future session reads: a
thread holding just "finding" plus "addressed in commit <sha>" records that something changed,
never *why* — that the finding was deeper than reported, that the fix was relocated rather than
applied, that a sibling case was deliberately left alone. That rationale is the asset.

⚠️ ``isResolved`` does **not** answer this. A good review bot closes its own thread the moment
it sees the fix, so the flag measures the BOT's satisfaction, not the author's response.
Measured on the PR that motivated this gate: all 14 threads showed ``isResolved: true`` and
**11 of them held no reply from the author at all**.

The predicate is therefore about **thread content, never resolver identity**:

    a thread is answered when it holds at least one comment from an author OUTSIDE the
    declared review-bot roster, of at least ``int_min_chars`` characters.

That single rule settles three questions at once — what counts as answered (a bot's own
acknowledgement does not), who may resolve (anyone; identity is not the signal), and
bot-replying-to-bot (excluded by construction). Two rules people reach for first —
*"only a human may resolve"* and *"the last comment must be human"* — **fail the best case**,
because a good bot acknowledges the human's reply and then resolves, so the bot's comment is
always last.

**Provider-agnostic by construction.** The roster is data in ``.review-bots.yaml``; no tool is
named in the logic here. Adding a reviewer is adding a row. Note the shapes genuinely differ:
one tool posts inline threads, another posts only a status check and no thread at all — a
roster that assumes "every reviewer speaks in threads" is born broken, which is why an empty
thread list is a pass, not a failure.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys


try:
	import yaml
except ModuleNotFoundError:  # pragma: no cover - the gate self-skips without its parser
	yaml = None  # type: ignore[assignment]


_ROSTER_FILE = ".review-bots.yaml"
# Floor for a "substantive" reply. Measured, not invented: the replies on the PR that motivated
# this gate ran 100-667 characters (median 439), and an earlier sample of genuine verdict
# replies ran 356-1126. 100 sits at or below the shortest real one, so it excludes "done" and
# "fixed" without ever arguing with a real answer.
_MIN_REPLY_CHARS = 100

_QUERY = """
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviewThreads(first:100) {
        nodes {
          isResolved
          isOutdated
          path
          comments(first:50) { nodes { author { login } body } }
        }
      }
    }
  }
}
"""


def load_roster(path_root: pathlib.Path) -> set[str]:
	"""Read the declared review-bot logins.

	Parameters
	----------
	path_root : pathlib.Path
	    Repository root holding ``.review-bots.yaml``.

	Returns
	-------
	set of str
	    Logins treated as reviewers rather than as answers. Empty when the file is absent,
	    which makes the gate a no-op rather than a source of false failures.
	"""
	path_roster = path_root / _ROSTER_FILE
	if yaml is None or not path_roster.is_file():
		return set()
	dict_roster = yaml.safe_load(path_roster.read_text(encoding="utf-8")) or {}
	return {
		str(d.get("login", "")) for d in (dict_roster.get("reviewers") or []) if d.get("login")
	}


def fetch_threads(str_owner: str, str_repo: str, int_number: int) -> list[dict]:
	"""Fetch the PR's review threads through the GitHub GraphQL API.

	Parameters
	----------
	str_owner : str
	    Repository owner.
	str_repo : str
	    Repository name.
	int_number : int
	    Pull-request number.

	Returns
	-------
	list of dict
	    One entry per review thread.

	Raises
	------
	RuntimeError
	    If the API call fails, so an unreachable API is never mistaken for a clean PR.
	"""
	list_cmd = [
		"gh",
		"api",
		"graphql",
		"-f",
		f"query={_QUERY}",
		"-F",
		f"owner={str_owner}",
		"-F",
		f"repo={str_repo}",
		"-F",
		f"number={int_number}",
	]
	# Constant argv built from CI-provided identifiers; no shell is involved.
	cls_run = subprocess.run(list_cmd, capture_output=True, text=True, check=False)  # noqa: S603
	if cls_run.returncode != 0:
		raise RuntimeError(f"GraphQL query failed: {cls_run.stderr.strip()[:400]}")
	dict_out = json.loads(cls_run.stdout)
	if "errors" in dict_out:
		raise RuntimeError(f"GraphQL returned errors: {dict_out['errors']}")
	return dict_out["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]


def find_thread_problems(
	list_threads: list[dict], set_roster: set[str], int_min_chars: int = _MIN_REPLY_CHARS
) -> list[str]:
	"""Return one problem per thread that nobody outside the roster answered.

	Parameters
	----------
	list_threads : list of dict
	    Review threads as returned by :func:`fetch_threads`.
	set_roster : set of str
	    Logins that count as reviewers rather than as answers.
	int_min_chars : int, optional
	    Minimum length for a reply to count as substantive.

	Returns
	-------
	list of str
	    Human-readable problems; empty when every thread carries an answer.
	"""
	list_problems: list[str] = []
	for dict_thread in list_threads:
		list_comments = dict_thread["comments"]["nodes"]
		if not list_comments:
			continue
		list_answers = [
			c
			for c in list_comments
			if (c.get("author") or {}).get("login") not in set_roster
			and len((c.get("body") or "").strip()) >= int_min_chars
		]
		if list_answers:
			continue

		str_first = (list_comments[0].get("body") or "").strip().splitlines()
		str_title = next(
			(s for s in str_first if s.startswith("**")),
			str_first[0] if str_first else "",
		)
		str_state = "resolved" if dict_thread.get("isResolved") else "open"
		list_problems.append(
			f"{dict_thread.get('path', '?')}: thread is {str_state} but nobody outside the "
			f"reviewer roster answered it — {str_title.strip('* ')[:90]}"
		)
	return list_problems


def main() -> int:
	"""Check the current PR's review threads.

	Returns
	-------
	int
	    ``0`` when every thread is answered (or the repo declares no roster), ``1`` otherwise.
	"""
	str_repo_full = os.environ.get("GITHUB_REPOSITORY", "")
	str_number = os.environ.get("PR_NUMBER", "")
	if not str_repo_full or not str_number.isdigit():
		print("PR_NUMBER / GITHUB_REPOSITORY not set — nothing to check")
		return 0

	path_root = pathlib.Path.cwd()
	set_roster = load_roster(path_root)
	if not set_roster:
		print(f"No {_ROSTER_FILE} — the review-thread gate is not adopted here")
		return 0

	str_owner, _, str_repo = str_repo_full.partition("/")
	list_threads = fetch_threads(str_owner, str_repo, int(str_number))
	list_problems = find_thread_problems(list_threads, set_roster)

	for str_problem in list_problems:
		print(f"❌ {str_problem}")
	if list_problems:
		print(
			f"\n{len(list_problems)} of {len(list_threads)} review thread(s) carry no answer.\n"
			"Resolving a thread is not answering it: a reviewer bot closes its own threads when "
			"it sees the fix, so the resolved flag records ITS satisfaction, not your reasoning. "
			"Reply with what changed and why — that reply is what the next session reads to learn "
			"the decision."
		)
		return 1
	print(f"All {len(list_threads)} review thread(s) answered.")
	return 0


if __name__ == "__main__":
	# Windows' stdout defaults to cp1252, which cannot encode the status glyphs this
	# script prints: it would die with UnicodeEncodeError before reporting anything. And
	# because this backs an always_run pre-commit hook, that crash blocks EVERY commit from
	# a Windows checkout rather than failing the file under check. Fixed at the I/O seam so
	# the glyphs stay; a test pins it with PYTHONIOENCODING=cp1252.
	for cls_stream in (sys.stdout, sys.stderr):
		if hasattr(cls_stream, "reconfigure"):
			cls_stream.reconfigure(encoding="utf-8", errors="replace")

	sys.exit(main())
