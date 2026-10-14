#!/usr/bin/env python3
"""Fail when `main`'s required status checks and the PR jobs drift apart (blueprintx#535).

Two directions, both read from live settings (classic branch protection + active rulesets):

1. a REQUIRED context no unconditional PR job emits -> every PR waits forever;
2. an unconditional PR job that is neither required nor listed in the policy file -> a
   failing gate that cannot block a merge.

Policy data: bin/ci/required_checks_policy.txt, `kind|name|reason` per line, kind being
`optional` (deliberately not required) or `external` (required, emitted by an app or a
dynamic workflow that has no file here). A line without a reason is rejected.

Reading protection needs Administration access, so with no readable API: fail in CI
(REQUIRED_CHECKS_SYNC_REQUIRED=1), skip loudly elsewhere. Explanation: docs/required-status-checks.md.
"""

import argparse
import itertools
import json
import os
import pathlib
import re
import subprocess
import sys

try:
    import yaml
except ImportError:
    yaml = None

REPO = "guilhermegor/blueprintx"
PR_TYPES = {"opened", "reopened", "synchronize"}
FILTERS = ("branches", "branches-ignore", "paths", "paths-ignore")
RE_EVENT_CLAUSE = re.compile(r"^github\.event_name\s*(==|!=)\s*'([a-z_]+)'$")


def event_clause_true(str_clause: str) -> bool:
    """Whether a bare `github.event_name ==/!= 'x'` clause holds for a pull_request event."""
    match = RE_EVENT_CLAUSE.match(str_clause.strip())
    if not match:
        return False
    return (match.group(2) == "pull_request") == (match.group(1) == "==")


def if_always_true(str_if) -> bool:
    """A job `if:` is harmless only if some `||` alternative is a true event_name test."""
    if str_if is None:
        return True
    return any(event_clause_true(c) for c in str(str_if).split("||"))


def pr_trigger_unfiltered(dict_on) -> bool:
    """`pull_request` with no branch/path filter and a `types:` that covers new pushes."""
    if not isinstance(dict_on, dict) or "pull_request" not in dict_on:
        return False
    dict_pr = dict_on["pull_request"] or {}
    if any(k in dict_pr for k in FILTERS):
        return False
    return "types" not in dict_pr or PR_TYPES <= set(dict_pr["types"])


def expand_name(str_name: str, dict_job: dict) -> list:
    """Interpolate `${{ matrix.<k> }}` over the job's matrix; fail on include/exclude."""
    dict_matrix = (dict_job.get("strategy") or {}).get("matrix") or {}
    if "${{" not in str_name:
        return [str_name]
    if "include" in dict_matrix or "exclude" in dict_matrix:
        sys.exit(
            f"::error::matrix include/exclude in job '{str_name}' is not expandable"
        )
    list_keys = [k for k, v in dict_matrix.items() if isinstance(v, list)]
    list_names = []
    for tuple_vals in itertools.product(*(dict_matrix[k] for k in list_keys)):
        str_out = str_name
        for str_key, str_val in zip(list_keys, tuple_vals):
            str_out = re.sub(
                r"\$\{\{\s*matrix\.%s\s*\}\}" % re.escape(str_key),
                str(str_val),
                str_out,
            )
        list_names.append(str_out)
    return list_names


def pr_jobs(path_dir: pathlib.Path) -> dict:
    """{emitted name: True if it runs unconditionally on every PR} over every workflow."""
    dict_jobs = {}
    for path_file in sorted(path_dir.glob("*.y*ml")):
        dict_wf = yaml.safe_load(path_file.read_text(encoding="utf-8")) or {}
        dict_on = dict_wf.get("on", dict_wf.get(True))
        if isinstance(dict_on, str):
            dict_on = {dict_on: None}
        elif isinstance(dict_on, list):
            dict_on = dict.fromkeys(dict_on)
        if not isinstance(dict_on, dict) or "pull_request" not in dict_on:
            continue
        flag_wf = pr_trigger_unfiltered(dict_on)
        for str_id, dict_job in (dict_wf.get("jobs") or {}).items():
            if "uses" in dict_job:
                continue
            flag = flag_wf and if_always_true(dict_job.get("if"))
            for str_name in expand_name(str(dict_job.get("name", str_id)), dict_job):
                dict_jobs[str_name] = dict_jobs.get(str_name, False) or flag
    return dict_jobs


def read_policy(path_file: pathlib.Path) -> dict:
    """{kind: {name: reason}}; a malformed or reason-less line aborts."""
    dict_policy = {"optional": {}, "external": {}}
    for int_no, str_line in enumerate(
        path_file.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not str_line.strip() or str_line.lstrip().startswith("#"):
            continue
        list_parts = [p.strip() for p in str_line.split("|", 2)]
        if (
            len(list_parts) != 3
            or list_parts[0] not in dict_policy
            or not list_parts[2]
        ):
            sys.exit(
                f"::error file={path_file},line={int_no}::need `optional|external|name|reason`"
            )
        dict_policy[list_parts[0]][list_parts[1]] = list_parts[2]
    return dict_policy


def gh_json(str_path: str):
    str_out = subprocess.run(
        ["gh", "api", str_path], capture_output=True, text=True, check=True
    ).stdout
    return json.loads(str_out)


def live_required() -> set:
    """Contexts from classic protection plus every active ruleset on the default branch."""
    set_ctx = set(
        gh_json(f"repos/{REPO}/branches/main/protection")["required_status_checks"][
            "contexts"
        ]
    )
    for dict_rs in gh_json(f"repos/{REPO}/rulesets"):
        if dict_rs.get("enforcement") != "active":
            continue
        for dict_rule in gh_json(f"repos/{REPO}/rulesets/{dict_rs['id']}")["rules"]:
            if dict_rule["type"] == "required_status_checks":
                list_chk = dict_rule["parameters"]["required_status_checks"]
                set_ctx |= {c["context"] for c in list_chk}
    return set_ctx


def compare(set_req: set, dict_jobs: dict, dict_policy: dict) -> list:
    """Every finding, as a message; empty means in sync."""
    list_err = []
    set_always = {n for n, f in dict_jobs.items() if f}
    for str_name in sorted(set_req - set_always - set(dict_policy["external"])):
        list_err.append(f"required but no unconditional PR job emits it: {str_name}")
    for str_name in sorted(set_always - set_req - set(dict_policy["optional"])):
        list_err.append(
            f"runs on every PR, not required, not in the policy file: {str_name}"
        )
    for str_name in sorted(set(dict_policy["optional"]) - set_always):
        list_err.append(
            f"policy `optional` entry names no unconditional PR job: {str_name}"
        )
    for str_name in sorted(set(dict_policy["external"]) - set_req):
        list_err.append(f"policy `external` entry is not required: {str_name}")
    return list_err


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflows", default=".github/workflows")
    parser.add_argument("--policy", default="bin/ci/required_checks_policy.txt")
    parser.add_argument(
        "--required-file", help="JSON list of contexts; replaces the API read (tests)"
    )
    args = parser.parse_args()
    try:
        if yaml is None:
            raise ValueError("PyYAML is not installed")
        if args.required_file:
            set_req = set(
                json.loads(pathlib.Path(args.required_file).read_text(encoding="utf-8"))
            )
        else:
            set_req = live_required()
    except (OSError, subprocess.CalledProcessError, KeyError, ValueError) as exc:
        if os.environ.get("REQUIRED_CHECKS_SYNC_REQUIRED") == "1":
            print(
                f"::error::cannot read branch protection ({exc}); failing closed",
                file=sys.stderr,
            )
            return 1
        print(
            f"SKIPPED (loudly): cannot read branch protection ({exc}). Nothing was checked."
        )
        return 0
    list_err = compare(
        set_req,
        pr_jobs(pathlib.Path(args.workflows)),
        read_policy(pathlib.Path(args.policy)),
    )
    for str_msg in list_err:
        print(f"::error::{str_msg}", file=sys.stderr)
    print(f"required={len(set_req)} findings={len(list_err)}")
    return 1 if list_err else 0


if __name__ == "__main__":
    sys.exit(main())
