#!/usr/bin/env bash

persistence_file_name() {
    printf 'persistence_ext4_%sGB_%s.dat' "$(($1 / 1024))" "$2"
}

ventoy_json_generate() {
    local path_manifest="$1" path_drive="$2" path_resolved="$3" int_size_mb="$4"
    local str_line str_label str_id str_rel str_first=1
    manifest_entries "$path_manifest" >/dev/null || return 1
    {
        printf '{\n    "control": [\n        { "VTOY_TREE_VIEW_MENU_STYLE": "1" },\n'
        printf '        { "VTOY_DEFAULT_SEARCH_ROOT": "/isos" }\n    ],\n'
        printf '    "theme": {\n        "display_mode": "CLI"\n    },\n    "persistence": [\n'
        while IFS= read -r str_line; do
            str_label="$(manifest_field "$str_line" 8)"
            [ -n "$str_label" ] || continue
            str_id="$(manifest_field "$str_line" 1)"
            str_rel="$(awk -F'\t' -v i="$str_id" '$1 == i { print $2 }' "$path_resolved")"
            if [ -z "$str_rel" ]; then
                echo "ventoy.json: persistence entry '$str_id' has no resolved image" >&2
                return 1
            fi
            [ "$str_first" -eq 1 ] || printf ',\n'
            str_first=0
            printf '        {\n            "image": "/%s",\n' "$str_rel"
            printf '            "backend": [\n                "/persistance/%s"\n            ]\n        }' \
                "$(persistence_file_name "$int_size_mb" "$str_label")"
        done < <(manifest_entries "$path_manifest")
        printf '\n    ]\n}\n'
    } >"$path_drive/ventoy/ventoy.json"
}

ventoy_json_check() {
    local path_drive="$1" path_json str_ref int_bad=0
    path_json="$path_drive/ventoy/ventoy.json"
    [ -f "$path_json" ] || {
        echo "ventoy.json: $path_json not found" >&2
        return 1
    }
    while IFS= read -r str_ref; do
        if [ ! -e "$path_drive$str_ref" ]; then
            echo "ventoy.json: $str_ref does not exist on the drive tree" >&2
            int_bad=1
        fi
    done < <(grep -oE '"/[^"]+"' "$path_json" | tr -d '"')
    return "$int_bad"
}

tools_ventoy_dir() {
    ls -d "$TOOLS_DIR"/ventoy-[0-9]*/ 2>/dev/null | sort -V | tail -n1
}

tools_ensure() {
    local path_manifest="$1" str_line path_tmp path_dir
    [ -z "${VENTOY_DIR:-}" ] || return 0
    if [ -z "$(tools_ventoy_dir)" ]; then
        str_line="$(manifest_entries "$path_manifest" | grep '^ventoy|')" || return 1
        fetch_entry "$str_line" "" "/dev/null" "${BUILD_DIR:-build}/state" || return 1
        path_tmp="$(mktemp -d "$TOOLS_DIR/.x.XXXXXX")"
        tar -xzf "$(ls "$TOOLS_DIR"/ventoy-*-linux.tar.gz | sort -V | tail -n1)" -C "$path_tmp" --no-same-owner
        for path_dir in "$path_tmp"/ventoy-[0-9]*; do
            rm -rf "${TOOLS_DIR:?}/$(basename "$path_dir")"
            mv "$path_dir" "$TOOLS_DIR/"
        done
        rm -rf "$path_tmp"
    fi
}

persistence_download() {
    local path_img="$1" int_size_mb="$2" str_label="$3" path_tmp path_tmp_json str_name str_gb str_zip str_hash str_body
    [ $((int_size_mb % 1024)) -eq 0 ] || return 1
    str_gb="$((int_size_mb / 1024))GB"
    [[ "$str_label" =~ ^[A-Za-z0-9_-]+$ ]] || return 1
    str_name="persistence_ext4_${str_gb}_${str_label}.dat.7z"
    command -v 7z >/dev/null 2>&1 || return 1
    path_tmp="$(mktemp -d)"
    path_tmp_json="$path_tmp/release.json"
    net_get "${GITHUB_API:-https://api.github.com}/repos/ventoy/backend/releases/latest" "$path_tmp_json" || {
        rm -rf "$path_tmp"
        return 1
    }
    str_zip="$(jq -r '[.assets[] | select(.name == "images.zip")][0].browser_download_url // empty' "$path_tmp_json")"
    str_body="$(jq -r '.body // empty' "$path_tmp_json" | tr -d '\r')"
    str_hash="$(awk -v n="$str_name" '$2 == n && $1 ~ /^[0-9a-f]{64}$/ { print $1; exit }' <<<"$str_body")"
    if [[ "$str_zip" != https://github.com/* ]] || [ -z "$str_hash" ] ||
        ! net_get "$str_zip" "$path_tmp/images.zip" ||
        ! 7z e -y -bso0 -bsp0 -o"$path_tmp" "$path_tmp/images.zip" "images/$str_name" ||
        ! hash_matches "$path_tmp/$str_name" "$str_hash" ||
        ! 7z e -y -bso0 -bsp0 -o"$path_tmp/out" "$path_tmp/$str_name"; then
        rm -rf "$path_tmp"
        return 1
    fi
    mv "$path_tmp/out/${str_name%.7z}" "$path_img"
    rm -rf "$path_tmp"
}

persistence_create() {
    local path_manifest="$1" path_drive="$2" int_size_mb="$3"
    local str_line str_label path_img path_tool str_name
    manifest_entries "$path_manifest" >/dev/null || return 1
    while IFS= read -r str_line; do
        str_label="$(manifest_field "$str_line" 8)"
        [ -n "$str_label" ] || continue
        str_name="$(persistence_file_name "$int_size_mb" "$str_label")"
        path_img="$path_drive/persistance/$str_name"
        [ ! -f "$path_img" ] || continue
        if compgen -G "$path_drive/persistance/persistence_ext4_*_${str_label}.dat" >/dev/null; then
            print_status "warning" "persistence size changed: the saved session data in the old image is lost"
            rm -f "$path_drive"/persistance/persistence_ext4_*_"${str_label}".dat
        fi
        mkdir -p "$path_drive/persistance"
        if persistence_download "$path_img" "$int_size_mb" "$str_label"; then
            print_status "info" "persistence image downloaded from ventoy/backend (checksum from the release notes)"
            continue
        fi
        print_status "warning" "no published image for ${int_size_mb} MB / $str_label: creating it with CreatePersistentImg.sh (needs root)"
        tools_ensure "$path_manifest" || return 1
        path_tool="${VENTOY_DIR:-$(tools_ventoy_dir)}"
        ${SUDO-sudo} bash "$path_tool/CreatePersistentImg.sh" -s "$int_size_mb" -t ext4 -l "$str_label" -o "$path_img"
        ${SUDO-sudo} chown "$(id -u):$(id -g)" "$path_img"
    done < <(manifest_entries "$path_manifest")
}
