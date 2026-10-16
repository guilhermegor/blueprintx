#!/usr/bin/env bash

drive_resolve_device() {
    local str_target="$1" str_src str_parent
    if [[ "$str_target" == /dev/* ]]; then
        str_src="$str_target"
    else
        str_src="$("${FINDMNT:-findmnt}" -no SOURCE --target "$str_target" 2>/dev/null)" || {
            print_status "error" "$str_target is not a mount point or a /dev path"
            return 1
        }
    fi
    str_parent="$("${LSBLK:-lsblk}" -dnro PKNAME "$str_src" 2>/dev/null)" || true
    if [ -n "$str_parent" ]; then
        printf '/dev/%s' "$str_parent"
    else
        printf '%s' "$str_src"
    fi
}

drive_guard() {
    local str_dev="$1" str_info str_type str_rm
    str_info="$("${LSBLK:-lsblk}" -dnro TYPE,RM "$str_dev" 2>/dev/null)" || {
        print_status "error" "$str_dev: not a block device"
        return 1
    }
    read -r str_type str_rm <<<"$str_info"
    if [ "$str_type" != disk ] || [ "$str_rm" != 1 ]; then
        print_status "error" "$str_dev is not a removable disk (TYPE=$str_type RM=$str_rm): refusing"
        return 1
    fi
}

drive_has_ventoy() {
    "${LSBLK:-lsblk}" -nro LABEL "$1" 2>/dev/null | grep -qx VTOYEFI
}

drive_partition() {
    case "$1" in
        *[0-9]) printf '%sp1' "$1" ;;
        *) printf '%s1' "$1" ;;
    esac
}

drive_prompt_target() {
    local str_target=""
    if [ ! -t 0 ]; then
        print_status "error" "no target given: pass --target <mount point or /dev/sdX>"
        return 1
    fi
    read -r -p "Path of the pendrive (mount point or /dev/sdX): " str_target || true
    [ -n "$str_target" ] || {
        print_status "error" "no target given"
        return 1
    }
    printf '%s' "$str_target"
}

drive_install() {
    local str_dev="$1" str_answer
    print_status "warning" "Ventoy is NOT installed on $str_dev: ALL DATA ON THE WHOLE DEVICE WILL BE ERASED"
    "${LSBLK:-lsblk}" -o NAME,MODEL,SIZE,FSTYPE,LABEL "$str_dev" || true
    read -r -p "Type the device name ($str_dev) to confirm: " str_answer || true
    if [ "$str_answer" != "$str_dev" ]; then
        print_status "error" "confirmation did not match: aborting"
        return 1
    fi
    ${SUDO-sudo} bash "${VENTOY_DIR:-$(tools_ventoy_dir)}/Ventoy2Disk.sh" -I "$str_dev"
}

drive_data_mount() {
    local str_dev="$1"
    DRIVE_MNT_PATH="${DRIVE_MNT:-}"
    [ -z "$DRIVE_MNT_PATH" ] || return 0
    DRIVE_MNT_PATH="$("${LSBLK:-lsblk}" -nro MOUNTPOINT,LABEL "$str_dev" | awk '$2 == "Ventoy" && $1 != "" { print $1; exit }')"
    if [ -z "$DRIVE_MNT_PATH" ]; then
        DRIVE_MNT_PATH="$(mktemp -d)"
        DRIVE_MOUNTED_BY_US="$DRIVE_MNT_PATH"
        ${SUDO-sudo} mount "$(drive_partition "$str_dev")" "$DRIVE_MNT_PATH"
    fi
}

drive_cleanup_mount() {
    [ -z "${DRIVE_MOUNTED_BY_US:-}" ] || {
        ${SUDO-sudo} umount "$DRIVE_MOUNTED_BY_US" || true
        rmdir "$DRIVE_MOUNTED_BY_US" 2>/dev/null || true
        DRIVE_MOUNTED_BY_US=""
    }
}

drive_replace_managed() {
    local path_manifest="$1" path_mnt="$2" path_resolved="$3" str_id str_rel str_line
    while IFS=$'\t' read -r str_id str_rel; do
        str_line="$(manifest_entries "$path_manifest" | grep "^$str_id|")" || continue
        remove_older_versions "$path_mnt/$(dirname "$str_rel")" "$(manifest_field "$str_line" 6)" "$(basename "$str_rel")"
    done <"$path_resolved"
}

drive_copy_persistence() {
    local path_drive="$1" path_mnt="$2" path_img str_name str_label
    for path_img in "$path_drive"/persistance/*.dat; do
        [ -f "$path_img" ] || continue
        str_name="$(basename "$path_img")"
        [ ! -f "$path_mnt/persistance/$str_name" ] || continue
        str_label="${str_name#persistence_ext4_*GB_}"
        if compgen -G "$path_mnt/persistance/persistence_ext4_*_$str_label" >/dev/null; then
            print_status "warning" "persistence image changed: saved session data on the drive is lost"
            ${DRIVE_RUN-} rm -f "$path_mnt"/persistance/persistence_ext4_*_"$str_label"
        fi
        if [ "${DRY_RUN:-0}" = 1 ]; then
            print_status "info" "dry-run: would copy $str_name"
        else
            ${DRIVE_RUN-} mkdir -p "$path_mnt/persistance"
            ${DRIVE_RUN-} cp "$path_img" "$path_mnt/persistance/$str_name"
        fi
    done
}

drive_offer_extras() {
    local path_drive="$1" path_mnt="$2" str_rel="$3" yes_all="$4" path_item str_name str_answer
    for path_item in "$path_mnt/$str_rel"/* "$path_mnt/$str_rel"/.[!.]*; do
        [ -e "$path_item" ] || continue
        str_name="${path_item#"$path_mnt"/}"
        if [ ! -e "$path_drive/$str_name" ]; then
            str_answer=n
            if [ "$yes_all" = 1 ]; then
                str_answer=y
            elif [ "${DRY_RUN:-0}" = 1 ]; then
                print_status "info" "dry-run: extra on the drive, would ask: delete $str_name?"
                continue
            else
                read -r -p "delete $str_name? [y/N] " str_answer || str_answer=n
            fi
            case "$str_answer" in y | Y) ${DRIVE_RUN-} rm -rf "$path_item" ;; esac
        elif [ -d "$path_item" ]; then
            drive_offer_extras "$path_drive" "$path_mnt" "$str_name" "$yes_all"
        fi
    done
}

drive_sync() {
    local path_manifest="$1" path_drive="$2" path_mnt="$3" path_resolved="$4" yes_all="$5"
    local -a list_rsync=(-rt --no-perms --no-owner --no-group --exclude=/persistance/)
    DRIVE_RUN=""
    [ -w "$path_mnt" ] || DRIVE_RUN="${SUDO-sudo}"
    [ "${DRY_RUN:-0}" != 1 ] || list_rsync+=(-n -i)
    drive_replace_managed "$path_manifest" "$path_mnt" "$path_resolved"
    ${DRIVE_RUN-} rsync "${list_rsync[@]}" "$path_drive/" "$path_mnt/"
    drive_copy_persistence "$path_drive" "$path_mnt"
    drive_offer_extras "$path_drive" "$path_mnt" "" "$yes_all"
}

drive_write() {
    local str_target="$1" path_manifest="$2" path_drive="$3" path_resolved="$4" yes_all="$5"
    local str_dev
    [ -n "$str_target" ] || str_target="$(drive_prompt_target)" || return 1
    str_dev="$(drive_resolve_device "$str_target")" || return 1
    drive_guard "$str_dev" || return 1
    if drive_has_ventoy "$str_dev"; then
        print_status "info" "Ventoy found on $str_dev: sync mode"
    elif [ "${DRY_RUN:-0}" = 1 ]; then
        print_status "info" "dry-run: Ventoy is absent on $str_dev; would ERASE it, run Ventoy2Disk.sh -I, then sync"
        return 0
    else
        tools_ensure "$path_manifest" || return 1
        drive_install "$str_dev" || return 1
    fi
    trap drive_cleanup_mount EXIT
    drive_data_mount "$str_dev"
    drive_sync "$path_manifest" "$path_drive" "$DRIVE_MNT_PATH" "$path_resolved" "$yes_all"
    drive_cleanup_mount
}
