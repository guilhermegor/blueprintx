#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
int_failures=0

CASE_NAMES=(
    "ladder review on head passes"
    "ladder row is posts threads"
    "marker poster names the ladder"
    "same review fails with the row removed"
    "User-typed review with the bare login is rejected"
    "Bot-typed review with the ladder login is accepted"
    "User-typed PR author with the bare login is not exempt"
    "Bot-typed PR author with the ladder login is exempt"
)

harness_setup() {
    cat <<'PY'
import importlib.util
import os
import pathlib
import shutil
import sys
import tempfile

path_repo, str_roster, int_case = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
path_gate = path_repo / "templates" / "common" / "bin" / "check_review_threads.py"
cls_spec = importlib.util.spec_from_file_location("gate", path_gate)
cls_gate = importlib.util.module_from_spec(cls_spec)
cls_spec.loader.exec_module(cls_gate)

str_app = "guilhermegor-review-ladder"
str_head = "9ae76ab0000000000000000000000000000000000"
str_key = cls_gate.normalise_login(str_app)

path_tmp = pathlib.Path(tempfile.mkdtemp())
shutil.copy(path_repo / str_roster, path_tmp / ".review-bots.yaml")
os.chdir(path_tmp)
dict_roster = cls_gate.load_roster(path_tmp)
set_posters = cls_gate.load_marker_posters(path_tmp)
PY
}

harness_cases() {
    cat <<'PY'
def review(str_login, str_type):
    return {
        "author": {"login": str_login, "__typename": str_type},
        "commit": {"oid": str_head},
        "state": "COMMENTED",
    }


def missing(list_reviews, dict_roster_used=None):
    dict_use = dict_roster if dict_roster_used is None else dict_roster_used
    return cls_gate.find_missing_review_problem(
        list_reviews, cls_gate.reviewer_logins(dict_use), "someone", str_head_oid=str_head
    )


def fetched(list_reviews):
    dict_page = {"pageInfo": {"hasNextPage": False, "endCursor": None}}
    dict_pr = {
        "reviews": {**dict_page, "nodes": list_reviews},
        "reviewThreads": {**dict_page, "nodes": []},
        "comments": {**dict_page, "nodes": []},
    }
    cls_gate._fetch_page = lambda *args: dict_pr
    return cls_gate.fetch_pull_request("o", "r", 1)["reviews"]["nodes"]


def author_problem(str_type):
    dict_pr = {
        "author": {"login": str_app, "__typename": str_type},
        "headRefOid": str_head,
        "reviews": {"nodes": []},
        "comments": {"nodes": []},
    }
    return cls_gate._missing_review(dict_pr, "o/r", cls_gate.reviewer_logins(dict_roster))[0]


def without_row():
    return {k: v for k, v in dict_roster.items() if k != str_key}


LIST_CASES = [
    lambda: missing([review(str_app + "[bot]", "Bot")]) is None,
    lambda: dict_roster.get(str_key) == "threads",
    lambda: str_key in set_posters,
    lambda: missing([review(str_app + "[bot]", "Bot")], without_row()) is not None,
    lambda: missing(fetched([review(str_app, "User")])) is not None,
    lambda: missing(fetched([review(str_app + "[bot]", "Bot")])) is None,
    lambda: author_problem("User") is not None,
    lambda: author_problem("Bot") is None,
]
sys.exit(0 if LIST_CASES[int_case]() else 1)
PY
}

run_case() {
    local str_roster="$1" int_case="$2"
    python3 - "$REPO_ROOT" "$str_roster" "$int_case" < <(harness_setup; harness_cases)
}

main() {
    local str_roster int_case
    for str_roster in templates/python-common/.review-bots.yaml templates/ts-common/.github/.review-bots.yaml; do
        for int_case in "${!CASE_NAMES[@]}"; do
            if run_case "$str_roster" "$int_case"; then
                echo "ok: $str_roster: ${CASE_NAMES[$int_case]}"
            else
                echo "FAIL: $str_roster: ${CASE_NAMES[$int_case]}" >&2
                int_failures=$((int_failures + 1))
            fi
        done
    done
    if [ "$int_failures" -ne 0 ]; then
        echo "$int_failures failure(s)" >&2
        exit 1
    fi
    echo "all passed"
}

main "$@"
