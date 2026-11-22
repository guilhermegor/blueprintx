"""PR quality gate — classify by changed PATH, label, comment once, hand safe PRs to auto-merge.

Runs on every `pull_request` event. It applies `risk:*` / `size:*` / `gate:*` labels, publishes ONE
sticky comment (updated in place via a hidden HTML marker, never stacked), and arms GitHub's
**native** auto-merge for the low-risk classes.

Three decisions carry this file:

**1. Auto-MERGE, never auto-APPROVE.** The ruleset sets `required_approving_review_count: 0` (it
must — GitHub forbids self-approval, so >= 1 locks a solo maintainer out), which makes a bot
approval worth nothing. Native auto-merge (GraphQL `enablePullRequestAutoMerge`, NOT
`PUT /pulls/:n/merge`) **bypasses nothing**: GitHub holds the merge until every required check of
the ruleset is green. So this script decides only **eligibility**; the *ruleset* decides whether it
passed. Never let a gate script judge check results and merge.

**2. Gate on the changed PATHS, never on diff size.** "Auto-merge if the diff is small" is
intuitive and **backwards** for contract-heavy code: the real failure mode is *semantic*. A
one-character change to a schema constant is the smallest possible diff and the most dangerous —
and every test still passes, because the tests assert the contract that was written. Size-gating
auto-merges precisely the changes that most need human eyes. See `RISK_PATHS`.

**3. Consent is opt-OUT.** The safe classes merge with **no label**; a `do-not-merge` label is the
escape hatch. Making a maintainer label every routine PR (Dependabot's weekly bumps included)
defeats the point of the automation.

Everything above the `main()` boundary is a **pure function** so the whole classifier is
unit-tested
offline with no network. Only `main()` touches the API.
"""

from fnmatch import fnmatchcase
import json
import os
import sys
import time
import urllib.error
import urllib.request


API = "https://api.github.com"

COMMENT_MARKER = "<!-- pr-quality-gate -->"

BLOCK_LABEL = "do-not-merge"

LOCKFILE = "poetry.lock"

RISK_ORDER = ("src", "tests", "other", "ci", "deps", "docs")

RISK_PATHS = {
    "src": ("src/",),
    "tests": ("tests/", "poe_tasks.toml", "poe_tasks.*.toml"),
    "ci": (".github/", "bin/", ".pre-commit-config.yaml"),
    "deps": ("pyproject.toml", LOCKFILE, "requirements.txt"),
    "docs": (
        "docs/",
        ".specs/backlog/",
        "mkdocs.yml",
        "README.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
    ),
}

AUTO_MERGEABLE = frozenset({"docs", "ci", "deps"})

SIZE_BUCKETS = (("XS", 10), ("S", 50), ("M", 200), ("L", 500))
SIZE_XL = "XL"

REQUIRED_AXES = frozenset({"tests"})
PAGE_SIZE = 100
PR_FILES_CAP = 3000


def classify_path(str_path: str) -> str:
    """Return the risk class of ONE path (``other`` when nothing matches).

    Parameters
    ----------
    str_path : str
        A repository-relative path from the PR's file list.

    Returns
    -------
    str
        One of ``RISK_ORDER``.
    """
    for str_class in RISK_ORDER:
        for str_rule in RISK_PATHS.get(str_class, ()):
            if str_rule.endswith("/"):
                if str_path.startswith(str_rule):
                    return str_class
            elif "*" in str_rule:
                if "/" not in str_path and fnmatchcase(str_path, str_rule):
                    return str_class
            elif str_path == str_rule:
                return str_class
    return "other"


def classify_risk(list_paths: list) -> str:
    """Return the MOST DANGEROUS risk class across every changed path.

    Parameters
    ----------
    list_paths : list of str
        Every path changed by the PR.

    Returns
    -------
    str
        The first class of ``RISK_ORDER`` present among the paths; ``docs`` for an empty list.

    Notes
    -----
    Callers asking *set membership* ("does ANY path fall in class X?") must call this **per path**,
    not on the whole list — collapsing to the single most-dangerous class answers a different
    question and silently lets a mixed branch escape a per-class requirement.
    """
    if not list_paths:
        return "docs"
    set_classes = {classify_path(p) for p in list_paths}
    for str_class in RISK_ORDER:
        if str_class in set_classes:
            return str_class
    return "other"


def classify_size(int_changed_lines: int) -> str:
    """Return the size bucket for a changed-line count.

    Parameters
    ----------
    int_changed_lines : int
        additions + deletions across the PR.

    Returns
    -------
    str
        ``XS`` / ``S`` / ``M`` / ``L`` / ``XL``.
    """
    for str_bucket, int_limit in SIZE_BUCKETS:
        if int_changed_lines <= int_limit:
            return str_bucket
    return SIZE_XL


def is_lockfile_only(list_paths: list) -> bool:
    """Return whether the diff touches the lockfile and nothing else.

    A size heuristic measures **nothing** on a machine-generated artifact: a regenerated lockfile's
    diff size tracks how many dependency hashes moved, not how much risk arrived. Three patch bumps
    can produce ~600 lines of ``sha256`` churn no human will read line-by-line, which would
    otherwise make "did the weekly bump self-merge?" depend on how many packages happened to move.

    Deliberately narrow — exempting the whole ``deps`` class would also exempt a hand-edited
    ``pyproject.toml`` range, the one file in that class where dependency risk is real.

    Parameters
    ----------
    list_paths : list of str
        Every path changed by the PR.

    Returns
    -------
    bool
        ``True`` when ``LOCKFILE`` is the only changed file.
    """
    return set(list_paths) == {LOCKFILE}


def is_auto_mergeable(
    str_risk: str, *, str_size: str, list_labels: list, bool_lockfile_only: bool = False
) -> bool:
    """Decide ELIGIBILITY for native auto-merge (never whether the checks passed).

    Parameters
    ----------
    str_risk : str
        The PR's risk class from :func:`classify_risk`.
    str_size : str
        The PR's size bucket from :func:`classify_size`.
    list_labels : list of str
        Labels currently on the PR.
    bool_lockfile_only : bool, optional
        From :func:`is_lockfile_only`; waives the XL veto only for a generated lockfile.

    Returns
    -------
    bool
        ``True`` when the PR may be handed to auto-merge.
    """
    if str_risk not in AUTO_MERGEABLE:
        return False
    if str_size == SIZE_XL and not bool_lockfile_only:
        return False
    return BLOCK_LABEL not in list_labels


def gate_state(dict_axes: dict) -> str:
    """Fold per-axis states into ONE display state: red > pending > green.

    A known failure is not still deciding, so a red axis outranks a pending one **for display**.

    ⚠️ Never use this to decide whether to stop polling — see :func:`axes_are_terminal`.

    Parameters
    ----------
    dict_axes : dict of {str: str}
        Axis name -> ``"success"`` / ``"failure"`` / ``"failing"`` / ``"pending"``.

    Returns
    -------
    str
        ``"failure"``, ``"pending"`` or ``"success"``.
    """
    if any(v in {"failure", "failing"} for v in dict_axes.values()):
        return "failure"
    if any(v == "pending" for v in dict_axes.values()):
        return "pending"
    return "success"


def axes_are_terminal(dict_axes: dict) -> bool:
    """Return whether EVERY axis has reached a terminal state (the only reason to stop polling).

    Kept separate from :func:`gate_state` on purpose. Breaking the poll loop on
    ``gate_state() != "pending"`` ends it on the **first transient red while other checks are still
    running** — and since the gate only re-runs on a push, nothing re-renders the comment: it stays
    "Blocked" forever on a PR that went green seconds later.

    Parameters
    ----------
    dict_axes : dict of {str: str}
        Axis name -> state; ``"failing"`` (red while a sibling run still runs) is not terminal.

    Returns
    -------
    bool
        ``True`` when no axis is still pending or failing.
    """
    return not any(v in {"pending", "failing", "absent"} for v in dict_axes.values())


def render_comment(
    str_risk: str, *, str_size: str, dict_axes: dict, bool_eligible: bool, dict_failing: dict
) -> str:
    """Render the sticky comment body (English — a contributor/machine-facing surface).

    The bot writes English even when the project's published docs are localized: the language
    boundary is the AUDIENCE, not the repository. Only published documentation follows the docs
    site's own language.

    Parameters
    ----------
    str_risk : str
        Risk class.
    str_size : str
        Size bucket.
    dict_axes : dict of {str: str}
        Axis name -> state.
    bool_eligible : bool
        Whether the PR is eligible for auto-merge.
    dict_failing : dict of {str: list}
        Axis name -> the NAMES of its failing checks.

    Returns
    -------
    str
        The full comment body, marker included.
    """
    dict_icon = {
        "success": "✅",
        "failure": "❌",
        "failing": "❌",
        "pending": "⏳",
        "absent": "➖",
    }
    list_rows = []
    for str_axis, str_state in sorted(dict_axes.items()):
        str_detail = ", ".join(f"`{n}`" for n in dict_failing.get(str_axis, [])) or "—"
        list_rows.append(
            f"| {str_axis} | {dict_icon.get(str_state, '?')} {str_state} | {str_detail} |"
        )

    str_verdict = (
        "🟢 **Eligible for auto-merge** — GitHub will merge once every required check is green."
        if bool_eligible
        else f"🔴 **Not auto-merging** — add `{BLOCK_LABEL}` to force this, or merge by hand."
    )
    return (
        f"{COMMENT_MARKER}\n"
        f"### PR quality gate\n\n"
        f"**risk:** `{str_risk}` · **size:** `{str_size}`\n\n"
        f"| axis | state | failing |\n|---|---|---|\n" + "\n".join(list_rows) + "\n\n"
        f"{str_verdict}\n"
    )


def _api(str_method: str, *, str_url: str, dict_payload: dict | None = None) -> object:
    """Call the GitHub REST API with the workflow token.

    Parameters
    ----------
    str_method : str
        HTTP method.
    str_url : str
        Absolute URL.
    dict_payload : dict, optional
        JSON body.

    Returns
    -------
    object
        Parsed JSON, or ``None`` on a 4xx/5xx (the gate degrades rather than failing the run).
    """
    bytes_body = json.dumps(dict_payload).encode() if dict_payload is not None else None
    cls_req = urllib.request.Request(str_url, data=bytes_body, method=str_method)  # noqa: S310
    cls_req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    cls_req.add_header("Accept", "application/vnd.github+json")
    if bytes_body:
        cls_req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(cls_req) as cls_resp:  # noqa: S310
            return json.loads(cls_resp.read() or "null")
    except urllib.error.HTTPError as cls_err:
        print(f"::warning::{str_method} {str_url} -> HTTP {cls_err.code}")
        return None


def _graphql(str_query: str, *, dict_vars: dict) -> object:
    """Call the GraphQL API (native auto-merge has no REST equivalent).

    ⚠️ GraphQL answers a REFUSED mutation with HTTP 200 and an ``errors`` array in the
    **body** — the HTTP-status check inside :func:`_api` never sees it. Discarding the return
    value here would make a rejected mutation a silent no-op: the log says the action was
    taken, nothing happened, and there is nothing to investigate.

    Parameters
    ----------
    str_query : str
        The GraphQL document.
    dict_vars : dict
        Query variables.

    Returns
    -------
    object
        Parsed JSON, or ``None`` on a transport error (from :func:`_api`).
    """
    dict_response = _api(
        "POST", str_url=f"{API}/graphql", dict_payload={"query": str_query, "variables": dict_vars}
    )
    list_errors = dict_response.get("errors") if isinstance(dict_response, dict) else None
    if list_errors:
        print(f"::warning::GraphQL mutation refused: {list_errors}", file=sys.stderr)
    return dict_response


def _enable_auto_merge(str_node_id: str, *, str_head_sha: str) -> str | None:
    """Arm GitHub's native auto-merge for one PR (see module docstring, decision 1).

    Arming is best-effort: a read-only token (a Dependabot-triggered run, or a repository whose
    default workflow permissions leave ``contents`` read-only) is refused with "Resource not
    accessible by integration". That is reported as a skip, never as a failed gate.

    Parameters
    ----------
    str_node_id : str
        The pull request's GraphQL node id.
    str_head_sha : str
        The head the checks were polled on; GitHub refuses the mutation if the head moved.

    Returns
    -------
    str or None
        ``None`` when armed; otherwise the reason it was skipped.
    """
    dict_response = _graphql(
        "mutation($id:ID!,$sha:GitObjectID){enablePullRequestAutoMerge(input:{pullRequestId:$id,"
        "expectedHeadOid:$sha,mergeMethod:SQUASH}){clientMutationId}}",
        dict_vars={"id": str_node_id, "sha": str_head_sha or None},
    )
    if not isinstance(dict_response, dict):
        return "the GraphQL request failed before GitHub answered"
    list_errors = dict_response.get("errors")
    if not list_errors:
        return None
    str_reason = "; ".join(str(d.get("message", d)) for d in list_errors if isinstance(d, dict))
    return str_reason or str(list_errors)


def _disable_auto_merge(str_node_id: str) -> str | None:
    """Disarm GitHub's native auto-merge for one PR (the ``do-not-merge`` opt-out).

    Parameters
    ----------
    str_node_id : str
        The pull request's GraphQL node id.

    Returns
    -------
    str or None
        ``None`` when disarmed; otherwise the reason it failed.
    """
    dict_response = _graphql(
        "mutation($id:ID!){disablePullRequestAutoMerge(input:{pullRequestId:$id})"
        "{clientMutationId}}",
        dict_vars={"id": str_node_id},
    )
    if not isinstance(dict_response, dict):
        return "the GraphQL request failed before GitHub answered"
    return str(dict_response["errors"]) if dict_response.get("errors") else None


def list_pr_files(str_repo: str, *, int_pr: int) -> list | None:
    """Read EVERY page of the PR's file list, or ``None`` when it cannot be read whole.

    A failed or truncated read is unknown, never an empty diff: ``[]`` classifies as ``docs``
    and would hand a ``src/`` change to auto-merge. GitHub lists at most ``PR_FILES_CAP``
    files, so a list that fills the cap may be missing paths and is treated as unreadable.

    Parameters
    ----------
    str_repo : str
        ``owner/name``.
    int_pr : int
        The pull request number.

    Returns
    -------
    list of dict or None
        Every file entry, or ``None`` on a failed or possibly-truncated read.
    """
    list_files: list = []
    for int_page in range(1, PR_FILES_CAP // PAGE_SIZE + 1):
        list_page = _api(
            "GET",
            str_url=f"{API}/repos/{str_repo}/pulls/{int_pr}/files"
            f"?per_page={PAGE_SIZE}&page={int_page}",
        )
        if not isinstance(list_page, list):
            return None
        list_files.extend(list_page)
        if len(list_page) < PAGE_SIZE:
            return list_files
    return None


def changed_paths(list_files: list) -> list:
    """Return every path a PR touches, including the SOURCE side of each rename.

    Parameters
    ----------
    list_files : list of dict
        Entries from :func:`list_pr_files`.

    Returns
    -------
    list of str
        ``filename`` plus ``previous_filename`` where GitHub reports one.
    """
    return [
        str_path
        for dict_file in list_files
        for str_path in (dict_file.get("filename"), dict_file.get("previous_filename"))
        if str_path
    ]


def _revision(dict_pr: dict) -> tuple:
    """Return the ``(head sha, base sha)`` pair a verdict is valid for.

    Parameters
    ----------
    dict_pr : dict
        The pull request payload.

    Returns
    -------
    tuple of str
        Head and base commit SHAs.
    """
    return (dict_pr.get("head") or {}).get("sha"), (dict_pr.get("base") or {}).get("sha")


def _is_dependabot(dict_pr: dict) -> bool:
    """Tell whether Dependabot opened the PR, so only ``dependabot-auto-merge.yml`` arms it.

    Parameters
    ----------
    dict_pr : dict
        The pull request payload.

    Returns
    -------
    bool
        ``True`` for a Dependabot-authored PR.
    """
    return (dict_pr.get("user") or {}).get("login") == "dependabot[bot]"


def _report_skip(str_reason: str | None) -> None:
    """Log a skipped auto-merge arming as a notice; do nothing when it was armed.

    Parameters
    ----------
    str_reason : str or None
        The skip reason from :func:`_enable_auto_merge`, or ``None`` when armed.

    Returns
    -------
    None
    """
    if str_reason:
        print(f"::notice::auto-merge not armed, step skipped: {str_reason}")


def collect_axes(list_check_runs: list, *, dict_axis_rules: dict) -> tuple:
    """Fold check-runs into per-axis states and the names of each axis's failing checks.

    ⚠️ Track the check that carries the real CONCLUSION, not an umbrella status. With CodeQL
    default setup the check literally named ``CodeQL`` is a ~2-second umbrella that flaps to
    non-success while awaiting a result for a new head SHA, while the ``Analyze (…)`` runs are the
    actual analyses — matching the umbrella makes the gate scream "failing" on a green PR.

    ⚠️ An axis with **no check-run yet** on this head SHA is ⏳ *awaiting a result*, never ❌.

    Parameters
    ----------
    list_check_runs : list of dict
        The ``check_runs`` array for the PR's head SHA.
    dict_axis_rules : dict of {str: tuple}
        Axis name -> name substrings identifying the checks that carry its conclusion.

    Returns
    -------
    tuple of (dict, dict)
        ``(axis -> state, axis -> [failing check names])``.
    """
    dict_axes, dict_failing = {}, {}
    for str_axis, tuple_matches in dict_axis_rules.items():
        list_mine = [
            r
            for r in list_check_runs
            if any(m.lower() in (r.get("name") or "").lower() for m in tuple_matches)
        ]
        if not list_mine:
            dict_axes[str_axis] = "pending" if str_axis in REQUIRED_AXES else "absent"
            continue
        list_failed = [
            r.get("name")
            for r in list_mine
            if r.get("status") == "completed"
            and r.get("conclusion") not in {"success", "neutral", "skipped"}
        ]
        bool_done = all(r.get("status") == "completed" for r in list_mine)
        dict_axes[str_axis] = {
            (True, True): "failure",
            (True, False): "failing",
            (False, True): "success",
            (False, False): "pending",
        }[(bool(list_failed), bool_done)]
        if list_failed:
            dict_failing[str_axis] = list_failed
    return dict_axes, dict_failing


def upsert_comment(str_repo: str, *, int_pr: int, str_body: str) -> None:
    """Create the sticky comment, or edit the existing one in place (never stack).

    Parameters
    ----------
    str_repo : str
        ``owner/repo``.
    int_pr : int
        PR number.
    str_body : str
        Rendered comment body (carries ``COMMENT_MARKER``).

    Returns
    -------
    None
    """
    list_comments = _api("GET", str_url=f"{API}/repos/{str_repo}/issues/{int_pr}/comments") or []
    for dict_comment in list_comments:
        if COMMENT_MARKER in (dict_comment.get("body") or ""):
            _api(
                "PATCH",
                str_url=f"{API}/repos/{str_repo}/issues/comments/{dict_comment['id']}",
                dict_payload={"body": str_body},
            )
            return
    _api(
        "POST",
        str_url=f"{API}/repos/{str_repo}/issues/{int_pr}/comments",
        dict_payload={"body": str_body},
    )


def poll_axes_until_terminal(
    str_repo: str, *, str_head_sha: str, int_max_polls: int, int_poll_seconds: int
) -> tuple[dict, dict]:
    """Poll the head commit's check runs until every axis reaches a terminal state.

    ⚠️ Stops ONLY when every axis is terminal — never on ``gate_state() != "pending"``,
    which would freeze the comment on the first transient red while other checks still run.

    A scaffold declares the axes it produces in ``GATE_AXES`` (comma-separated, e.g.
    ``tests,lint``); an undeclared axis is not polled, so one nothing produces no longer costs the
    whole budget. ``tests`` is always polled, and unset keeps every axis. A declared axis that has
    no check-run yet stays ``absent`` (non-terminal), because its producer may just be slow.

    Parameters
    ----------
    str_repo : str
        ``owner/name``.
    str_head_sha : str
        The PR head commit whose check runs are read.
    int_max_polls : int
        Maximum polls before giving up and reporting whatever was last seen.
    int_poll_seconds : int
        Seconds between polls.

    Returns
    -------
    tuple of dict
        ``(dict_axes, dict_failing)`` as returned by :func:`collect_axes`.
    """
    dict_axis_rules = {
        "tests": ("Run Automated Tests",),
        "lint": ("Ruff", "mypy", "lint"),
        "code scanning": ("Analyze",),
    }
    str_declared = os.environ.get("GATE_AXES", "").strip()
    if str_declared:
        set_declared = {s.strip() for s in str_declared.split(",")} | REQUIRED_AXES
        dict_axis_rules = {k: v for k, v in dict_axis_rules.items() if k in set_declared}

    int_max_polls = max(1, int_max_polls)

    dict_axes, dict_failing = {}, {}
    for int_attempt in range(int_max_polls):
        list_runs = (
            _api(
                "GET",
                str_url=f"{API}/repos/{str_repo}/commits/{str_head_sha}/check-runs?per_page=100",
            )
            or {}
        ).get("check_runs", [])
        dict_axes, dict_failing = collect_axes(list_runs, dict_axis_rules=dict_axis_rules)
        if axes_are_terminal(dict_axes):
            break
        if int_attempt < int_max_polls - 1:
            time.sleep(int_poll_seconds)
    return dict_axes, dict_failing


def sync_gate_labels(
    str_repo: str, *, int_pr: int, list_current: list, list_desired: list
) -> None:
    """Apply the desired risk/size/gate labels and drop the stale ones.

    Only the three families this gate owns are touched; any other label a human added
    survives untouched.

    Parameters
    ----------
    str_repo : str
        ``owner/name``.
    int_pr : int
        The pull request number.
    list_current : list of str
        Labels currently on the PR.
    list_desired : list of str
        The labels this run computed.
    """
    _api(
        "POST",
        str_url=f"{API}/repos/{str_repo}/issues/{int_pr}/labels",
        dict_payload={"labels": list_desired},
    )
    for str_stale in list_current:
        str_axis = str_stale.split(":", 1)[0]
        if str_axis in {"risk", "size", "gate"} and str_stale not in list_desired:
            _api("DELETE", str_url=f"{API}/repos/{str_repo}/issues/{int_pr}/labels/{str_stale}")


def reconcile_auto_merge(dict_pr: dict, *, bool_eligible: bool, list_labels: list) -> bool:
    """Disarm auto-merge when ``do-not-merge`` is present, else arm it for an eligible PR.

    GitHub keeps an armed auto-merge across label changes, so skipping the arm call alone
    leaves a request the opt-out label was meant to cancel.

    Parameters
    ----------
    dict_pr : dict
        The pull request payload read after polling (its ``auto_merge`` and head).
    bool_eligible : bool
        From :func:`is_auto_mergeable`.
    list_labels : list of str
        Labels currently on the PR.

    Returns
    -------
    bool
        ``False`` only when the opt-out label could not disarm an armed auto-merge; arming
        stays best-effort.
    """
    if BLOCK_LABEL in list_labels and dict_pr.get("auto_merge"):
        str_reason = _disable_auto_merge(dict_pr.get("node_id"))
        print(
            f"::error::{BLOCK_LABEL}: could not disarm auto-merge: {str_reason}"
            if str_reason
            else f"::notice::{BLOCK_LABEL}: auto-merge disarmed"
        )
        return not str_reason
    if bool_eligible and not _is_dependabot(dict_pr):
        str_head_sha = (dict_pr.get("head") or {}).get("sha", "")
        _report_skip(_enable_auto_merge(dict_pr.get("node_id"), str_head_sha=str_head_sha))
    return True


def _reread_same_revision(str_pr_url: str, *, dict_pr: dict, int_pr: int) -> dict | None:
    """Re-read the PR before publishing, or ``None`` when it is unreadable or has moved.

    Parameters
    ----------
    str_pr_url : str
        The PR's REST URL.
    dict_pr : dict
        The payload the verdict was computed from.
    int_pr : int
        The PR number, for the error annotation.

    Returns
    -------
    dict | None
        The fresh payload when its revision matches ``dict_pr``, else ``None``.
    """
    dict_now = _api("GET", str_url=str_pr_url)
    if not isinstance(dict_now, dict):
        print(f"::error::could not re-read PR #{int_pr} before publishing")
        return None
    if _revision(dict_now) != _revision(dict_pr):
        print(f"::error::PR #{int_pr} moved to a new revision while gated; re-run this job")
        return None
    return dict_now


def main() -> int:
    """Run the gate for one PR: classify, label, comment, and arm auto-merge when eligible.

    Returns
    -------
    int
        0 only when every polled axis is green. Nonzero when an axis is red, when an axis is
        still pending after the poll budget (a required check that passes while tests still
        run lets auto-merge land before they finish; re-run the job once they do), or when
        the PR or its file list cannot be read. "Classify and gate this PR" is a required
        status check (blueprintx#564, required-checks.txt), so this exit code is what the
        ruleset sees.
    """
    str_repo = os.environ["GITHUB_REPOSITORY"]
    int_pr = int(os.environ["PR_NUMBER"])

    str_pr_url = f"{API}/repos/{str_repo}/pulls/{int_pr}"
    dict_pr = _api("GET", str_url=str_pr_url)
    list_files = list_pr_files(str_repo, int_pr=int_pr) if isinstance(dict_pr, dict) else None
    if list_files is None:
        print(f"::error::could not read PR #{int_pr} or its complete file list; not classifying")
        return 1
    list_paths = changed_paths(list_files)

    str_risk = classify_risk(list_paths)
    str_size = classify_size(int(dict_pr.get("additions", 0)) + int(dict_pr.get("deletions", 0)))

    dict_axes, dict_failing = poll_axes_until_terminal(
        str_repo,
        str_head_sha=(dict_pr.get("head") or {}).get("sha", ""),
        int_max_polls=int(os.environ.get("GATE_MAX_POLLS", "26")),
        int_poll_seconds=int(os.environ.get("GATE_POLL_SECONDS", "30")),
    )

    dict_now = _reread_same_revision(str_pr_url, dict_pr=dict_pr, int_pr=int_pr)
    if dict_now is None:
        return 1

    list_labels = [lbl["name"] for lbl in dict_now.get("labels", [])]
    bool_eligible = is_auto_mergeable(
        str_risk,
        str_size=str_size,
        list_labels=list_labels,
        bool_lockfile_only=is_lockfile_only(list_paths),
    )
    bool_disarmed = reconcile_auto_merge(
        dict_now, bool_eligible=bool_eligible, list_labels=list_labels
    )

    sync_gate_labels(
        str_repo,
        int_pr=int_pr,
        list_current=list_labels,
        list_desired=[f"risk:{str_risk}", f"size:{str_size}", f"gate:{gate_state(dict_axes)}"],
    )

    upsert_comment(
        str_repo,
        int_pr=int_pr,
        str_body=render_comment(
            str_risk,
            str_size=str_size,
            dict_axes=dict_axes,
            bool_eligible=bool_eligible,
            dict_failing=dict_failing,
        ),
    )
    str_state = gate_state(dict_axes)
    print(f"risk={str_risk} size={str_size} eligible={bool_eligible} state={str_state}")
    return 0 if str_state == "success" and bool_disarmed else 1


if __name__ == "__main__":
    for cls_stream in (sys.stdout, sys.stderr):
        if hasattr(cls_stream, "reconfigure"):
            cls_stream.reconfigure(encoding="utf-8", errors="replace")

    sys.exit(main())
