#!/bin/bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "lib/scaffold_gate_parity.sh is meant to be sourced, not executed." >&2
    exit 1
fi

scaffold_render_gate_parity() {
    local str_src="$1" str_fragment="$2" str_dest="$3"
    if ! grep -q '^## Gate parity' "$str_src"; then
        print_status "error" "$str_src has no '## Gate parity' section to replace"
        return 1
    fi
    awk -v frag="$str_fragment" '
        /^## / {
            skip = ($0 ~ /^## Gate parity/)
            if (skip) {
                while ((getline line < frag) > 0) print line
                print ""
            }
        }
        !skip { print }
    ' "$str_src" >"$str_dest"
}
