#!/usr/bin/env bash

set -euo pipefail

root="${1:-.}"
re_block='(/\*|//)[[:space:]]*eslint-disable([[:space:]]|\*|$)'
re_line='eslint-disable-line([[:space:]]*(\*/|--|$)|.*skip/)'

hits="$(grep -rnE --include='*.test.*' --include='*.spec.*' \
    --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=coverage \
    -e "$re_block" -e "$re_line" "$root" || true)"

if [ -n "$hits" ]; then
    printf '%s\n' "$hits" >&2
    echo "ERROR: test files may not use a block, bare or skip/-naming eslint-disable (see AGENTS.md)." >&2
    exit 1
fi
