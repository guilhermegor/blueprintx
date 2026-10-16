#!/usr/bin/env bash

TOOLS_DIR="${TOOLS_DIR:-${PROJECT_ROOT:-.}/.tools}"
MS_UA="Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0"
HASH_RE='[0-9a-fA-F]{64}|[0-9a-fA-F]{40}|[0-9a-fA-F]{32}'

net_get() {
    "${CURL:-curl}" -fsSL --retry 3 --proto =https --proto-redir =https --tlsv1.2 --connect-timeout 20 --max-time 3600 ${NET_UA:+-A "$NET_UA"} -o "$2" "$1"
}

net_size() {
    "${CURL:-curl}" -fsSIL --proto =https --proto-redir =https --tlsv1.2 "$1" | tr -d '\r' | awk 'tolower($1) == "content-length:" { n = $2 } END { print n }'
}

sums_parse() {
    sed -nE \
        -e 's/^([0-9a-fA-F]{64}) [ *](.+)$/\1\t\2/p' \
        -e 's/^SHA256 \((.+)\) = ([0-9a-fA-F]{64})$/\2\t\1/p' "$1"
}

pick_newest() {
    awk -F'\t' -v re="$1" '{ n = $1; sub(/.*\//, "", n); if (n ~ re || $1 ~ re) print n "\t" $0 }' |
        sort -V -t$'\t' -k1,1 | tail -n1 | cut -f2-
}

sidecar_hash() {
    local path_tmp
    path_tmp="$(mktemp)"
    net_get "$1" "$path_tmp" || {
        rm -f "$path_tmp"
        return 1
    }
    sed -nE 's/^('"$HASH_RE"')([ *].*)?\r?$/\1/p' "$path_tmp" | head -n1
    rm -f "$path_tmp"
}

gpg_verify_sums() {
    local path_sums="$1" str_url="$2" str_trust="$3" str_fpr str_suffix str_keyurl path_home int_rc=1
    IFS=: read -r _ str_fpr str_suffix str_keyurl <<<"$str_trust"
    command -v gpg >/dev/null 2>&1 || {
        echo "gpg: not installed, cannot verify $str_url (fail closed)" >&2
        return 1
    }
    path_home="$(mktemp -d)"
    chmod 700 "$path_home"
    if net_get "$str_url$str_suffix" "$path_home/sig" && net_get "$str_keyurl" "$path_home/key.asc" &&
        gpg --homedir "$path_home" --batch --show-keys --with-colons "$path_home/key.asc" 2>/dev/null |
        awk -F: '$1 == "fpr" { print $10 }' | grep -qx "$str_fpr" &&
        gpg --homedir "$path_home" --batch -q --import "$path_home/key.asc" 2>/dev/null &&
        gpg --homedir "$path_home" --batch --status-fd 1 --verify "$path_home/sig" "$path_sums" 2>/dev/null |
        awk -v f="$str_fpr" '$1 == "[GNUPG:]" && $2 == "VALIDSIG" && $NF == f { ok = 1 } END { exit !ok }'; then
        int_rc=0
    else
        echo "gpg: signature of $str_url not verified against key $str_fpr (fail closed)" >&2
    fi
    rm -rf "$path_home"
    return "$int_rc"
}

valid_name() {
    [[ "$1" =~ ^[A-Za-z0-9._+-]+$ ]] && [[ "$1" != *..* ]]
}

resolve_dirsums() {
    local str_base="$1" str_re="$2" str_sums="$3" str_trust="${4:-}" path_tmp str_name str_hash
    path_tmp="$(mktemp)"
    net_get "$str_base$str_sums" "$path_tmp" || {
        rm -f "$path_tmp"
        return 1
    }
    if [[ "$str_trust" == gpg:* ]]; then
        gpg_verify_sums "$path_tmp" "$str_base$str_sums" "$str_trust" || {
            rm -f "$path_tmp"
            return 1
        }
    fi
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

resolve_dirindex() {
    local str_base="$1" str_re="$2" str_sum="$3" path_tmp str_href str_hash=""
    path_tmp="$(mktemp)"
    net_get "$str_base" "$path_tmp" || {
        rm -f "$path_tmp"
        return 1
    }
    str_href="$(grep -oE 'href="[^"]+"' "$path_tmp" | sed -E 's/^href="//; s/"$//' | grep -E "$str_re" |
        awk '{ n = $0; sub(/.*\//, "", n); print n "\t" $0 }' | sort -V -t$'\t' -k1,1 | tail -n1 | cut -f2)" || true
    rm -f "$path_tmp"
    if [ -z "$str_href" ]; then
        echo "resolve: no link matching $str_re in $str_base" >&2
        return 1
    fi
    [[ "$str_sum" != sidecar:* ]] || str_hash="$(sidecar_hash "$str_base$str_href${str_sum#sidecar:}")" || return 1
    printf '%s\t%s\t%s\n' "$(basename "$str_href")" "$str_base$str_href" "$str_hash"
}

resolve_sfrss() {
    local str_src="$1" str_re="$2" str_sum="$3" str_proj str_path path_tmp str_row str_file str_hash str_url
    str_proj="${str_src%%/*}"
    str_path="${str_src#*/}"
    path_tmp="$(mktemp)"
    net_get "https://sourceforge.net/projects/$str_proj/rss?path=/${str_path// /%20}&limit=100" "$path_tmp" || {
        rm -f "$path_tmp"
        return 1
    }
    str_row="$(awk '
        /<title><!\[CDATA\[/ { t = $0; sub(/.*CDATA\[/, "", t); sub(/\]\].*/, "", t); h = "" }
        /<media:hash/ { h = $0; sub(/.*algo="[a-z0-9]+">/, "", h); sub(/<.*/, "", h); print t "\t" h }
    ' "$path_tmp" | pick_newest "$str_re")"
    rm -f "$path_tmp"
    if [ -z "$str_row" ]; then
        echo "resolve: no SourceForge file matching $str_re in $str_src" >&2
        return 1
    fi
    IFS=$'\t' read -r str_file str_hash <<<"$str_row"
    str_url="https://downloads.sourceforge.net/project/$str_proj$str_file"
    [[ "$str_sum" != sidecar:* ]] || str_hash="$(sidecar_hash "$str_url${str_sum#sidecar:}")" || return 1
    printf '%s\t%s\t%s\n' "$(basename "$str_file")" "$str_url" "$str_hash"
}

resolve_archive() {
    local str_id="$1" str_re="$2" path_tmp str_row
    path_tmp="$(mktemp)"
    net_get "https://archive.org/metadata/$str_id" "$path_tmp" || {
        rm -f "$path_tmp"
        return 1
    }
    str_row="$(jq -r --arg re "$str_re" --arg id "$str_id" \
        '[.files[] | select(.name | test($re))] | sort_by(.mtime | tonumber) | last // empty | [.name, "https://archive.org/download/\($id)/\(.name)", (.sha1 // "")] | @tsv' \
        "$path_tmp")"
    rm -f "$path_tmp"
    if [ -z "$str_row" ]; then
        echo "resolve: no archive.org file matching $str_re in $str_id" >&2
        return 1
    fi
    printf '%s\n' "$str_row"
}

resolve_latesturl() {
    local str_url="$1" str_re="$2" str_sum="$3" str_name str_hash=""
    str_name="$(sed -E 's/^\^//; s/\$$//; s/\\//g' <<<"$str_re")"
    if [[ "$str_sum" == sidecar:* ]]; then
        str_hash="$(sidecar_hash "$str_url${str_sum#sidecar:}")" || return 1
    else
        str_hash="size:$(net_size "$str_url")"
    fi
    printf '%s\t%s\t%s\n' "$str_name" "$str_url" "$str_hash"
}

resolve_windows() {
    local NET_UA="$MS_UA" str_lang="$1" str_sid str_edition str_sku path_tmp str_url str_err
    str_sid="$(cat /proc/sys/kernel/random/uuid)"
    path_tmp="$(mktemp)"
    local str_api="https://www.microsoft.com/software-download-connector/api"
    local str_q="profile=606624d44113&friendlyFileName=undefined&Locale=en-US&sessionID=$str_sid"
    net_get "https://www.microsoft.com/en-us/software-download/windows11" "$path_tmp" || {
        rm -f "$path_tmp"
        return 1
    }
    str_edition="$(grep -oE 'value="[0-9]{4,5}"' "$path_tmp" | head -n1 | tr -dc 0-9)"
    net_get "https://vlscppe.microsoft.com/tags?org_id=y6jn8c31&session_id=$str_sid" "$path_tmp" || true
    net_get "$str_api/getskuinformationbyproductedition?$str_q&productEditionId=$str_edition&SKU=undefined" "$path_tmp" || {
        rm -f "$path_tmp"
        return 1
    }
    str_sku="$(jq -r --arg l "$str_lang" '[.Skus[]? | select(.Language == $l)][0].Id // empty' "$path_tmp")"
    if [ -z "$str_sku" ]; then
        rm -f "$path_tmp"
        echo "resolve: Microsoft offers no '$str_lang' ISO; download it manually into payload/" >&2
        return 1
    fi
    net_get "$str_api/GetProductDownloadLinksBySku?$str_q&productEditionId=undefined&SKU=$str_sku" "$path_tmp" || {
        rm -f "$path_tmp"
        return 1
    }
    str_url="$(jq -r '[.ProductDownloadOptions[]? | select(.Uri | test("x64"))][0].Uri // empty' "$path_tmp")"
    str_err="$(jq -r '[.Errors[]?.Value] | join("; ")' "$path_tmp")"
    rm -f "$path_tmp"
    if [ -z "$str_url" ]; then
        echo "resolve: Microsoft refused the automated request (${str_err:-no link}); download the ISO manually into payload/isos/Windows/" >&2
        return 1
    fi
    printf '%s\t%s\t\n' "$(basename "${str_url%%\?*}")" "$str_url"
}

second_origin_missing() {
    if [ "${ALLOW_SINGLE_ORIGIN:-0}" = 1 ]; then
        print_status "warning" "second origin (ventoy.net) $2: $1 checked against one origin only (ALLOW_SINGLE_ORIGIN=1)" >&2
        return 0
    fi
    echo "resolve: second origin (ventoy.net) $2 for $1 (fail closed; set ALLOW_SINGLE_ORIGIN=1 to accept one origin)" >&2
    return 1
}

second_origin_check() {
    local str_name="$1" str_hash="$2" path_tmp str_other
    path_tmp="$(mktemp)"
    if ! net_get "https://www.ventoy.net/en/download.html" "$path_tmp"; then
        rm -f "$path_tmp"
        second_origin_missing "$str_name" "unreachable"
        return
    fi
    str_other="$(sed -nE 's/.*"linsha" *: *"([0-9a-f]{64})".*/\1/p' "$path_tmp" | head -n1)"
    rm -f "$path_tmp"
    if [ -z "$str_other" ]; then
        second_origin_missing "$str_name" "lists no checksum"
        return
    fi
    if [ "$str_other" != "${str_hash,,}" ]; then
        echo "resolve: GitHub digest and ventoy.net disagree for $str_name (fail closed)" >&2
        return 1
    fi
}

resolve_entry() {
    local str_line="$1" str_kind str_src str_re str_sum str_trust str_row str_name str_url str_hash
    str_trust="$(manifest_field "$str_line" 10)"
    str_kind="$(manifest_field "$str_line" 4)"
    str_src="$(manifest_field "$str_line" 5)"
    str_re="$(manifest_field "$str_line" 6)"
    str_sum="$(manifest_field "$str_line" 7)"
    case "$str_kind" in
        dirsums) str_row="$(resolve_dirsums "$str_src" "$str_re" "${str_sum#sums:}" "$str_trust")" || return 1 ;;
        github) str_row="$(resolve_github "$str_src" "$str_re")" || return 1 ;;
        dirindex) str_row="$(resolve_dirindex "$str_src" "$str_re" "$str_sum")" || return 1 ;;
        sfrss) str_row="$(resolve_sfrss "$str_src" "$str_re" "$str_sum")" || return 1 ;;
        archive) str_row="$(resolve_archive "$str_src" "$str_re")" || return 1 ;;
        latesturl) str_row="$(resolve_latesturl "$str_src" "$str_re" "$str_sum")" || return 1 ;;
        windows) str_row="$(resolve_windows "$str_src")" || return 1 ;;
    esac
    IFS=$'\t' read -r str_name str_url str_hash <<<"$str_row"
    if [ "$str_kind" != latesturl ] && ! valid_name "$str_name"; then
        echo "resolve: refusing unexpected file name '$str_name'" >&2
        return 1
    fi
    if [[ "$str_url" != https://* ]] || { [ "$str_kind" = github ] && [[ "$str_url" != https://github.com/* ]]; }; then
        echo "resolve: refusing a non-https or off-host URL for $str_name" >&2
        return 1
    fi
    if [ "$str_trust" = two-origin ]; then
        second_origin_check "$str_name" "$str_hash" || return 1
    fi
    if [ -z "$str_hash" ] && [[ "$str_sum" != none:* ]]; then
        echo "resolve: no upstream checksum for $str_name (fail closed)" >&2
        return 1
    fi
    printf '%s\t%s\t%s\n' "$str_name" "$str_url" "$str_hash"
}

hash_matches() {
    local path_file="$1" str_want="${2,,}" str_cmd
    case "${#str_want}" in
        64) str_cmd=sha256sum ;;
        40) str_cmd=sha1sum ;;
        32) str_cmd=md5sum ;;
        *) return 1 ;;
    esac
    [ "$("$str_cmd" "$path_file" | cut -d' ' -f1)" = "$str_want" ]
}

remove_older_versions() {
    local path_dir="$1" str_re="$2" str_keep="$3" path_old str_base
    for path_old in "$path_dir"/*; do
        [ -f "$path_old" ] || continue
        str_base="$(basename "$path_old")"
        if [ "$str_base" != "$str_keep" ] && [[ "$str_base" =~ $str_re ]]; then
            if [ "${DRY_RUN:-0}" = 1 ]; then
                print_status "info" "dry-run: would replace older version: $str_base"
            else
                print_status "info" "replacing older version: $str_base"
                ${DRIVE_RUN-} rm -f "$path_old"
            fi
        fi
    done
}

extract_member() {
    local path_archive="$1" path_dir="$2" str_re="$3" str_member
    command -v 7z >/dev/null 2>&1 || {
        print_status "error" "7z is required to extract $(basename "$path_archive")"
        return 1
    }
    local path_tmp
    str_member="$(7z l -ba -slt "$path_archive" | sed -n 's/^Path = //p' | grep -E "$str_re" | head -n1)"
    [ -n "$str_member" ] || return 1
    path_tmp="$(mktemp -d "$path_dir/.x.XXXXXX")"
    7z e -y -bso0 -bsp0 -o"$path_tmp" "$path_archive" "$str_member"
    mv "$path_tmp/$(basename "$str_member")" "$path_dir/"
    rm -rf "$path_tmp"
    basename "$str_member"
}

fetch_entry() {
    local str_line="$1" path_drive="$2" path_resolved="$3" path_state="$4"
    local str_id str_folder str_re str_row str_name str_url str_hash path_dir path_dest str_final str_extract
    str_id="$(manifest_field "$str_line" 1)"
    str_folder="$(manifest_field "$str_line" 3)"
    str_re="$(manifest_field "$str_line" 6)"
    str_extract="$(manifest_field "$str_line" 9)"
    if [ "$(manifest_field "$str_line" 4)" = manual ]; then
        print_status "warning" "manual: $str_id has no machine-readable upstream; put the file in payload/$str_folder/"
        return 0
    fi
    str_row="$(resolve_entry "$str_line")" || {
        print_status "error" "$str_id: could not resolve the latest version (skipped)"
        return 1
    }
    IFS=$'\t' read -r str_name str_url str_hash <<<"$str_row"
    path_dir="$path_drive/$str_folder"
    [ "$str_folder" = "@tools" ] && path_dir="$TOOLS_DIR"
    mkdir -p "$path_dir" "$path_state"
    path_dest="$path_dir/$str_name"
    str_final="$str_name"
    [ -z "$str_extract" ] || str_final="$(cat "$path_state/$str_id.final" 2>/dev/null || true)"
    if [ -f "$path_state/$str_id" ] && [ "$(cut -f1-2 "$path_state/$str_id")" = "$str_name"$'\t'"$str_hash" ] &&
        [ -n "$str_final" ] && [ -f "$path_dir/$str_final" ] &&
        [ "$(cut -f3 "$path_state/$str_id")" = "$(stat -c %s "$path_dir/$str_final")" ]; then
        :
    else
        print_status "info" "download: $str_id -> $str_name [trust: $(manifest_field "$str_line" 10 | cut -d: -f1)]"
        net_get "$str_url" "$path_dest.part" || {
            rm -f "$path_dest.part"
            print_status "error" "$str_id: download failed"
            return 1
        }
        if [[ "$str_hash" == size:* ]] || [ -z "$str_hash" ]; then
            print_status "warning" "unverified: $str_id (explicit none: in the manifest)"
        elif ! hash_matches "$path_dest.part" "$str_hash"; then
            rm -f "$path_dest.part"
            print_status "error" "checksum mismatch: $str_id ($str_name)"
            return 1
        fi
        mv "$path_dest.part" "$path_dest"
        if [ -n "$str_extract" ]; then
            str_final="$(extract_member "$path_dest" "$path_dir" "$str_extract")" || return 1
            rm -f "$path_dest"
            printf '%s' "$str_final" >"$path_state/$str_id.final"
        fi
        printf '%s\t%s\t%s' "$str_name" "$str_hash" "$(stat -c %s "$path_dir/$str_final")" >"$path_state/$str_id"
    fi
    remove_older_versions "$path_dir" "${str_extract:-$str_re}" "$str_final"
    [ "$str_folder" = "@tools" ] || printf '%s\t%s\n' "$str_id" "$str_folder/$str_final" >>"$path_resolved"
}

fetch_all() {
    local path_manifest="$1" path_drive="$2" path_resolved="$3" str_line int_bad=0
    manifest_entries "$path_manifest" >/dev/null || return 1
    mkdir -p "$(dirname "$path_resolved")"
    : >"$path_resolved"
    while IFS= read -r str_line; do
        fetch_entry "$str_line" "$path_drive" "$path_resolved" "$(dirname "$path_resolved")/state" || int_bad=1
    done < <(manifest_entries "$path_manifest")
    return "$int_bad"
}
