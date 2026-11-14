#!/usr/bin/env bash

set -euo pipefail

root="${1:-.}"
re_block='(/\*|//)[[:space:]]*eslint-disable([[:space:]]|\*|$)'
re_line='eslint-disable-line([[:space:]]*(\*/|--|$)|.*skip/)|eslint-disable-next-line.*skip/'

int_status=0
hits="$(grep -rnE --include='*.test.*' --include='*.spec.*' --exclude='*.snap' \
    --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=coverage \
    -e "$re_block" -e "$re_line" "$root")" || int_status=$?

if [ "$int_status" -le 1 ]; then
    int_status=0
    hits_ml="$(grep -rlzE --include='*.test.*' --include='*.spec.*' --exclude='*.snap' \
        --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=coverage \
        -e "$re_block" "$root" | tr '\0' '\n')" || int_status=$?
    hits="$hits$hits_ml"
fi

if [ "$int_status" -gt 1 ]; then
    echo "ERROR: grep failed (exit $int_status) while scanning $root" >&2
    exit "$int_status"
fi

if [ -n "$hits" ]; then
    printf '%s\n' "$hits" >&2
    echo "ERROR: test files may not use a block, bare or skip/-naming eslint-disable (see AGENTS.md)." >&2
    exit 1
fi
