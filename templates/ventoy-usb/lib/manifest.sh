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
        dirsums:sums:?* | github:gh-digest | dirindex:sidecar:?* | sfrss:sidecar:?*) ;;
        sfrss:rss-hash | archive:archive-hash | latesturl:sidecar:?*) ;;
        github:none:?* | dirindex:none:?* | latesturl:none:?* | windows:none:?*) ;;
        manual:*) ;;
        *) return 1 ;;
    esac
}

manifest_trust_valid() {
    local str_kind="$1" str_sum="$2" str_trust="$3"
    case "$str_trust" in
        gpg:[0-9A-F][0-9A-F]*:*:https://*) [ "$str_kind" = dirsums ] ;;
        two-origin) [ "$str_kind" = github ] ;;
        same-origin-digest) [[ "$str_sum" != none:* && "$str_kind" != manual ]] ;;
        none) [[ "$str_sum" == none:* ]] ;;
        *) return 1 ;;
    esac
}

manifest_validate_line() {
    local str_line="$1" str_pipes
    str_pipes="${str_line//[^|]/}"
    if [ "${#str_pipes}" -ne 9 ]; then
        echo "manifest: expected 10 '|'-separated fields: $str_line" >&2
        return 1
    fi
    case "$(manifest_field "$str_line" 4)" in
        dirsums | github | dirindex | sfrss | archive | latesturl | windows | manual) ;;
        *)
            echo "manifest: unknown kind in: $str_line" >&2
            return 1
            ;;
    esac
    if ! manifest_checksum_valid "$(manifest_field "$str_line" 4)" "$(manifest_field "$str_line" 7)"; then
        echo "manifest: missing or invalid checksum (fail closed) in: $str_line" >&2
        return 1
    fi
    if ! manifest_trust_valid "$(manifest_field "$str_line" 4)" "$(manifest_field "$str_line" 7)" "$(manifest_field "$str_line" 10)"; then
        echo "manifest: trust level missing or inconsistent with the checksum in: $str_line" >&2
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
