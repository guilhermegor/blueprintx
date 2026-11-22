#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

int_failures=0

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

run_with_gh() {
    printf '#!/bin/bash\n%s\n' "$1" >"$str_stub_dir/gh"
    chmod +x "$str_stub_dir/gh"
    PATH="$str_stub_dir:$PATH" BLUEPRINTX_VERSION="$2" warn_if_outdated 2>&1
}

check "older install warns" "older than the latest release 4.8.8" "$(run_with_gh 'echo v4.8.8' 3.9.5)"
check "equal version is silent" "" "$(run_with_gh 'echo v4.8.8' 4.8.8)"
check "newer install is silent" "" "$(run_with_gh 'echo v4.8.8' 5.0.0)"
check "gh failure is silent" "" "$(run_with_gh 'exit 1' 3.9.5)"
check "dev checkout is silent" "" "$(run_with_gh 'echo v4.8.8' 0.0.0)"
check "empty answer is silent" "" "$(run_with_gh 'echo' 3.9.5)"

(( int_failures == 0 ))
