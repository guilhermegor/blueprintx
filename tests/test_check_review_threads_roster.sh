#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
int_failures=0

run_case() {
    local str_desc="$1" str_roster="$2" str_want="$3" str_got
    str_got="$(python3 - "$REPO_ROOT" "$str_roster" "$str_want" <<'PY'
import importlib.util
import pathlib
import shutil
import sys
import tempfile

path_repo, str_roster, str_variant = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
path_gate = path_repo / "templates" / "common" / "bin" / "check_review_threads.py"
cls_spec = importlib.util.spec_from_file_location("gate", path_gate)
cls_gate = importlib.util.module_from_spec(cls_spec)
cls_spec.loader.exec_module(cls_gate)

str_ladder = "guilhermegor-review-ladder[bot]"
str_head = "9ae76ab0000000000000000000000000000000000"
list_reviews = [{"author": {"login": str_ladder}, "commit": {"oid": str_head}, "state": "COMMENTED"}]

with tempfile.TemporaryDirectory() as str_tmp:
    shutil.copy(path_repo / str_roster, pathlib.Path(str_tmp) / ".review-bots.yaml")
    dict_roster = cls_gate.load_roster(pathlib.Path(str_tmp))
    set_posters = cls_gate.load_marker_posters(pathlib.Path(str_tmp))

str_key = cls_gate.normalise_login(str_ladder)
if str_variant == "poster":
    print("pass" if str_key in set_posters else "fail")
elif str_variant == "threads":
    print("pass" if dict_roster.get(str_key) == "threads" else "fail")
else:
    if str_variant == "row_removed":
        dict_roster.pop(str_key, None)
    str_problem = cls_gate.find_missing_review_problem(
        list_reviews, cls_gate.reviewer_logins(dict_roster), "someone", str_head_oid=str_head
    )
    bool_want_problem = str_variant == "row_removed"
    print("pass" if (str_problem is not None) == bool_want_problem else "fail")
PY
)" || str_got="error"
    if [ "$str_got" = "pass" ]; then
        echo "ok: $str_desc"
    else
        echo "FAIL: $str_desc -> $str_got" >&2
        int_failures=$((int_failures + 1))
    fi
}

for str_roster in templates/python-common/.review-bots.yaml templates/ts-common/.github/.review-bots.yaml; do
    run_case "$str_roster: ladder review on head passes" "$str_roster" review
    run_case "$str_roster: ladder row is posts threads" "$str_roster" threads
    run_case "$str_roster: marker poster names the ladder" "$str_roster" poster
    run_case "$str_roster: same review fails with the row removed" "$str_roster" row_removed
done

if [ "$int_failures" -ne 0 ]; then
    echo "$int_failures failure(s)" >&2
    exit 1
fi
echo "all passed"
