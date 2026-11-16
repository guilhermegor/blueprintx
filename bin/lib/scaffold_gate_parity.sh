#!/bin/bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "lib/scaffold_gate_parity.sh is meant to be sourced, not executed." >&2
    exit 1
fi

scaffold_render_gate_parity() {
    local str_src="$1" str_fragment="$2" str_dest="$3"
    if [ ! -r "$str_fragment" ] || [ ! -s "$str_fragment" ]; then
        print_status "error" "gate-parity fragment $str_fragment is missing or empty"
        return 1
    fi
    if ! grep -q '^## Gate parity' "$str_src"; then
        print_status "error" "$str_src has no '## Gate parity' section to replace"
        return 1
    fi
    awk -v frag="$str_fragment" '
        /^```/ { fenced = !fenced }
        !fenced && /^## / {
            skip = ($0 ~ /^## Gate parity/)
            if (skip) {
                while ((getline line < frag) > 0) print line
                close(frag)
                print ""
            }
        }
        !skip { print }
    ' "$str_src" >"$str_dest"
}
