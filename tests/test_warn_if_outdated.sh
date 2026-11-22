#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

int_failures=0
str_latest_json='{"tag_name": "v4.8.8"}'

check() {
    local str_name="$1" str_want="$2" str_got="$3"
    if [[ -z "$str_want" && -z "$str_got" ]] || [[ -n "$str_want" && "$str_got" == *"$str_want"* ]]; then
        print_status "success" "PASS: $str_name"
    else
        print_status "error" "FAIL: $str_name (want '$str_want', got '$str_got')"
        int_failures=$((int_failures + 1))
    fi
}

str_stub_dir="$(mktemp -d)"
trap 'rm -rf "$str_stub_dir"' EXIT

run_with_curl() {
    printf '#!/bin/bash\n%s\n' "$1" >"$str_stub_dir/curl"
    chmod +x "$str_stub_dir/curl"
    PATH="$str_stub_dir:$PATH" BLUEPRINTX_VERSION="$2" warn_if_outdated 2>&1
}

check "older install warns" "older than the latest release 4.8.8" "$(run_with_curl "echo '$str_latest_json'" 3.9.5)"
check "equal version is silent" "" "$(run_with_curl "echo '$str_latest_json'" 4.8.8)"
check "newer install is silent" "" "$(run_with_curl "echo '$str_latest_json'" 5.0.0)"
check "prerelease install is silent" "" "$(run_with_curl "echo '$str_latest_json'" 4.8.8-rc.1)"
check "curl failure is silent" "" "$(run_with_curl 'exit 22' 3.9.5)"
check "dev checkout is silent" "" "$(run_with_curl "echo '$str_latest_json'" 0.0.0)"
check "empty answer is silent" "" "$(run_with_curl 'echo' 3.9.5)"
check "opt-out is silent" "" "$(BLUEPRINTX_NO_UPDATE_CHECK=1 run_with_curl "echo '$str_latest_json'" 3.9.5)"
check "curl absent is silent" "" "$(PATH="$str_stub_dir/none" BLUEPRINTX_VERSION=3.9.5 warn_if_outdated 2>&1)"

(( int_failures == 0 ))
