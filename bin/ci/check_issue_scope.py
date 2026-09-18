"""Enforce that a PR's changed files stay inside the declared file surface of the issues it closes.

Full design rationale lives in ``docs/issue-scope.md``. Summary:

* An issue declares its file surface as a fenced ```surface``` code block in its body — one path
  or glob pattern per line — not a ``scope:*`` label. A label needs a separate taxonomy file
  mapping label to paths and a mass-backfill of every open issue before it protects anything; a
  fenced block is a single per-issue declaration written once, by whoever files the issue.
* The check reads the PR's changed files, the issues it closes (``closingIssuesReferences``,
  REST does not expose this — it is the one call that must go through ``gh``'s GraphQL-backed
  ``--json``), and its commit messages (for the override trailer) in ONE ``gh pr view`` call,
  then reads each linked issue's body with one REST call per issue. This repo's GitHub API quota
  was exhausted three times in one day by checks that re-queried every open PR and branch, so
  this gate is deliberately call-frugal: typically 2 calls total (1 PR + 1 issue).
* Strictness is "payable", not "zero current violations": a PR whose linked issue has not yet
  declared a surface is reported (UNDECLARED-SURFACE) but not blocked — enforcing against an
  empty backfill would immediately block every issue open the day this gate landed. Enforcement
  activates per issue, the moment that issue declares a surface.
* The API being unreadable (rate limit, network, auth) is NEVER a silent pass — it is reported as
  UNKNOWN and the check exits non-zero, matching this repo's rule that a skipped gate in CI is a
  gate reporting its own blindness as OK (see ``bin/ci/check_actions.sh``).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys


_RE_SURFACE_BLOCK = re.compile(r"```surface\s*\n(.*?)```", re.S)
_RE_OVERRIDE_TRAILER = re.compile(r"^surface-override:\s*(.+)$", re.I | re.M)


class ScopeCheckUnknown(Exception):
    """The GitHub API could not be read — must surface as UNKNOWN, never a silent pass."""


def gh_json(list_args: list[str]) -> dict:
    """Run a ``gh`` command and parse its stdout as JSON.

    Parameters
    ----------
    list_args : list of str
        Arguments passed to the ``gh`` binary, e.g. ``["pr", "view", "12", "--json", "files"]``.

    Returns
    -------
    dict
        The parsed JSON object.

    Raises
    ------
    ScopeCheckUnknown
        The command failed, timed out, or did not return valid JSON — the API is unreadable.
    """
    try:
        cls_result = subprocess.run(
            ["gh", *list_args],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
    except FileNotFoundError as cls_exc:
        raise ScopeCheckUnknown("gh CLI is not installed") from cls_exc
    except subprocess.TimeoutExpired as cls_exc:
        raise ScopeCheckUnknown(f"gh {' '.join(list_args)} timed out") from cls_exc
    except subprocess.CalledProcessError as cls_exc:
        str_detail = (cls_exc.stderr or cls_exc.stdout or str(cls_exc)).strip()
        raise ScopeCheckUnknown(f"gh {' '.join(list_args)} failed: {str_detail}") from cls_exc

    try:
        return json.loads(cls_result.stdout)
    except json.JSONDecodeError as cls_exc:
        raise ScopeCheckUnknown(f"gh {' '.join(list_args)} returned non-JSON output") from cls_exc


def pr_snapshot(str_repo: str, str_pr: str) -> tuple[list[str], list[int], list[str]]:
    """Return a PR's changed files, closed issue numbers, and commit bodies in one API call.

    Parameters
    ----------
    str_repo : str
        ``owner/name``.
    str_pr : str
        The pull request number, as a string.

    Returns
    -------
    tuple of (list of str, list of int, list of str)
        Changed file paths, linked issue numbers (from ``closingIssuesReferences``), and each
        commit's message body (searched for the ``surface-override:`` trailer).
    """
    dict_pr = gh_json(
        [
            "pr",
            "view",
            str_pr,
            "--repo",
            str_repo,
            "--json",
            "files,closingIssuesReferences,commits",
        ]
    )
    list_files = sorted({dict_f["path"] for dict_f in dict_pr.get("files", [])})
    list_issues = sorted(
        {int(dict_r["number"]) for dict_r in dict_pr.get("closingIssuesReferences", [])}
    )
    list_bodies = [dict_c.get("messageBody", "") or "" for dict_c in dict_pr.get("commits", [])]
    return list_files, list_issues, list_bodies


def issue_surface(str_repo: str, int_issue: int) -> set[str] | None:
    """Return one issue's declared file-surface patterns, or None if it declares none.

    Parameters
    ----------
    str_repo : str
        ``owner/name``.
    int_issue : int
        The issue number.

    Returns
    -------
    set of str or None
        Declared path/glob patterns, or None when the issue body has no ```surface``` block.
    """
    dict_issue = gh_json(["api", f"repos/{str_repo}/issues/{int_issue}"])
    str_body = dict_issue.get("body") or ""
    cls_match = _RE_SURFACE_BLOCK.search(str_body)
    if not cls_match:
        return None
    set_patterns = {
        str_line.strip()
        for str_line in cls_match.group(1).splitlines()
        if str_line.strip() and not str_line.strip().startswith("#")
    }
    # An empty fence (or one holding only comments) is UNDECLARED, never "declared as nothing".
    # Returning an empty set here would put every changed file outside the surface and fail the
    # PR, which is the opposite of the documented non-blocking behaviour for an undeclared
    # surface — and the issue template ships exactly that shape.
    return set_patterns or None


def path_in_surface(str_path: str, set_patterns: set[str]) -> bool:
    """Return whether a changed file falls inside a declared surface.

    Parameters
    ----------
    str_path : str
        A repo-relative changed-file path.
    set_patterns : set of str
        Declared patterns — an exact path, or a glob (``docs/**`` and ``docs/*`` are
        equivalent: `fnmatch` wildcards are not path-segment-aware, so `*` already spans `/`).

    Returns
    -------
    bool
        True when `str_path` matches any pattern.
    """
    return any(
        str_path == str_pattern
        or fnmatch.fnmatchcase(str_path, str_pattern.replace("/**", "/*"))
        for str_pattern in set_patterns
    )


def override_reason(list_bodies: list[str]) -> str | None:
    """Return the reason from a ``surface-override:`` commit trailer, if any commit carries one.

    Parameters
    ----------
    list_bodies : list of str
        Each commit's message body.

    Returns
    -------
    str or None
        The override reason, or None if no commit carries the trailer.
    """
    for str_body in list_bodies:
        cls_match = _RE_OVERRIDE_TRAILER.search(str_body)
        if cls_match:
            return cls_match.group(1).strip()
    return None


def gather_declared_surfaces(
    str_repo: str, list_issues: list[int]
) -> tuple[dict[int, set[str]], list[int]]:
    """Split a PR's linked issues into those with a declared surface and those without.

    Parameters
    ----------
    str_repo : str
        ``owner/name``.
    list_issues : list of int
        Linked issue numbers.

    Returns
    -------
    tuple of (dict of {int: set of str}, list of int)
        Declared surfaces keyed by issue number, and the issue numbers with none.

    Raises
    ------
    ScopeCheckUnknown
        Any linked issue's body could not be read.
    """
    dict_declared: dict[int, set[str]] = {}
    list_undeclared: list[int] = []
    for int_issue in list_issues:
        set_surface = issue_surface(str_repo, int_issue)
        if set_surface is None:
            list_undeclared.append(int_issue)
        else:
            dict_declared[int_issue] = set_surface
    return dict_declared, list_undeclared


def report_violations(
    list_files: list[str],
    dict_declared: dict[int, set[str]],
    list_commit_bodies: list[str],
) -> tuple[int, list[str]]:
    """Compare changed files against the declared union and report the verdict.

    Parameters
    ----------
    list_files : list of str
        The PR's changed file paths.
    dict_declared : dict of {int: set of str}
        Declared surfaces keyed by issue number — every linked issue has one.
    list_commit_bodies : list of str
        Each commit's message body, searched for the override trailer.

    Returns
    -------
    tuple of (int, list of str)
        Exit code (0 pass, 1 fail) and the lines to print.
    """
    set_union: set[str] = set()
    for set_surface in dict_declared.values():
        set_union |= set_surface

    list_violations = [
        str_path for str_path in list_files if not path_in_surface(str_path, set_union)
    ]
    if not list_violations:
        return 0, [
            f"scope OK: {len(list_files)} file(s) within the declared surface of "
            f"{sorted(dict_declared)}"
        ]

    str_reason = override_reason(list_commit_bodies)
    if str_reason:
        list_lines = [
            f"OVERRIDDEN (surface-override: {str_reason}) — files outside declared surface:"
        ]
        list_lines += [f"    {str_path}" for str_path in list_violations]
        return 0, list_lines

    list_lines = ["::error::files touched outside the declared issue surface:"]
    list_lines += [f"    {str_path}" for str_path in list_violations]
    list_lines.append(
        "add the path(s) to a ```surface``` block on the linked issue, or add a "
        "'surface-override: <reason>' commit trailer to widen this PR's surface deliberately"
    )
    return 1, list_lines


def evaluate(str_repo: str, str_pr: str) -> tuple[int, list[str]]:
    """Evaluate one PR against its linked issues' declared surfaces.

    Parameters
    ----------
    str_repo : str
        ``owner/name``.
    str_pr : str
        The pull request number, as a string.

    Returns
    -------
    tuple of (int, list of str)
        Exit code (0 pass, 1 fail/unknown) and the lines to print.
    """
    try:
        list_files, list_issues, list_bodies = pr_snapshot(str_repo, str_pr)
        if not list_issues:
            return 0, ["no linked issue found for this PR — scope check not applicable"]
        dict_declared, list_undeclared = gather_declared_surfaces(str_repo, list_issues)
    except ScopeCheckUnknown as cls_exc:
        return 1, [f"::error::UNKNOWN — could not verify issue scope: {cls_exc}"]

    if list_undeclared:
        str_issues = ", ".join(f"#{n}" for n in list_undeclared)
        return 0, [
            f"UNDECLARED-SURFACE: {str_issues} closes without a declared surface — scope not "
            "enforced for this PR (payable strictness; see docs/issue-scope.md).",
            "Declare a ```surface``` block on the issue body to activate enforcement.",
        ]

    return report_violations(list_files, dict_declared, list_bodies)


def main() -> int:
    """Run the scope check from ``GITHUB_REPOSITORY`` / ``PR_NUMBER`` and print the verdict.

    Returns
    -------
    int
        Process exit code.
    """
    str_repo = os.environ.get("GITHUB_REPOSITORY", "")
    str_pr = os.environ.get("PR_NUMBER", "")
    if not str_repo or not str_pr:
        print("::error::GITHUB_REPOSITORY and PR_NUMBER must both be set", file=sys.stderr)
        return 1

    int_code, list_lines = evaluate(str_repo, str_pr)
    str_stream = sys.stderr if int_code else sys.stdout
    for str_line in list_lines:
        print(str_line, file=str_stream)
    return int_code


if __name__ == "__main__":
    sys.exit(main())
