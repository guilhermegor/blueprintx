#!/usr/bin/env bash
set -euo pipefail
str_dest=""
str_url=""
int_head=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o)
            str_dest="$2"
            shift
            ;;
        --retry | -A | --connect-timeout | --max-time)
            shift
            ;;
        -*I*) int_head=1 ;;
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
if [ "$int_head" -eq 1 ]; then
    printf 'HTTP/1.1 200 OK\r\nContent-Length: %s\r\n\r\n' "$(wc -c <"$path_src")"
else
    cp "$path_src" "$str_dest"
fi
