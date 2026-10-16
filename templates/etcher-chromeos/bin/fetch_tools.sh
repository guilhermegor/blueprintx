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
    local str_json="$TOOLS_DIR/bmaptool-release.json" str_name str_url str_digest str_tgz str_src
    mkdir -p "$TOOLS_DIR/bin"
    curl -fsSL --retry 3 -o "$str_json" "$BMAPTOOL_API"
    read -r str_name str_url str_digest < <(bmaptool_asset "$str_json") || true
    if [ -z "${str_digest:-}" ]; then
        print_status "error" "latest bmaptool release has no .tar.gz asset with a GitHub sha256 digest; install bmaptool from your distro or use --tool dd"
        return 1
    fi
    str_tgz="$TOOLS_DIR/$str_name"
    curl -fsSL --retry 3 -o "$str_tgz" "$str_url"
    verify_hash sha256 "$str_digest" "$str_tgz"
    tar -xzf "$str_tgz" -C "$TOOLS_DIR"
    str_src="$(ls -d "$TOOLS_DIR"/bmaptool-*/src | head -n1)"
    printf '#!/usr/bin/env bash\nPYTHONPATH="%s" exec python3 -m bmaptool "$@"\n' "$str_src" >"$TOOLS_DIR/bin/bmaptool"
    chmod +x "$TOOLS_DIR/bin/bmaptool"
    print_status "success" "bmaptool ($str_name) -> $TOOLS_DIR/bin/bmaptool"
}

fetch_etcher() {
    local str_json="$TOOLS_DIR/etcher-release.json" str_tag str_zip str_base
    mkdir -p "$TOOLS_DIR/etcher"
    curl -fsSL --retry 3 -o "$str_json" "$ETCHER_API"
    str_tag="$(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["tag_name"])' "$str_json")"
    str_zip="balenaEtcher-linux-x64-${str_tag#v}.zip"
    str_base="https://github.com/balena-io/etcher/releases/download/$str_tag"
    curl -fsSL --retry 3 -o "$TOOLS_DIR/etcher/$str_zip" "$str_base/$str_zip"
    curl -fsSL --retry 3 -o "$TOOLS_DIR/etcher/SHA256SUMS.Linux.x64.txt" "$str_base/SHA256SUMS.Linux.x64.txt"
    (cd "$TOOLS_DIR/etcher" && grep -F " $str_zip" SHA256SUMS.Linux.x64.txt | sha256sum -c -)
    unzip -o -q -d "$TOOLS_DIR/etcher" "$TOOLS_DIR/etcher/$str_zip"
    print_status "success" "balenaEtcher $str_tag -> $TOOLS_DIR/etcher (GUI; flash with it manually)"
}

case "${1:-all}" in
    bmaptool) fetch_bmaptool ;;
    etcher) fetch_etcher ;;
    all) fetch_bmaptool ;;
    *)
        print_status "error" "Usage: $0 [bmaptool|etcher|all]  (all = bmaptool; etcher is the optional GUI)"
        exit 1
        ;;
esac
