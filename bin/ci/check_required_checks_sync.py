#!/usr/bin/env python3
"""Fail when `main`'s required status checks and the PR jobs drift apart (blueprintx#535).

Default mode needs no token. It compares the committed expected contexts
(.github/required-checks.json, per layer) with the workflow jobs, both directions:

1. a REQUIRED context no unconditional PR job emits -> every PR waits forever;
2. an unconditional PR job that is neither required nor listed in the policy file -> a
   failing gate that cannot block a merge.

Policy data: bin/ci/required_checks_policy.txt, `kind|name|reason` per line, kind being
`optional` (deliberately not required) or `external` (required, emitted by an app or a
dynamic workflow that has no file here). A line without a reason is rejected.

`--live` compares the JSON with the live protection and ruleset API instead (needs admin
access; runs only on main). Unreadable API: fail with REQUIRED_CHECKS_SYNC_REQUIRED=1,
skip loudly otherwise. Explanation: docs/required-status-checks.md.
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


def job_flags(str_file: str, dict_job_map: dict, flag_wf: bool) -> dict:
    """{job id: unconditional}; a job that `needs` a conditional job is conditional too."""
    dict_flag = {}
    for str_id, dict_job in dict_job_map.items():
        if "uses" in dict_job:
            sys.exit(
                f"::error::{str_file}: reusable-workflow job '{str_id}' is unsupported; "
                "add its emitted check names to the policy file by hand"
            )
        dict_flag[str_id] = flag_wf and if_always_true(dict_job.get("if"))
    flag_changed = True
    while flag_changed:
        flag_changed = False
        for str_id, dict_job in dict_job_map.items():
            list_needs = dict_job.get("needs") or []
            list_needs = [list_needs] if isinstance(list_needs, str) else list_needs
            if dict_flag[str_id] and not all(
                dict_flag.get(n, False) for n in list_needs
            ):
                dict_flag[str_id] = False
                flag_changed = True
    return dict_flag


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
        dict_job_map = dict_wf.get("jobs") or {}
        dict_flag = job_flags(
            path_file.name, dict_job_map, pr_trigger_unfiltered(dict_on)
        )
        for str_id, dict_job in dict_job_map.items():
            for str_name in expand_name(str(dict_job.get("name", str_id)), dict_job):
                dict_jobs[str_name] = (
                    dict_jobs.get(str_name, False) or dict_flag[str_id]
                )
    return dict_jobs


def emitting_files(path_dir: pathlib.Path) -> dict:
    """{emitted name: {workflow file name}} over every workflow, whatever its trigger."""
    dict_files = {}
    for path_file in sorted(path_dir.glob("*.y*ml")):
        dict_wf = yaml.safe_load(path_file.read_text(encoding="utf-8")) or {}
        for str_id, dict_job in (dict_wf.get("jobs") or {}).items():
            if "uses" in dict_job:
                continue
            for str_name in expand_name(str(dict_job.get("name", str_id)), dict_job):
                dict_files.setdefault(str_name, set()).add(path_file.name)
    return dict_files


def inactive_emitters(set_req: set, dict_files: dict, dict_states: dict) -> list:
    """Required contexts whose emitting workflow file is not `active` in the Actions UI."""
    list_err = []
    for str_name in sorted(set_req & set(dict_files)):
        for str_file in sorted(dict_files[str_name]):
            str_state = dict_states.get(str_file, "missing")
            if str_state != "active":
                list_err.append(
                    f"required '{str_name}' is emitted by {str_file}, state {str_state}"
                )
    return list_err


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


def live_required() -> dict:
    """{"classic": set, "ruleset": set} read from the API (the rules in effect on main)."""
    dict_live = {
        "classic": set(
            gh_json(f"repos/{REPO}/branches/main/protection")["required_status_checks"][
                "contexts"
            ]
        ),
        "ruleset": set(),
    }
    for dict_rule in gh_json(f"repos/{REPO}/rules/branches/main"):
        if dict_rule["type"] == "required_status_checks":
            list_chk = dict_rule["parameters"]["required_status_checks"]
            dict_live["ruleset"] |= {c["context"] for c in list_chk}
    return dict_live


def live_workflow_states() -> dict:
    """{workflow file name: state} as the Actions API reports it."""
    dict_raw = gh_json(f"repos/{REPO}/actions/workflows?per_page=100")
    return {
        pathlib.PurePosixPath(w["path"]).name: w["state"] for w in dict_raw["workflows"]
    }


def read_expected(path_file: pathlib.Path) -> dict:
    """The committed {"classic": set, "ruleset": set}; any other shape aborts."""
    dict_raw = json.loads(path_file.read_text(encoding="utf-8"))
    if set(dict_raw) != {"classic", "ruleset"}:
        sys.exit(f"::error file={path_file}::need exactly the keys classic and ruleset")
    return {k: set(v) for k, v in dict_raw.items()}


def compare_live(dict_exp: dict, dict_live: dict) -> list:
    """Per layer, the contexts the JSON and the live settings disagree on."""
    list_err = []
    for str_layer in ("classic", "ruleset"):
        for str_name in sorted(dict_exp[str_layer] - dict_live[str_layer]):
            list_err.append(
                f"{str_layer}: in required-checks.json, not live: {str_name}"
            )
        for str_name in sorted(dict_live[str_layer] - dict_exp[str_layer]):
            list_err.append(
                f"{str_layer}: live, not in required-checks.json: {str_name}"
            )
    return list_err


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


def live_read() -> dict:
    """Live layers plus the workflow states, under one key each."""
    dict_live = live_required()
    dict_live["states"] = live_workflow_states()
    return dict_live


def read_or_skip(args) -> tuple:
    """(expected, live-or-None, exit code or None); the API is read only under --live."""
    try:
        if yaml is None:
            raise ValueError("PyYAML is not installed")
        dict_exp = read_expected(pathlib.Path(args.expected))
        return dict_exp, (live_read() if args.live else None), None
    except (OSError, subprocess.CalledProcessError, KeyError, ValueError) as exc:
        if os.environ.get("REQUIRED_CHECKS_SYNC_REQUIRED") == "1":
            print(f"::error::cannot read ({exc}); failing closed", file=sys.stderr)
            return None, None, 1
        print(f"SKIPPED (loudly): cannot read ({exc}). Nothing was checked.")
        return None, None, 0


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflows", default=".github/workflows")
    parser.add_argument("--policy", default="bin/ci/required_checks_policy.txt")
    parser.add_argument("--expected", default=".github/required-checks.json")
    parser.add_argument(
        "--live", action="store_true", help="compare the JSON with the API"
    )
    args = parser.parse_args()
    dict_exp, dict_live, int_rc = read_or_skip(args)
    if int_rc is not None:
        return int_rc
    if args.live:
        list_err = compare_live(dict_exp, dict_live) + inactive_emitters(
            dict_exp["classic"] | dict_exp["ruleset"],
            emitting_files(pathlib.Path(args.workflows)),
            dict_live["states"],
        )
    else:
        list_err = compare(
            dict_exp["classic"] | dict_exp["ruleset"],
            pr_jobs(pathlib.Path(args.workflows)),
            read_policy(pathlib.Path(args.policy)),
        )
    for str_msg in list_err:
        print(f"::error::{str_msg}", file=sys.stderr)
    print(f"findings={len(list_err)}")
    return 1 if list_err else 0


if __name__ == "__main__":
    sys.exit(main())
