#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$PROJECT_ROOT/lib/common.sh"
# shellcheck source=lib/verify.sh
source "$PROJECT_ROOT/lib/verify.sh"
TOOLS_DIR="${CROS_TOOLS_DIR:-$PROJECT_ROOT/.tools}"

BMAPTOOL_VERSION="3.9.0"
BMAPTOOL_SHA256="9940bb97fa0f2c11ee4625a2f620a4ae2b94c556f8d01c070aee08486a2a1812"
BMAPTOOL_URL="https://github.com/yoctoproject/bmaptool/archive/refs/tags/v${BMAPTOOL_VERSION}.tar.gz"
ETCHER_API="${CROS_ETCHER_API:-https://api.github.com/repos/balena-io/etcher/releases/latest}"

fetch_bmaptool() {
    local str_tgz="$TOOLS_DIR/bmaptool-$BMAPTOOL_VERSION.tar.gz"
    mkdir -p "$TOOLS_DIR/bin"
    curl -fsSL --retry 3 -o "$str_tgz" "$BMAPTOOL_URL"
    verify_hash sha256 "$BMAPTOOL_SHA256" "$str_tgz"
    tar -xzf "$str_tgz" -C "$TOOLS_DIR"
    cat >"$TOOLS_DIR/bin/bmaptool" <<WRAP
#!/usr/bin/env bash
PYTHONPATH="$TOOLS_DIR/bmaptool-$BMAPTOOL_VERSION/src" exec python3 -m bmaptool "\$@"
WRAP
    chmod +x "$TOOLS_DIR/bin/bmaptool"
    print_status "success" "bmaptool $BMAPTOOL_VERSION -> $TOOLS_DIR/bin/bmaptool"
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
