"""Re-test open PRs that touch the files a default-branch merge changed (blueprintx#1286).

With the strict "branch must be up to date" policy off, an open PR is not re-tested after other
PRs merge. GitHub still blocks TEXTUAL conflicts, but a semantic collision (no line conflict)
lets a PR merge on a CI run that never saw the new main. After each push to the default branch
this script intersects the files that push changed with the files of every open PR targeting
that branch and calls ``update-branch`` on each PR that overlaps, which re-runs its CI. PRs with
no overlap are left alone.

LIMITATION, STATED PLAINLY. File overlap is a cheap proxy, not a guarantee. On 2026-11-22 main
went red twice from collisions this check would NOT have caught, because the colliding PRs touched
DIFFERENT files: ``enable_pages.sh`` began sourcing a new lib that its test fixture did not copy,
and a new ruff-pin guard collided with a later unpinned ``pipx install ruff``. The CI run on the
default branch (blueprintx#1282) remains the real net; this is an early re-test only.

HOT FILES. Files nearly every PR touches would make every PR collide with every merge. Paths
matching ``RERUN_EXCLUDE_FILES`` (comma- or newline-separated ``fnmatch`` globs) are ignored on
both sides. Default: ``poetry.lock,CHANGELOG.md``.

TOKEN. The script only runs with the ``RERUN_TOKEN`` secret (a PAT or App token with
``contents: write`` and ``pull-requests: write``). A branch update pushed with ``GITHUB_TOKEN``
starts no workflows on the PR (GitHub suppresses token-triggered events), so the PR would sit
on "waiting for status" with no checks on its new head; without the secret the script logs and
exits 0 without touching any PR.
COST. Every update moves the PR head: earlier reviews no longer cover it, approvals are dismissed
where the "dismiss stale approvals" rule is on, and review bots run again. A truncated merge file
list updates EVERY open PR at once. ``update-branch`` is sent without ``expected_head_sha``: it
merges the default branch into whatever head exists at that moment, which is the same result as
the "Update branch" button. The workflow triggers on ``main`` only; a project whose default
branch has another name must change ``branches:`` in ``rerun-on-collision.yml``.
Draft and bot-authored PRs (Dependabot, Renovate) are never updated: a push to a bot branch makes
the bot stop maintaining it. A PR whose files cannot be read is logged and skipped (it is still
updated when the merge file list was truncated).

RE-REVIEW. The review gate (``check_review_threads.py``) carries a review forward only while the
PR's own patch fingerprint is unchanged, and turns red ("review superseded") otherwise. After a
successful update this script waits for the PR head to move, fingerprints the old and the new
head with that gate's own ``fetch_patch_fingerprint``, and posts ONE review request comment per
PR when the fingerprints differ. An unchanged fingerprint posts nothing: the carried-forward
review stands. A fingerprint that cannot be computed counts as changed, the gate's own fail-closed
reading. Who is asked comes from ``.review-bots.yaml`` through the gate's loaders: only a
``posts: threads`` login with an entry in ``REVIEW_COMMANDS`` is asked, so a roster with no such
login (or none at all) requests nothing. Requests go out in ascending PR number, which is age
order, one comment per PR and reviewer per run, so a merge that collides with many PRs does not
burst one reviewer's quota. Two merges in a row that both collide with a PR each post a request:
a request already pending is not detected. The head wait is bounded (HEAD_POLLS x
HEAD_POLL_SECONDS per PR, serial, inside the job's ``timeout-minutes``); a head that never moves
is logged as a warning and requests nothing. The review gate is imported best-effort: when it is
missing the branch updates still run and nothing is requested. The comment is authored by the
``RERUN_TOKEN`` user (the same
``pull-requests: write`` the update needs): CodeRabbit ignores bot-authored comments. The
fingerprint reads use ``gh``, which takes its token from ``GH_TOKEN``; the workflow sets it to
``RERUN_TOKEN``.
"""

from collections.abc import Callable
import fnmatch
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


try:
    import check_review_threads
except ImportError:
    check_review_threads = None  # type: ignore[assignment]


API = "https://api.github.com"
DEFAULT_EXCLUDES = "poetry.lock,CHANGELOG.md"
ZERO_SHA = "0" * 40
PAGE_SIZE = 100
FILE_CAP = 300
PR_FILE_CAP = 3000
HEAD_POLLS = 20
HEAD_POLL_SECONDS = 3
REVIEW_COMMANDS = {"coderabbitai": "@coderabbitai full review"}


def paths_of(list_files: list[dict]) -> set[str]:
    """Return every path a file list touches, including the old name of a rename."""
    return {
        str_item
        for dict_file in list_files
        for str_item in (dict_file["filename"], dict_file.get("previous_filename"))
        if str_item
    }


def parse_excludes(str_raw: str) -> list[str]:
    """Split a comma/newline-separated glob list, dropping blanks.

    Parameters
    ----------
    str_raw : str
        Raw ``RERUN_EXCLUDE_FILES`` value.

    Returns
    -------
    list[str]
        The globs.
    """
    return [
        str_glob.strip() for str_glob in str_raw.replace("\n", ",").split(",") if str_glob.strip()
    ]


def colliding_prs(
    set_merge_files: set[str],
    *,
    dict_pr_files: dict[int, set[str]],
    list_excludes: list[str] | None = None,
) -> list[int]:
    """Return the PR numbers whose files intersect the merge's, ignoring hot files.

    Parameters
    ----------
    set_merge_files : set[str]
        Paths the merge changed.
    dict_pr_files : dict[int, set[str]]
        Open PR number to the paths that PR changes.
    list_excludes : list[str] | None
        ``fnmatch`` globs for paths to ignore on both sides.

    Returns
    -------
    list[int]
        Sorted PR numbers to update.
    """
    list_globs = list_excludes or []

    def fn_keep(str_path: str) -> bool:
        str_base = str_path.rsplit("/", 1)[-1]
        return not any(
            fnmatch.fnmatch(str_path, str_glob) or fnmatch.fnmatch(str_base, str_glob)
            for str_glob in list_globs
        )

    set_merged = {str_item for str_item in set_merge_files if fn_keep(str_item)}
    return sorted(
        int_pr
        for int_pr, set_paths in dict_pr_files.items()
        if set_merged & {str_item for str_item in set_paths if fn_keep(str_item)}
    )


def _call(
    str_method: str, *, str_path: str, str_token: str, dict_body: dict | None = None
) -> object:
    """Make one GitHub REST call and return the decoded JSON body."""
    cls_request = urllib.request.Request(  # noqa: S310 - fixed https API host
        f"{API}/{str_path}",
        method=str_method,
        data=None if dict_body is None else json.dumps(dict_body).encode(),
        headers={
            "Authorization": f"Bearer {str_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **({} if dict_body is None else {"Content-Type": "application/json"}),
        },
    )
    with urllib.request.urlopen(cls_request, timeout=30) as cls_resp:  # noqa: S310
        return json.loads(cls_resp.read() or b"null")


def _paged(str_path: str, *, str_token: str) -> list:
    """Collect every page of a list endpoint."""
    str_sep = "&" if "?" in str_path else "?"
    list_out: list = []
    int_page = 1
    while True:
        str_page = f"{str_path}{str_sep}per_page={PAGE_SIZE}&page={int_page}"
        obj_data = _call("GET", str_path=str_page, str_token=str_token)
        if not isinstance(obj_data, list):
            raise ValueError(f"{str_path}: expected a list, got {type(obj_data).__name__}")
        list_out.extend(obj_data)
        if len(obj_data) < PAGE_SIZE:
            return list_out
        int_page += 1


def _open_pr_files(
    str_repo: str, *, str_branch: str, str_token: str
) -> tuple[dict[int, set[str]], set[int]]:
    """Map each open non-draft PR to its paths, plus the PRs whose file list GitHub capped.

    A PR file list stops at PR_FILE_CAP files, so a capped PR may overlap through a file the
    API omitted; the caller updates it unconditionally. Unreadable PRs are logged and skipped.
    """
    dict_pr_files: dict[int, set[str]] = {}
    set_capped: set[int] = set()
    for dict_pr in _paged(
        f"repos/{str_repo}/pulls?state=open&base={urllib.parse.quote(str_branch)}",
        str_token=str_token,
    ):
        if dict_pr["draft"] or (dict_pr["user"] or {}).get("type") == "Bot":
            continue
        str_files = f"repos/{str_repo}/pulls/{dict_pr['number']}/files"
        try:
            list_files = _paged(str_files, str_token=str_token)
            dict_pr_files[dict_pr["number"]] = paths_of(list_files)
            if len(list_files) >= PR_FILE_CAP:
                set_capped.add(dict_pr["number"])
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc_err:
            dict_pr_files[dict_pr["number"]] = set()
            print(f"::warning::skip PR #{dict_pr['number']}: cannot read files: {exc_err}")
    return dict_pr_files, set_capped


def _merge_files(
    str_repo: str, *, str_before: str, str_after: str, str_token: str
) -> set[str] | None:
    """Return the paths the push changed, or None when GitHub capped the list at 300 files."""
    if str_before == ZERO_SHA:
        obj_data = _call(
            "GET", str_path=f"repos/{str_repo}/commits/{str_after}", str_token=str_token
        )
    else:
        obj_data = _call(
            "GET",
            str_path=f"repos/{str_repo}/compare/{str_before}...{str_after}",
            str_token=str_token,
        )
    list_files = obj_data.get("files")
    return None if list_files is None or len(list_files) >= FILE_CAP else paths_of(list_files)


def _targets(
    set_merge: set[str] | None,
    *,
    dict_pr_files: dict[int, set[str]],
    list_excludes: list[str],
    set_capped: frozenset[int] | set[int] = frozenset(),
) -> list[int]:
    """Pick the PRs to update; a truncated merge or PR file list updates conservatively."""
    if set_merge is None:
        print(f"merge file list reached {FILE_CAP} (GitHub's cap): updating every open PR")
        return sorted(dict_pr_files)
    if set_capped:
        print(f"PR file list reached {PR_FILE_CAP} (GitHub's cap), updating: {sorted(set_capped)}")
    return sorted(
        set(colliding_prs(set_merge, dict_pr_files=dict_pr_files, list_excludes=list_excludes))
        | set_capped
    )


def review_commands(dict_roster: dict[str, str]) -> list[str]:
    """Return the review requests the roster's reviewers can be asked with.

    Parameters
    ----------
    dict_roster : dict[str, str]
        Roster as returned by ``check_review_threads.load_roster``.

    Returns
    -------
    list[str]
        One comment body per ``posts: threads`` login that has an entry in ``REVIEW_COMMANDS``,
        in login order. Empty for an empty roster.
    """
    set_reviewers = check_review_threads.reviewer_logins(dict_roster)
    for str_login in sorted(set_reviewers - set(REVIEW_COMMANDS)):
        print(f"::warning::reviewer {str_login} has no entry in REVIEW_COMMANDS: it is not asked")
    set_asked = set_reviewers & set(REVIEW_COMMANDS)
    return [REVIEW_COMMANDS[str_login] for str_login in sorted(set_asked)]


def patch_unchanged(fn_fingerprint: Callable[[str], str], *, str_old: str, str_new: str) -> bool:
    """Return whether the PR's own patch is the same at the old and the new head.

    Parameters
    ----------
    fn_fingerprint : Callable[[str], str]
        Maps a commit oid to its patch fingerprint; raises when the patch is unavailable.
    str_old : str
        The head before the branch update.
    str_new : str
        The head after it.

    Returns
    -------
    bool
        ``True`` only when both fingerprints were computed and are equal, the review gate's
        own fail-closed rule (``check_review_threads.review_covers_head``).
    """
    try:
        return check_review_threads.review_covers_head(
            fn_fingerprint,
            str_review_oid=str_old,
            str_head_oid=str_new,
            str_head_digest=fn_fingerprint(str_new),
        )
    except Exception as exc_err:  # noqa: BLE001
        print(f"patch fingerprint of {str_new[:7]} unavailable: {exc_err}")
        return False


def _pull(str_repo: str, *, int_num: int, str_token: str) -> dict:
    """Read one PR and return it as a dict."""
    obj_data = _call("GET", str_path=f"repos/{str_repo}/pulls/{int_num}", str_token=str_token)
    if not isinstance(obj_data, dict):
        raise ValueError(f"PR #{int_num}: expected an object, got {type(obj_data).__name__}")
    return obj_data


def _await_new_head(
    fn_pull: Callable[[], dict], *, str_old: str, fn_sleep: Callable[[float], None] = time.sleep
) -> dict | None:
    """Poll until the PR head differs from ``str_old``; None if it never moves.

    ``update-branch`` answers 202 before the merge commit exists, so the new head has to be
    waited for.
    """
    for _ in range(HEAD_POLLS):
        dict_pull = fn_pull()
        if dict_pull["head"]["sha"] != str_old:
            return dict_pull
        fn_sleep(HEAD_POLL_SECONDS)
    return None


def _ask_for_review(
    str_repo: str, *, int_num: int, str_token: str, list_commands: list[str]
) -> None:
    """Post one comment per review command on the PR."""
    for str_command in list_commands:
        _call(
            "POST",
            str_path=f"repos/{str_repo}/issues/{int_num}/comments",
            str_token=str_token,
            dict_body={"body": str_command},
        )
        print(f"requested review on PR #{int_num}: {str_command}")


def _follow_up(
    str_repo: str, *, int_num: int, str_old: str, str_token: str, list_commands: list[str]
) -> None:
    """Request a new review when the update changed the PR's own patch."""
    dict_pull = _await_new_head(
        lambda: _pull(str_repo, int_num=int_num, str_token=str_token), str_old=str_old
    )
    if dict_pull is None:
        print(f"::warning::PR #{int_num}: head did not move, no review requested")
        return
    str_owner, _, str_name = str_repo.partition("/")
    str_base = dict_pull["base"]["sha"]
    if patch_unchanged(
        lambda str_oid: check_review_threads.fetch_patch_fingerprint(
            str_owner, str_repo=str_name, str_base=str_base, str_oid=str_oid
        ),
        str_old=str_old,
        str_new=dict_pull["head"]["sha"],
    ):
        return
    _ask_for_review(str_repo, int_num=int_num, str_token=str_token, list_commands=list_commands)


def _update_one(str_repo: str, *, int_num: int, str_token: str, list_commands: list[str]) -> None:
    """Update one PR's branch, then request a review if its own patch changed."""
    try:
        str_old = _pull(str_repo, int_num=int_num, str_token=str_token)["head"]["sha"]
        _call(
            "PUT", str_path=f"repos/{str_repo}/pulls/{int_num}/update-branch", str_token=str_token
        )
        print(f"updated PR #{int_num}")
    except urllib.error.HTTPError as exc_err:
        print(f"skip PR #{int_num}: HTTP {exc_err.code}")
        return
    except (OSError, ValueError, KeyError, TypeError) as exc_err:
        print(f"skip PR #{int_num}: {exc_err}")
        return
    if not list_commands:
        return
    try:
        _follow_up(
            str_repo,
            int_num=int_num,
            str_old=str_old,
            str_token=str_token,
            list_commands=list_commands,
        )
    except Exception as exc_err:  # noqa: BLE001
        print(f"::warning::PR #{int_num}: review request failed: {exc_err}")


def _roster_commands() -> list[str]:
    """Return the review requests for this checkout's roster; empty when it cannot be read.

    A roster that is missing, malformed or without a reviewer must never stop the branch
    updates, so every failure is logged and read as "nobody to ask". That includes the review
    gate not being importable next to this script.
    """
    if check_review_threads is None:
        print("::warning::check_review_threads.py is not importable: no review will be requested")
        return []
    try:
        return review_commands(check_review_threads.load_roster(pathlib.Path.cwd()))
    except Exception as exc_err:  # noqa: BLE001
        print(f"::warning::no review will be requested, roster unusable: {exc_err}")
        return []


def main() -> int:
    """Update every open PR that collides with the push that triggered this run.

    Returns
    -------
    int
        0 always for per-PR failures (logged); 1 only when the merge's files or the
        open-PR list cannot be read.
    """
    str_token = os.environ.get("RERUN_TOKEN")
    if not str_token:
        print("::warning::RERUN_TOKEN is not set: skipping, a GITHUB_TOKEN update starts no CI")
        return 0
    str_repo = os.environ["GITHUB_REPOSITORY"]
    str_before, str_after = os.environ.get("BEFORE_SHA") or ZERO_SHA, os.environ["AFTER_SHA"]
    str_branch = os.environ.get("BASE_BRANCH") or "main"
    list_excludes = parse_excludes(os.environ.get("RERUN_EXCLUDE_FILES") or DEFAULT_EXCLUDES)

    try:
        set_merge = _merge_files(
            str_repo, str_before=str_before, str_after=str_after, str_token=str_token
        )
        dict_pr_files, set_capped = _open_pr_files(
            str_repo, str_branch=str_branch, str_token=str_token
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc_err:
        print(f"cannot read merge files or open PRs: {exc_err}", file=sys.stderr)
        return 1

    list_commands = _roster_commands()
    for int_num in _targets(
        set_merge, dict_pr_files=dict_pr_files, list_excludes=list_excludes, set_capped=set_capped
    ):
        _update_one(str_repo, int_num=int_num, str_token=str_token, list_commands=list_commands)
    return 0


if __name__ == "__main__":
    sys.exit(main())
