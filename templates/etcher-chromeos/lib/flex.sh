#!/usr/bin/env bash
# shellcheck disable=SC2034

FLEX_MANIFEST_URL="${CROS_FLEX_MANIFEST_URL:-https://dl.google.com/dl/edgedl/chromeos/recovery/cloudready_recovery2.json}"
FLEX_VERSION="" FLEX_URL="" FLEX_FILE="" FLEX_FILESIZE="" FLEX_ZIPSIZE="" FLEX_SHA1=""

flex_pick_entry() {
    python3 -I - "$1" "$2" <<'PY'
import json, sys

list_entries = [e for e in json.load(open(sys.argv[1])) if e.get("channel") == sys.argv[2]]
if not list_entries:
    sys.exit("no %s entry in the manifest" % sys.argv[2])
dict_best = max(list_entries, key=lambda e: [int(p) for p in e["version"].split(".")])
print("\t".join(str(dict_best[k]) for k in
                ("version", "url", "file", "filesize", "zipfilesize", "sha1")))
PY
}

flex_resolve() {
    local str_dir="$1" str_channel="$2" str_manifest="$1/recovery-manifest.json" str_line
    mkdir -p "$str_dir"
    curl -fsSL --retry 3 -o "$str_manifest" "$FLEX_MANIFEST_URL"
    str_line="$(flex_pick_entry "$str_manifest" "$str_channel")"
    IFS=$'\t' read -r FLEX_VERSION FLEX_URL FLEX_FILE FLEX_FILESIZE FLEX_ZIPSIZE FLEX_SHA1 <<<"$str_line"
}

flex_download() {
    local str_dir="$1" str_zip="$1/${FLEX_URL##*/}" str_bin="$1/$FLEX_FILE"
    curl -fL --retry 3 -C - -o "$str_zip" "$FLEX_URL"
    verify_size "$FLEX_ZIPSIZE" "$str_zip"
    unzip -o -q -d "$str_dir" "$str_zip" "$FLEX_FILE"
    if ! verify_size "$FLEX_FILESIZE" "$str_bin" || ! verify_hash sha1 "$FLEX_SHA1" "$str_bin"; then
        rm -f "$str_bin"
        return 1
    fi
    IMAGE_PATH="$str_bin"
}
