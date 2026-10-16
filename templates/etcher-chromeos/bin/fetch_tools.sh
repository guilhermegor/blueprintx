#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$PROJECT_ROOT/lib/common.sh"
# shellcheck source=lib/verify.sh
source "$PROJECT_ROOT/lib/verify.sh"
TOOLS_DIR="${CROS_TOOLS_DIR:-$PROJECT_ROOT/.tools}"
ETCHER_API="${CROS_ETCHER_API:-https://api.github.com/repos/balena-io/etcher/releases/latest}"
WORK_DIR=""
trap 'rm -rf "$WORK_DIR"' EXIT
RE_TAG='^v?[0-9]+(\.[0-9]+)*$'
RE_NAME='^[A-Za-z0-9._-]+$'

fetch() {
    curl --proto '=https' --tlsv1.2 -fsSL --retry 3 -o "$1" "$2"
}

require_opt_in() {
    if [ "${ALLOW_UNSIGNED_DOWNLOAD:-0}" != 1 ]; then
        print_status "error" "$1 would be downloaded from GitHub; rerun with ALLOW_UNSIGNED_DOWNLOAD=1 (make tools ALLOW_UNSIGNED_DOWNLOAD=1) to accept that"
        return 1
    fi
    print_status "warning" "integrity is only a same-origin digest from the release that serves the file, not publisher-attested"
}

json_field() {
    python3 -I -c '
import json, sys

d = json.load(open(sys.argv[1]))
for k in sys.argv[2:]:
    d = d[k]
print(d)
' "$@"
}

fetch_bmaptool() {
    if command -v bmaptool >/dev/null 2>&1; then
        print_status "success" "bmaptool already installed: $(command -v bmaptool)"
        return 0
    fi
    print_status "info" "bmaptool is not installed. Install it from your distro: apt install bmap-tools | dnf install bmap-tools"
    print_status "info" "Without it, flashing falls back to dd, which needs nothing."
}

fetch_etcher() {
    local str_work str_tag str_zip str_base str_sum
    require_opt_in balenaEtcher
    mkdir -p "$TOOLS_DIR"
    str_work="$(mktemp -d "$TOOLS_DIR/etcher.XXXXXX")"
    WORK_DIR="$str_work"
    fetch "$str_work/release.json" "$ETCHER_API"
    str_tag="$(json_field "$str_work/release.json" tag_name)"
    str_zip="balenaEtcher-linux-x64-${str_tag#v}.zip"
    if [[ ! "$str_tag" =~ $RE_TAG ]] || [[ ! "$str_zip" =~ $RE_NAME ]]; then
        print_status "error" "unexpected balenaEtcher tag '$str_tag'; refusing to build a URL from it"
        return 1
    fi
    str_base="https://github.com/balena-io/etcher/releases/download/$str_tag"
    fetch "$str_work/$str_zip" "$str_base/$str_zip"
    fetch "$str_work/SHA256SUMS.Linux.x64.txt" "$str_base/SHA256SUMS.Linux.x64.txt"
    str_sum="$(awk -v n="$str_zip" '$2 == n { print $1 }' "$str_work/SHA256SUMS.Linux.x64.txt")"
    if [ -z "$str_sum" ]; then
        print_status "error" "no exact SHA256SUMS line for $str_zip"
        return 1
    fi
    verify_hash sha256 "$str_sum" "$str_work/$str_zip"
    rm -rf "$TOOLS_DIR/etcher"
    mkdir "$TOOLS_DIR/etcher"
    unzip -o -q -d "$TOOLS_DIR/etcher" "$str_work/$str_zip"
    print_status "success" "balenaEtcher $str_tag -> $TOOLS_DIR/etcher (GUI; flash with it manually)"
}

main() {
    local str_what="bmaptool"
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --allow-github-digest) ALLOW_UNSIGNED_DOWNLOAD=1 ;;
            *) str_what="$1" ;;
        esac
        shift
    done
    case "$str_what" in
        bmaptool) fetch_bmaptool ;;
        etcher) fetch_etcher ;;
        *)
            print_status "error" "Usage: $0 [--allow-github-digest] [bmaptool|etcher]"
            return 1
            ;;
    esac
}

main "$@"
