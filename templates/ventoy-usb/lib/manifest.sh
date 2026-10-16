#!/usr/bin/env bash

manifest_field() {
    cut -d'|' -f"$2" <<<"$1"
}

manifest_group_enabled() {
    case "$1" in
        windows) [ "${INCLUDE_WINDOWS:-y}" = y ] ;;
        android) [ "${INCLUDE_ANDROID:-y}" = y ] ;;
        core | tool) return 0 ;;
        *) return 1 ;;
    esac
}

manifest_checksum_valid() {
    local str_kind="$1" str_sum="$2"
    case "$str_kind:$str_sum" in
        dirsums:sums:?*) ;;
        github:gh-digest) ;;
        pinned:sidecar:?*) ;;
        pinned:sha256:*) [[ "$str_sum" =~ ^sha256:[0-9a-f]{64}$ ]] ;;
        pinned:none:?* | github:none:?*) ;;
        manual:*) ;;
        *) return 1 ;;
    esac
}

manifest_validate_line() {
    local str_line="$1" str_pipes
    str_pipes="${str_line//[^|]/}"
    if [ "${#str_pipes}" -ne 7 ]; then
        echo "manifest: expected 8 '|'-separated fields: $str_line" >&2
        return 1
    fi
    case "$(manifest_field "$str_line" 4)" in
        dirsums | github | pinned | manual) ;;
        *)
            echo "manifest: unknown kind in: $str_line" >&2
            return 1
            ;;
    esac
    if ! manifest_checksum_valid "$(manifest_field "$str_line" 4)" "$(manifest_field "$str_line" 7)"; then
        echo "manifest: missing or invalid checksum (fail closed) in: $str_line" >&2
        return 1
    fi
}

manifest_entries() {
    local path_file="$1" str_line
    while IFS= read -r str_line || [ -n "$str_line" ]; do
        case "$str_line" in '' | '#'*) continue ;; esac
        manifest_validate_line "$str_line" || return 1
        manifest_group_enabled "$(manifest_field "$str_line" 2)" || continue
        printf '%s\n' "$str_line"
    done <"$path_file"
}
