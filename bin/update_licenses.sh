#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/logging.sh"

BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LICENSES_DIR="$BLUEPRINTX_ROOT/templates/licenses"
GITHUB_API="https://api.github.com/licenses"

# Map SPDX IDs to GitHub Licenses API keys (ordered for display)
SPDX_IDS=(MIT Apache-2.0 GPL-3.0 AGPL-3.0 LGPL-2.1 MPL-2.0 BSD-2-Clause BSD-3-Clause BSL-1.0 CC0-1.0 Unlicense)
declare -A LICENSE_KEYS=(
    ["MIT"]="mit"
    ["Apache-2.0"]="apache-2.0"
    ["GPL-3.0"]="gpl-3.0"
    ["AGPL-3.0"]="agpl-3.0"
    ["LGPL-2.1"]="lgpl-2.1"
    ["MPL-2.0"]="mpl-2.0"
    ["BSD-2-Clause"]="bsd-2-clause"
    ["BSD-3-Clause"]="bsd-3-clause"
    ["BSL-1.0"]="bsl-1.0"
    ["CC0-1.0"]="cc0-1.0"
    ["Unlicense"]="unlicense"
)

# The AGPL-3.0 closes the SaaS loophole: network use counts as distribution,
# so any service built on this code must also be released under the AGPL-3.0.
# This makes it ideal for dual-licensing — organisations that cannot comply
# (e.g. proprietary or commercial hosted services) must obtain a separate
# commercial license from the copyright holder.
AGPL_PREAMBLE="NOTE: This software is released under the GNU Affero General Public License v3.0.
This license is designed for a dual-licensing model: any software that uses this
code — including software delivered as a network service or API — must also be
released under the AGPL-3.0. Organisations that cannot comply with this requirement
must obtain a separate commercial license from the copyright holder.

───────────────────────────────────────────────────────────────────────────────

"

# ============================================================================
# FUNCTIONS
# ============================================================================

check_dependencies() {
    if ! command -v curl >/dev/null 2>&1; then
        exit_error "curl is required to fetch licenses."
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        exit_error "python3 is required for JSON parsing."
    fi
    print_status "success" "Dependencies OK (curl, python3)"
}

convert_placeholders() {
    sed \
        -e 's/\[year\]/${COPYRIGHT_YEAR}/g' \
        -e 's/\[fullname\]/${AUTHOR_NAME}/g' \
        -e 's/\[project\]/${PROJECT_NAME}/g'
}

fetch_body() {
    local key="$1"
    curl -fsSL \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "$GITHUB_API/$key" \
        | python3 -c "import sys, json; print(json.load(sys.stdin)['body'])" 2>/dev/null || true
}

write_license() {
    local spdx_id="$1"
    local key="${LICENSE_KEYS[$spdx_id]}"
    local out="$LICENSES_DIR/$spdx_id"

    local body
    body=$(fetch_body "$key")

    if [ -z "$body" ]; then
        print_status "warning" "$spdx_id — fetch failed, skipping"
        return 1
    fi

    if [ "$spdx_id" = "AGPL-3.0" ]; then
        { printf '%s' "$AGPL_PREAMBLE"; printf '%s\n' "$body"; } \
            | convert_placeholders > "$out"
    else
        printf '%s\n' "$body" | convert_placeholders > "$out"
    fi

    print_status "success" "$spdx_id"
}

update_all_licenses() {
    print_section "Updating license templates"
    print_status "config" "Target: $LICENSES_DIR"

    mkdir -p "$LICENSES_DIR"

    local failed=0
    for spdx_id in "${SPDX_IDS[@]}"; do
        write_license "$spdx_id" || failed=$((failed + 1))
    done

    if [ "$failed" -gt 0 ]; then
        print_status "warning" "$failed license(s) could not be updated — run again when network is available"
        exit 1
    fi

    print_status "success" "All ${#SPDX_IDS[@]} licenses updated"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    check_dependencies
    update_all_licenses
}

main
