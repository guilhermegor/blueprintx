#!/usr/bin/env bash

set -euo pipefail

SKELETON="${1:?skeleton name required}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
META="$REPO_ROOT/templates/$SKELETON/skeleton.meta"

[ -f "$META" ] || { echo "ERROR: skeleton '$SKELETON' not found" >&2; exit 1; }

str_language="$(grep '^language=' "$META" | cut -d= -f2-)"
if [ "$str_language" != "typescript" ]; then
    echo "Skipping '$SKELETON' - not a TypeScript skeleton (language=$str_language)."
    exit 0
fi

str_scaffold_rel="$(grep '^scaffold=' "$META" | cut -d= -f2-)"
[ -n "$str_scaffold_rel" ] || { echo "ERROR: no scaffold= in $META" >&2; exit 1; }

git config --global user.email >/dev/null 2>&1 || git config --global user.email "ci-bot@example.com"
git config --global user.name >/dev/null 2>&1 || git config --global user.name "ci-bot"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
PROJECT_NAME="ci-scaffold"
PROJECT_PATH="$WORK_DIR/$PROJECT_NAME"

echo "::group::Scaffold $SKELETON (offline, default answers)"
printf '\n%.0s' {1..80} \
    | BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot LINKEDIN_URL=https://www.linkedin.com/in/ci-bot \
        bash "$REPO_ROOT/$str_scaffold_rel" "$WORK_DIR" "$PROJECT_NAME" "CI scaffold jest" "0.0.1"
echo "::endgroup::"

if [ -n "${SCAFFOLD_TS_SABOTAGE:-}" ]; then
    str_victim="$(find "$PROJECT_PATH" -path '*/node_modules' -prune -o \( -name '*.test.ts' -o -name '*.test.tsx' \) -print | LC_ALL=C sort | head -1)"
    [ -n "$str_victim" ] || { echo "ERROR: no shipped jest test to sabotage" >&2; exit 1; }
    printf "\nit('sabotage', () => { expect(1).toBe(2); });\n" >>"$str_victim"
    echo "Sabotaged $str_victim"
fi

cd "$PROJECT_PATH"
npm ci --no-audit --no-fund
npm run lint
if [ "$SKELETON" = "react-spa-webpack" ]; then
    str_msg="test files may not use"
    list_bodies=(
        "/* eslint-disable */"
        "// eslint-disable-line"
        "it.skip('x', () => {}); // eslint-disable-line skip/require-issue"
        $'/*\n  eslint-disable\n*/'
    )
    for str_body in "${list_bodies[@]}"; do
        printf '%s\n' "$str_body" >src/zz-witness.test.ts
        int_rc=0
        str_out="$(bash bin/check_test_directives.sh . 2>&1)" || int_rc=$?
        if [ "$int_rc" -ne 1 ] || [[ "$str_out" != *"$str_msg"* ]]; then
            echo "ERROR: gate accepted (rc=$int_rc): $str_body" >&2
            exit 1
        fi
    done
    printf "it('x', () => {});\n" >src/zz-witness.test.ts
    npm run lint
    printf "/* eslint-disable */\nit.skip('x', () => {});\n" >src/zz-witness.test.ts
    str_out="$(npm run lint 2>&1)" && { echo "ERROR: lint accepted a block eslint-disable" >&2; exit 1; }
    if [[ "$str_out" != *"$str_msg"* ]]; then
        echo "ERROR: lint failed without running the test-directive gate" >&2
        exit 1
    fi
    printf "// eslint-disable-next-line skip/require-issue\n// eslint-disable-next-line jest/no-disabled-tests\nit.skip('x', () => {});\n" >src/zz-witness.test.ts
    str_out="$(npm run lint 2>&1)" && { echo "ERROR: lint accepted a chained next-line disable" >&2; exit 1; }
    if [[ "$str_out" != *"$str_msg"* ]]; then
        echo "ERROR: chained next-line disable was not rejected by the gate" >&2
        exit 1
    fi
    rm -f src/zz-witness.test.ts
fi
npm run lint:docs
npm test
echo "OK: $SKELETON scaffold passes npm ci, lint, lint:docs and jest."
