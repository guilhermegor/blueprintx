#!/bin/bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "lib/scaffold_gate_parity.sh is meant to be sourced, not executed." >&2
    exit 1
fi

scaffold_render_gate_parity() {
    local str_src="$1" str_fragment="$2" str_dest="$3" str_tmp
    if [ ! -r "$str_fragment" ] || [ ! -s "$str_fragment" ]; then
        print_status "error" "gate-parity fragment $str_fragment is missing or empty"
        return 1
    fi
    str_tmp="$(mktemp)"
    if ! awk -v frag="$str_fragment" '
        /^(```|~~~)/ { fenced = !fenced }
        !fenced && /^#{1,6} / {
            skip = ($0 ~ /^## Gate parity/)
            if (skip) {
                replaced = 1
                while ((getline line < frag) > 0) print line
                close(frag)
                print ""
            }
        }
        !skip { print }
        END { exit(replaced ? 0 : 1) }
    ' "$str_src" >"$str_tmp"; then
        rm -f "$str_tmp"
        print_status "error" "$str_src has no '## Gate parity' section outside a code fence to replace"
        return 1
    fi
    mv "$str_tmp" "$str_dest"
}
