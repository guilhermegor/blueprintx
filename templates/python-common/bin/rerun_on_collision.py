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
"""

import fnmatch
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


API = "https://api.github.com"
DEFAULT_EXCLUDES = "poetry.lock,CHANGELOG.md"
ZERO_SHA = "0" * 40
PAGE_SIZE = 100
FILE_CAP = 300
PR_FILE_CAP = 3000


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


def _call(str_method: str, *, str_path: str, str_token: str) -> object:
    """Make one GitHub REST call and return the decoded JSON body."""
    cls_request = urllib.request.Request(  # noqa: S310 - fixed https API host
        f"{API}/{str_path}",
        method=str_method,
        headers={
            "Authorization": f"Bearer {str_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
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

    for int_num in _targets(
        set_merge, dict_pr_files=dict_pr_files, list_excludes=list_excludes, set_capped=set_capped
    ):
        try:
            _call(
                "PUT",
                str_path=f"repos/{str_repo}/pulls/{int_num}/update-branch",
                str_token=str_token,
            )
            print(f"updated PR #{int_num}")
        except urllib.error.HTTPError as exc_err:
            print(f"skip PR #{int_num}: HTTP {exc_err.code}")
        except (OSError, ValueError) as exc_err:
            print(f"skip PR #{int_num}: {exc_err}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
