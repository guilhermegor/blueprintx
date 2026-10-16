#!/usr/bin/env bash
set -euo pipefail
str_dest=""
str_url=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o)
            str_dest="$2"
            shift
            ;;
        --retry)
            shift
            ;;
        -*) ;;
        *) str_url="$1" ;;
    esac
    shift
done
path_src="$FIXTURES/$(printf '%s' "$str_url" | sed 's/[^A-Za-z0-9.-]/_/g')"
[ -f "$path_src" ] || {
    echo "curl_stub: no fixture for $str_url" >&2
    exit 22
}
cp "$path_src" "$str_dest"
