#!/bin/bash
# Should-fail regression tests for bin/check_orphan_pr_bodies.sh (blueprintx#657).
#
# One witness per outcome (MATCHED, ORPHAN, UNKNOWN) plus the exit-code contract. `gh` is a
# stub on PATH, so the suite needs no network: it prints $STUB_GH_OUT, or fails if
# STUB_GH_FAIL is set.
#
# Usage: bash tests/test_check_orphan_pr_bodies.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/bin/check_orphan_pr_bodies.sh"

int_failures=0
str_tmp="$(mktemp -d)"
trap 'rm -rf "$str_tmp"' EXIT

mkdir -p "$str_tmp/bin" "$str_tmp/gitdir"
cat > "$str_tmp/bin/gh" <<'EOF'
#!/bin/bash
[ -z "${STUB_GH_FAIL:-}" ] || { echo "HTTP 403: rate limit" >&2; exit 1; }
cat "$STUB_GH_OUT"
EOF
chmod +x "$str_tmp/bin/gh"

BODY_A="Adds the orphan scan so unopened PR bodies stop hiding measured findings."
BODY_B="A completely different body that no pull request on the forge ever carried."
printf '561\t%s\n' "$BODY_A" > "$str_tmp/forge.tsv"
printf '561\t%s\n562\t%s\n' "$BODY_A" "$BODY_A" > "$str_tmp/forge_dup.tsv"

# Usage: run_case <name> <want-exit> <want-substring> <body-file-content> [STUB_GH_FAIL=1]
run_case() {
    local str_name="$1" int_want="$2" str_want="$3" str_body="$4" str_fail="${5:-}" str_out int_rc=0 str_forge="${6:-forge.tsv}"
    rm -f "$str_tmp"/gitdir/*.md
    # Filename deliberately unrelated to the body: matching must read content.
    printf '%s\n' "$str_body" > "$str_tmp/gitdir/issue_rmw.md"
    str_out="$(PATH="$str_tmp/bin:$PATH" BLUEPRINTX_REPO=o/r STUB_GH_OUT="$str_tmp/$str_forge" \
        STUB_GH_FAIL="$str_fail" bash "$SCRIPT" "$str_tmp/gitdir" 2>/dev/null)" || int_rc=$?
    if [ "$int_rc" -ne "$int_want" ] || [[ "$str_out" != *"$str_want"* ]]; then
        echo "FAIL: $str_name (exit $int_rc, want $int_want; output: $str_out)" >&2
        int_failures=$((int_failures + 1))
    else
        echo "PASS: $str_name"
    fi
}

run_case "matching body is MATCHED #N, exit 0" 0 "MATCHED #561" "$BODY_A"
run_case "reflowed whitespace still matches by content" 0 "MATCHED #561" "$(printf '%s' "$BODY_A" | tr ' ' '\n')"
run_case "unmatched body is ORPHAN, exit 1" 1 "ORPHAN" "$BODY_B"
run_case "gh failure is UNKNOWN, exit 2" 2 "UNKNOWN" "$BODY_A" 1
run_case "too-short body is UNKNOWN, exit 2" 2 "UNKNOWN" "tiny"
run_case "ambiguous match is UNKNOWN, exit 2" 2 "UNKNOWN (ambiguous: #561 #562)" "$BODY_A" "" forge_dup.tsv

if [ "$int_failures" -ne 0 ]; then
    echo "$int_failures case(s) failed" >&2
    exit 1
fi
