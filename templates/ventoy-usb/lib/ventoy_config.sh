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
    local path_manifest="$1" str_line
    [ -z "${VENTOY_DIR:-}" ] || return 0
    if [ -z "$(tools_ventoy_dir)" ]; then
        str_line="$(manifest_entries "$path_manifest" | grep '^ventoy|')" || return 1
        fetch_entry "$str_line" "" "/dev/null" "${BUILD_DIR:-build}/state" || return 1
        tar -xzf "$(ls "$TOOLS_DIR"/ventoy-*-linux.tar.gz | sort -V | tail -n1)" -C "$TOOLS_DIR"
    fi
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
        tools_ensure "$path_manifest" || return 1
        path_tool="${VENTOY_DIR:-$(tools_ventoy_dir)}"
        if compgen -G "$path_drive/persistance/persistence_ext4_*_${str_label}.dat" >/dev/null; then
            print_status "warning" "persistence size changed: the saved session data in the old image is lost"
            rm -f "$path_drive"/persistance/persistence_ext4_*_"${str_label}".dat
        fi
        print_status "info" "creating empty ${int_size_mb} MB persistence image (needs root: losetup)"
        ${SUDO-sudo} bash "$path_tool/CreatePersistentImg.sh" -s "$int_size_mb" -t ext4 -l "$str_label" -o "$path_img"
        ${SUDO-sudo} chown "$(id -u):$(id -g)" "$path_img"
    done < <(manifest_entries "$path_manifest")
}
