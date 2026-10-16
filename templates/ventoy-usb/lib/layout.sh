#!/usr/bin/env bash

LAYOUT_STATIC_DIRS=(dotfiles dotfiles/windows persistance recovery_tools dynfileos temp ventoy)

layout_dirs() {
    local path_manifest="$1" str_line str_folder
    printf '%s\n' "${LAYOUT_STATIC_DIRS[@]}"
    while IFS= read -r str_line; do
        str_folder="$(manifest_field "$str_line" 3)"
        [ "$str_folder" = "@tools" ] || printf '%s\n' "$str_folder"
    done < <(manifest_entries_all "$path_manifest")
}

manifest_entries_all() {
    INCLUDE_WINDOWS=y INCLUDE_ANDROID=y manifest_entries "$1"
}

layout_create() {
    local path_manifest="$1" path_drive="$2" str_dir
    manifest_entries_all "$path_manifest" >/dev/null || return 1
    while IFS= read -r str_dir; do
        mkdir -p "$path_drive/$str_dir"
    done < <(layout_dirs "$path_manifest")
}
