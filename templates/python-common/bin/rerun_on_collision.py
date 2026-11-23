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

TOKEN. Everything goes through ``GITHUB_TOKEN``. ⚠️ A branch update pushed with ``GITHUB_TOKEN``
does NOT start workflows on the PR (GitHub suppresses token-triggered events to prevent
recursion), so with the default token the branch is updated but CI may not re-run. Set
``RERUN_TOKEN`` (a PAT or App token with ``pull-requests: write``) to make the update retrigger CI.
"""

import fnmatch
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
DEFAULT_EXCLUDES = "poetry.lock,CHANGELOG.md"
ZERO_SHA = "0" * 40
PAGE_SIZE = 100


def paths_of(files: list[dict]) -> set[str]:
    """Return every path a file list touches, including the old name of a rename."""
    return {p for f in files for p in (f["filename"], f.get("previous_filename")) if p}


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
    return [g.strip() for g in str_raw.replace("\n", ",").split(",") if g.strip()]


def colliding_prs(
    merge_files: set[str], *, pr_files: dict[int, set[str]], excludes: list[str] | None = None
) -> list[int]:
    """Return the PR numbers whose files intersect the merge's, ignoring hot files.

    Parameters
    ----------
    merge_files : set[str]
        Paths the merge changed.
    pr_files : dict[int, set[str]]
        Open PR number to the paths that PR changes.
    excludes : list[str] | None
        ``fnmatch`` globs for paths to ignore on both sides.

    Returns
    -------
    list[int]
        Sorted PR numbers to update.
    """
    globs = excludes or []

    def keep(str_path: str) -> bool:
        return not any(fnmatch.fnmatch(str_path, g) for g in globs)

    merged = {p for p in merge_files if keep(p)}
    return sorted(n for n, files in pr_files.items() if merged & {p for p in files if keep(p)})


def _call(str_method: str, *, str_path: str, str_token: str) -> object:
    """Make one GitHub REST call and return the decoded JSON body."""
    req = urllib.request.Request(  # noqa: S310 - fixed https API host
        f"{API}/{str_path}",
        method=str_method,
        headers={
            "Authorization": f"Bearer {str_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read() or b"null")


def _paged(str_path: str, *, str_token: str, str_key: str = "") -> list:
    """Collect every page of a list endpoint (``str_key`` names the list inside an object)."""
    sep = "&" if "?" in str_path else "?"
    out: list = []
    page = 1
    while True:
        str_page = f"{str_path}{sep}per_page={PAGE_SIZE}&page={page}"
        data = _call("GET", str_path=str_page, str_token=str_token)
        items = data[str_key] if str_key else data
        out.extend(items)
        if len(items) < PAGE_SIZE:
            return out
        page += 1


def _open_pr_files(repo: str, *, branch: str, str_token: str) -> dict[int, set[str]]:
    """Map each open non-draft PR to its paths, skipping PRs whose files cannot be read."""
    pr_files: dict[int, set[str]] = {}
    for pr in _paged(f"repos/{repo}/pulls?state=open&base={branch}", str_token=str_token):
        if pr["draft"]:
            continue
        str_files = f"repos/{repo}/pulls/{pr['number']}/files"
        try:
            pr_files[pr["number"]] = paths_of(_paged(str_files, str_token=str_token))
        except (urllib.error.URLError, TimeoutError) as err:
            print(f"skip PR #{pr['number']}: cannot read files: {err}")
    return pr_files


def _merge_files(repo: str, *, before: str, after: str, str_token: str) -> set[str]:
    """Return the paths the push changed (a lone commit when ``before`` is the zero sha)."""
    if before == ZERO_SHA:
        commit = _call("GET", str_path=f"repos/{repo}/commits/{after}", str_token=str_token)
        return paths_of(commit["files"])
    str_cmp = f"repos/{repo}/compare/{before}...{after}"
    return paths_of(_paged(str_cmp, str_token=str_token, str_key="files"))


def main() -> int:
    """Update every open PR that collides with the push that triggered this run.

    Returns
    -------
    int
        0 always for per-PR failures (logged); 1 only when the merge's files cannot be read.
    """
    token = os.environ.get("RERUN_TOKEN") or os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    before, after = os.environ.get("BEFORE_SHA", ZERO_SHA), os.environ["AFTER_SHA"]
    branch = os.environ.get("BASE_BRANCH", "main")
    excludes = parse_excludes(os.environ.get("RERUN_EXCLUDE_FILES", DEFAULT_EXCLUDES))

    try:
        merge = _merge_files(repo, before=before, after=after, str_token=token)
    except (urllib.error.URLError, TimeoutError) as err:
        print(f"cannot read merge files: {err}", file=sys.stderr)
        return 1

    pr_files = _open_pr_files(repo, branch=branch, str_token=token)

    for num in colliding_prs(merge, pr_files=pr_files, excludes=excludes):
        try:
            _call("PUT", str_path=f"repos/{repo}/pulls/{num}/update-branch", str_token=token)
            print(f"updated PR #{num}")
        except urllib.error.HTTPError as err:
            print(f"skip PR #{num}: HTTP {err.code}")
        except (urllib.error.URLError, TimeoutError) as err:
            print(f"skip PR #{num}: {err}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
