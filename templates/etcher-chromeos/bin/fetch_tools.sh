#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$PROJECT_ROOT/lib/common.sh"
# shellcheck source=lib/verify.sh
source "$PROJECT_ROOT/lib/verify.sh"
TOOLS_DIR="${CROS_TOOLS_DIR:-$PROJECT_ROOT/.tools}"
BMAPTOOL_API="${CROS_BMAPTOOL_API:-https://api.github.com/repos/yoctoproject/bmaptool/releases/latest}"
ETCHER_API="${CROS_ETCHER_API:-https://api.github.com/repos/balena-io/etcher/releases/latest}"
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

bmaptool_asset() {
    python3 -I -c '
import json, sys

for a in json.load(open(sys.argv[1])).get("assets", []):
    if a["name"].endswith(".tar.gz") and (a.get("digest") or "").startswith("sha256:"):
        print(a["name"], a["browser_download_url"], a["digest"][7:])
        break
' "$1"
}

fetch_bmaptool() {
    local str_json str_name="" str_url="" str_digest="" str_tag str_work str_src
    if command -v bmaptool >/dev/null 2>&1; then
        print_status "success" "bmaptool already installed: $(command -v bmaptool)"
        return 0
    fi
    if [ "${ALLOW_UNSIGNED_DOWNLOAD:-0}" != 1 ]; then
        print_status "info" "bmaptool is not installed. Install it from your distro: apt install bmap-tools | dnf install bmap-tools"
        print_status "info" "Without it, flashing falls back to dd, which needs nothing."
        return 0
    fi
    require_opt_in bmaptool
    mkdir -p "$TOOLS_DIR/bin"
    str_work="$(mktemp -d "$TOOLS_DIR/bmaptool.XXXXXX")"
    str_json="$str_work/release.json"
    fetch "$str_json" "$BMAPTOOL_API"
    str_tag="$(json_field "$str_json" tag_name)"
    read -r str_name str_url str_digest < <(bmaptool_asset "$str_json") || true
    if [[ ! "$str_tag" =~ $RE_TAG ]] || [[ ! "$str_name" =~ $RE_NAME ]] || [ -z "$str_digest" ]; then
        print_status "error" "latest bmaptool release has no usable .tar.gz asset with a GitHub sha256 digest (tag '$str_tag'); install bmaptool from your distro or use --tool dd"
        rm -rf "$str_work"
        return 1
    fi
    fetch "$str_work/$str_name" "$str_url"
    verify_hash sha256 "$str_digest" "$str_work/$str_name"
    mkdir "$str_work/src"
    tar -xzf "$str_work/$str_name" -C "$str_work/src"
    str_src="$(find "$str_work/src" -mindepth 2 -maxdepth 2 -type d -name src | head -n1)"
    rm -rf "$TOOLS_DIR/bmaptool"
    mv "$(dirname "$str_src")" "$TOOLS_DIR/bmaptool"
    printf '#!/usr/bin/env bash\nPYTHONPATH="%s" exec python3 -m bmaptool "$@"\n' "$TOOLS_DIR/bmaptool/src" >"$TOOLS_DIR/bin/bmaptool"
    chmod +x "$TOOLS_DIR/bin/bmaptool"
    rm -rf "$str_work"
    print_status "success" "bmaptool $str_tag -> $TOOLS_DIR/bin/bmaptool"
}

fetch_etcher() {
    local str_work str_tag str_zip str_base str_sum
    require_opt_in balenaEtcher
    mkdir -p "$TOOLS_DIR"
    str_work="$(mktemp -d "$TOOLS_DIR/etcher.XXXXXX")"
    fetch "$str_work/release.json" "$ETCHER_API"
    str_tag="$(json_field "$str_work/release.json" tag_name)"
    str_zip="balenaEtcher-linux-x64-${str_tag#v}.zip"
    if [[ ! "$str_tag" =~ $RE_TAG ]] || [[ ! "$str_zip" =~ $RE_NAME ]]; then
        print_status "error" "unexpected balenaEtcher tag '$str_tag'; refusing to build a URL from it"
        rm -rf "$str_work"
        return 1
    fi
    str_base="https://github.com/balena-io/etcher/releases/download/$str_tag"
    fetch "$str_work/$str_zip" "$str_base/$str_zip"
    fetch "$str_work/SHA256SUMS.Linux.x64.txt" "$str_base/SHA256SUMS.Linux.x64.txt"
    str_sum="$(awk -v n="$str_zip" '$2 == n { print $1 }' "$str_work/SHA256SUMS.Linux.x64.txt")"
    if [ -z "$str_sum" ]; then
        print_status "error" "no exact SHA256SUMS line for $str_zip"
        rm -rf "$str_work"
        return 1
    fi
    verify_hash sha256 "$str_sum" "$str_work/$str_zip"
    rm -rf "$TOOLS_DIR/etcher"
    mkdir "$TOOLS_DIR/etcher"
    unzip -o -q -d "$TOOLS_DIR/etcher" "$str_work/$str_zip"
    rm -rf "$str_work"
    print_status "success" "balenaEtcher $str_tag -> $TOOLS_DIR/etcher (GUI; flash with it manually)"
}

main() {
    local str_what="all"
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --allow-github-digest) ALLOW_UNSIGNED_DOWNLOAD=1 ;;
            *) str_what="$1" ;;
        esac
        shift
    done
    case "$str_what" in
        bmaptool | all) fetch_bmaptool ;;
        etcher) fetch_etcher ;;
        *)
            print_status "error" "Usage: $0 [--allow-github-digest] [bmaptool|etcher|all]"
            return 1
            ;;
    esac
}

main "$@"
