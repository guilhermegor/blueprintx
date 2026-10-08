#!/bin/bash
# Should-fail regression tests for bin/check_orphan_pr_bodies.sh (blueprintx#657).
#
# One witness per outcome (MATCHED, ORPHAN, UNKNOWN) plus the exit-code contract. `gh` is a
# stub on PATH, so the suite needs no network: it prints the raw REST JSON in $STUB_GH_OUT (the
# script's own parsing runs over it), or fails if STUB_GH_FAIL is set.
#
# Usage: bash tests/test_check_orphan_pr_bodies.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/bin/check_orphan_pr_bodies.sh"

int_failures=0
str_tmp="$(mktemp -d)"
trap 'rm -rf "$str_tmp"' EXIT

mkdir -p "$str_tmp/bin" "$str_tmp/gitdir" "$str_tmp/norepo" "$str_tmp/plain"
cat > "$str_tmp/bin/gh" <<'STUB'
#!/bin/bash
[ -z "${STUB_GH_FAIL:-}" ] || { echo "HTTP 403: rate limit" >&2; exit 1; }
cat "$STUB_GH_OUT"
STUB
chmod +x "$str_tmp/bin/gh"

BODY_A="Adds the orphan scan so unopened PR bodies stop hiding measured findings."
BODY_B="A completely different body that no pull request on the forge ever carried."
TEMPLATE="## Description What Why How --- ## Changes Made Added Updated Fixed --- ## Testing"
CHECKLIST="Testing - [ ] CI checks pass and the orphan scan reports every unopened body found locally"

# forge_json <file> <num> <body> [<num> <body> ...]: raw REST-shaped JSON, one page.
forge_json() {
    local str_file="$1"
    shift
    python3 - "$str_file" "$@" <<'PY'
import json
import sys

list_args = sys.argv[2:]
list_items = [
    {"number": int(list_args[i]), "body": list_args[i + 1]} for i in range(0, len(list_args), 2)
]
open(sys.argv[1], "w").write(json.dumps(list_items))
PY
}
forge_json "$str_tmp/one.json" 561 "$BODY_A"
forge_json "$str_tmp/dup.json" 561 "$BODY_A" 562 "$BODY_A"
forge_json "$str_tmp/tmpl.json" 700 "$TEMPLATE"
forge_json "$str_tmp/ticked.json" 563 "${CHECKLIST/\[ \]/[x]}"
forge_json "$str_tmp/edited.json" 564 "${BODY_A/orphan/orfan}"
forge_json "$str_tmp/p1.json" 1 "unrelated"
forge_json "$str_tmp/p2.json" 561 "$BODY_A"
# --paginate concatenates one JSON array per page.
cat "$str_tmp/p1.json" "$str_tmp/p2.json" > "$str_tmp/paged.json"

# run_case <name> <want-exit> <want-substring> <body> [forge.json]
# Caller-set env: STUB_GH_FAIL, RUN_CWD (default the tmp dir), RUN_DIR (the script argument,
# default the fixture dir; empty means "no argument").
run_case() {
    local str_name="$1" int_want="$2" str_want="$3" str_body="$4" str_forge="${5:-one.json}"
    local str_out int_rc=0 list_arg=()
    rm -f "$str_tmp"/gitdir/*.md
    # Filename deliberately unrelated to the body: matching must read content.
    printf '%s\n' "$str_body" > "$str_tmp/gitdir/issue_rmw.md"
    [ -n "${RUN_DIR-$str_tmp/gitdir}" ] && list_arg=("${RUN_DIR-$str_tmp/gitdir}")
    str_out="$(cd "${RUN_CWD:-$str_tmp}" && PATH="$str_tmp/bin:$PATH" \
        STUB_GH_OUT="$str_tmp/$str_forge" bash "$SCRIPT" "${list_arg[@]}" 2>&1)" || int_rc=$?
    if [ "$int_rc" -ne "$int_want" ] || [[ "$str_out" != *"$str_want"* ]]; then
        echo "FAIL: $str_name (exit $int_rc, want $int_want; output: $str_out)" >&2
        int_failures=$((int_failures + 1))
    else
        echo "PASS: $str_name"
    fi
}

export BLUEPRINTX_REPO=o/r
run_case "matching body is MATCHED #N, exit 0" 0 "MATCHED #561" "$BODY_A"
run_case "reflowed whitespace still matches" 0 "MATCHED #561" "$(printf '%s' "$BODY_A" | tr ' ' '\n')"
run_case "non-breaking spaces normalise like ASCII ones" 0 "MATCHED #561" "${BODY_A// / }"
run_case "a page boundary does not hide a match" 0 "MATCHED #561" "$BODY_A" paged.json
run_case "unmatched body is ORPHAN, exit 1" 1 "ORPHAN" "$BODY_B"
run_case "ticked checkbox on the forge still matches" 0 "MATCHED #563" "$CHECKLIST" ticked.json
run_case "edited forge body is UNKNOWN, never ORPHAN" 2 "UNKNOWN (near #564" "$BODY_A" edited.json
run_case "unfilled-template forge body does not match a longer local body" 1 "ORPHAN" \
    "$TEMPLATE and then real content nobody ever published anywhere" tmpl.json
run_case "too-short body is UNKNOWN, exit 2" 2 "UNKNOWN" "tiny"
run_case "ambiguous match is UNKNOWN, exit 2" 2 "UNKNOWN (ambiguous: #561 #562)" "$BODY_A" dup.json
STUB_GH_FAIL=1 run_case "gh failure is UNKNOWN, exit 2" 2 "UNKNOWN" "$BODY_A"
RUN_DIR="$str_tmp/missing" run_case "nonexistent dir exits 2, not a silent green" 2 \
    "no such directory" "$BODY_A"

# git's own exit codes (1, 128) must not leak into the contract: a repo with no origin, and no repo.
git -C "$str_tmp/norepo" init -q
printf '%s\n' "$BODY_A" > "$str_tmp/norepo/.git/pr.md"
unset BLUEPRINTX_REPO
RUN_CWD="$str_tmp/norepo" RUN_DIR="" run_case "missing origin is UNKNOWN, exit 2" 2 "UNKNOWN" "$BODY_A"
GIT_CEILING_DIRECTORIES="$str_tmp" RUN_CWD="$str_tmp/plain" RUN_DIR="" run_case \
    "outside a repo exits 2" 2 "not inside a git repository" "$BODY_A"

if [ "$int_failures" -ne 0 ]; then
    echo "$int_failures case(s) failed" >&2
    exit 1
fi
