#!/usr/bin/env bash

net_get() {
    "${CURL:-curl}" -fsSL --retry 3 -o "$2" "$1"
}

sums_parse() {
    sed -nE \
        -e 's/^([0-9a-fA-F]{64}) [ *](.+)$/\1\t\2/p' \
        -e 's/^SHA256 \((.+)\) = ([0-9a-fA-F]{64})$/\2\t\1/p' "$1"
}

resolve_dirsums() {
    local str_base="$1" str_re="$2" str_sums="$3" path_tmp str_name str_hash
    path_tmp="$(mktemp)"
    net_get "$str_base$str_sums" "$path_tmp" || {
        rm -f "$path_tmp"
        return 1
    }
    str_name="$(sums_parse "$path_tmp" | cut -f2 | grep -E "$str_re" | sort -V | tail -n1)" || true
    if [ -z "$str_name" ]; then
        rm -f "$path_tmp"
        echo "resolve: no name matching $str_re in $str_base$str_sums" >&2
        return 1
    fi
    str_hash="$(sums_parse "$path_tmp" | awk -F'\t' -v n="$str_name" '$2 == n { print $1; exit }')"
    rm -f "$path_tmp"
    printf '%s\t%s\t%s\n' "$str_name" "$str_base$str_name" "$str_hash"
}

resolve_github() {
    local str_repo="$1" str_re="$2" path_tmp str_row
    path_tmp="$(mktemp)"
    net_get "${GITHUB_API:-https://api.github.com}/repos/$str_repo/releases/latest" "$path_tmp" || {
        rm -f "$path_tmp"
        return 1
    }
    str_row="$(jq -r --arg re "$str_re" \
        '[.assets[] | select(.name | test($re))][0] // empty | [.name, .browser_download_url, ((.digest // "") | sub("^sha256:"; ""))] | @tsv' \
        "$path_tmp")"
    rm -f "$path_tmp"
    if [ -z "$str_row" ]; then
        echo "resolve: no release asset matching $str_re in $str_repo" >&2
        return 1
    fi
    printf '%s\n' "$str_row"
}

resolve_pinned() {
    local str_url="$1" str_sum="$2" path_tmp str_hash=""
    case "$str_sum" in
        sha256:*) str_hash="${str_sum#sha256:}" ;;
        sidecar:*)
            path_tmp="$(mktemp)"
            net_get "$str_url${str_sum#sidecar:}" "$path_tmp" || {
                rm -f "$path_tmp"
                return 1
            }
            str_hash="$(grep -oE '[0-9a-fA-F]{64}' "$path_tmp" | head -n1)" || true
            rm -f "$path_tmp"
            ;;
    esac
    printf '%s\t%s\t%s\n' "$(basename "$str_url")" "$str_url" "$str_hash"
}

resolve_entry() {
    local str_line="$1" str_kind str_src str_re str_sum str_row str_name str_url str_hash
    str_kind="$(manifest_field "$str_line" 4)"
    str_src="$(manifest_field "$str_line" 5)"
    str_re="$(manifest_field "$str_line" 6)"
    str_sum="$(manifest_field "$str_line" 7)"
    case "$str_kind" in
        dirsums) str_row="$(resolve_dirsums "$str_src" "$str_re" "${str_sum#sums:}")" || return 1 ;;
        github) str_row="$(resolve_github "$str_src" "$str_re")" || return 1 ;;
        pinned) str_row="$(resolve_pinned "$str_src" "$str_sum")" || return 1 ;;
    esac
    IFS=$'\t' read -r str_name str_url str_hash <<<"$str_row"
    if [ -z "$str_hash" ] && [[ "$str_sum" != none:* ]]; then
        echo "resolve: no upstream checksum for $str_name (fail closed)" >&2
        return 1
    fi
    printf '%s\t%s\t%s\n' "$str_name" "$str_url" "$str_hash"
}

fetch_entry() {
    local str_line="$1" path_drive="$2" path_cache="$3" path_resolved="$4"
    local str_id str_folder str_row str_name str_url str_hash path_dir path_dest str_got
    str_id="$(manifest_field "$str_line" 1)"
    str_folder="$(manifest_field "$str_line" 3)"
    if [ "$(manifest_field "$str_line" 4)" = manual ]; then
        print_status "warning" "manual: $str_id -> put $(manifest_field "$str_line" 6) in manual/$str_folder/ ($(manifest_field "$str_line" 5))"
        return 0
    fi
    str_row="$(resolve_entry "$str_line")" || {
        print_status "error" "resolve failed: $str_id"
        return 1
    }
    IFS=$'\t' read -r str_name str_url str_hash <<<"$str_row"
    path_dir="$path_drive/$str_folder"
    [ "$str_folder" = "@tools" ] && path_dir="$path_cache"
    mkdir -p "$path_dir"
    path_dest="$path_dir/$str_name"
    if [ ! -f "$path_dest" ]; then
        print_status "info" "download: $str_id -> $str_name"
        net_get "$str_url" "$path_dest.part" || {
            rm -f "$path_dest.part"
            return 1
        }
        if [ -n "$str_hash" ]; then
            str_got="$(sha256sum "$path_dest.part" | cut -d' ' -f1)"
            if [ "$str_got" != "${str_hash,,}" ]; then
                rm -f "$path_dest.part"
                print_status "error" "checksum mismatch: $str_id ($str_name)"
                return 1
            fi
        else
            print_status "warning" "unverified ($(manifest_field "$str_line" 7)): $str_id"
        fi
        mv "$path_dest.part" "$path_dest"
    fi
    [ "$str_folder" = "@tools" ] || printf '%s\t%s\n' "$str_id" "$str_folder/$str_name" >>"$path_resolved"
}

fetch_all() {
    local path_manifest="$1" path_drive="$2" path_cache="$3" path_resolved="$4" str_line int_bad=0
    manifest_entries "$path_manifest" >/dev/null || return 1
    : >"$path_resolved"
    while IFS= read -r str_line; do
        fetch_entry "$str_line" "$path_drive" "$path_cache" "$path_resolved" || int_bad=1
    done < <(manifest_entries "$path_manifest")
    return "$int_bad"
}
