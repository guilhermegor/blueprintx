"""Fail a PR whose cumulative branch diff exceeds CodeRabbit's file-review cap.

CodeRabbit hard-refuses to review above 100 changed files ("Review skipped: N files
exceed the limit of 100"), and a PR in that state can never merge. The review-thread
gate (``templates/common/bin/check_review_threads.py``, blueprintx#433) reports that
refusal clearly once it happens — nothing until now PREVENTED it. Live proof:
blueprintx#424, open 13+ days at 241 files, selected twice in one hour by the
reviewer-slot step because it wins on contention and age (dotfiles-dev#420).

Calibrated over the 100 most recent PRs (blueprintx#551): exactly ONE violation
(#424, 241 files). The largest LEGITIMATE PR in that same set is #532 at 59 files —
an entire new skeleton tier. MAX_CHANGED_FILES = 90 therefore sits 10 below
CodeRabbit's vendor cap of 100 and 31 files above the biggest real change this repo
produces: headroom on both sides, not a number chosen to match today's diff.

Three design points, decided rather than assumed:

* **Fail, not warn.** A gate that cannot fail teaches people to ignore it
  (dotfiles-dev#250), and at a 1%-of-100 violation rate the cost of failing is near
  zero. The message below names the remedy (split at a natural seam) rather than
  only the count.
* **No escape hatch.** Every other hatch in this family (``# complexity-ok:
  <reason>``, ``lang:pt-ok``) exists because a real, hard-to-avoid case was found.
  None has surfaced here, and #424's own honest seam turned out to be
  whitespace-only vs content-changed, not an indivisible change — with 31 files of
  headroom before the vendor cap, the split is always available. Add a hatch only
  when a genuine indivisible case is found, per this repo's own one-implementation
  rule: build for a measured need, not a hypothetical one.
* **Reuses ``check_backlog_ledger.py``'s shape** (``templates/python-common/bin/``):
  diff the INDEX (``git diff --cached <merge-base>``) rather than the working tree
  or a single commit, so pre-commit sees staged content and CI (clean tree) reduces
  to the branch's cumulative diff. No-op on the default branch or off a feature
  branch with no divergence. CI needs ``fetch-depth: 0`` — a shallow clone has no
  merge-base to resolve.
"""

import subprocess
import sys


# CodeRabbit's own hard limit is 100 ("Review skipped: N files exceed the limit of
# 100"). This tracks THAT vendor limit, kept 10 below it — a PR that trips the vendor
# cap exactly is already too late to react to, the review has already failed. Named
# here rather than inlined in the message below, so a future vendor-limit change is
# one edit, not a grep-and-replace across every place the number appears.
MAX_CHANGED_FILES = 90


def _git(list_args: list) -> str:
    """Run a read-only git command and return stdout (empty string on failure).

    Parameters
    ----------
    list_args : list of str
        Arguments after ``git``.

    Returns
    -------
    str
        Captured stdout, stripped.
    """
    try:
        # Constant, trusted argv built in-process; no shell involved. S607 (partial
        # path) is resolution BY DESIGN — the hook must use the `git` the developer's
        # PATH selects, the one their shell, hooks and CI all use, not a hardcoded
        # path. Same precedent as check_backlog_ledger.py's identical helper.
        cls_proc = subprocess.run(  # noqa: S603
            ["git", *list_args],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    return cls_proc.stdout.strip()


def default_branch() -> str:
    """Return the repository's default branch name (``main``/``master``, else ``main``).

    Returns
    -------
    str
        The default branch name.
    """
    str_ref = _git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"])
    if str_ref:
        return str_ref.rsplit("/", 1)[-1]
    for str_candidate in ("main", "master"):
        if _git(["rev-parse", "--verify", "--quiet", str_candidate]):
            return str_candidate
    return "main"


def changed_file_count(str_base: str) -> int:
    """Return the branch's cumulative changed-file count, INDEX included.

    Parameters
    ----------
    str_base : str
        The merge-base commit to diff against.

    Returns
    -------
    int
        Number of changed paths.
    """
    str_out = _git(["diff", "--cached", "--name-only", str_base])
    return len([p for p in str_out.splitlines() if p])


def main() -> int:
    """Check the branch's cumulative diff against the file-count ceiling.

    Returns
    -------
    int
        0 when within the ceiling (or not applicable), 1 on a violation.
    """
    str_base = _git(["merge-base", "HEAD", default_branch()])
    str_head = _git(["rev-parse", "HEAD"])
    if not str_base or str_base == str_head:
        # On the default branch (or no merge-base): nothing branch-scoped to check.
        return 0

    int_count = changed_file_count(str_base)
    if int_count <= MAX_CHANGED_FILES:
        return 0

    print(
        f"❌ this branch changes {int_count} files, over the {MAX_CHANGED_FILES}-file "
        f"cap (blueprintx#551). CodeRabbit hard-refuses to review above 100 files, so "
        f"a PR this large can never merge. Split it at a natural seam (e.g. "
        f"whitespace-only vs content-changed, or by capability/tier) into PRs of "
        f"{MAX_CHANGED_FILES} files or fewer each."
    )
    return 1


if __name__ == "__main__":
    # Same Windows cp1252 guard as check_backlog_ledger.py: this backs an always_run
    # pre-commit hook, so a UnicodeEncodeError on the status glyphs would block every
    # commit from a Windows checkout rather than failing the branch under check.
    for cls_stream in (sys.stdout, sys.stderr):
        if hasattr(cls_stream, "reconfigure"):
            cls_stream.reconfigure(encoding="utf-8", errors="replace")

    sys.exit(main())
