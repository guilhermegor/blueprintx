#!/usr/bin/env bash

drive_guard() {
    local str_dev="$1" str_info str_type str_rm
    if [ -z "$str_dev" ]; then
        print_status "error" "no device given: pass DEVICE=/dev/sdX explicitly"
        return 1
    fi
    if [[ "$str_dev" != /dev/* ]]; then
        print_status "error" "'$str_dev' is not a /dev path"
        return 1
    fi
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

drive_partition() {
    case "$1" in
        *[0-9]) printf '%sp1' "$1" ;;
        *) printf '%s1' "$1" ;;
    esac
}

drive_write() {
    local str_dev="$1" path_drive="$2" path_cache="$3" str_dry="$4" str_answer path_mnt
    drive_guard "$str_dev" || return 1
    if [ "$str_dry" = 1 ]; then
        print_status "info" "dry-run: would ERASE $str_dev and run Ventoy2Disk.sh -I $str_dev"
        print_status "info" "dry-run: would mount $(drive_partition "$str_dev") and rsync $path_drive/ onto it"
        return 0
    fi
    print_status "warning" "ALL DATA ON $str_dev WILL BE DESTROYED"
    read -r -p "Type the device path again to confirm: " str_answer || true
    if [ "$str_answer" != "$str_dev" ]; then
        print_status "error" "confirmation did not match: aborting"
        return 1
    fi
    ${SUDO-sudo} bash "$(dirname "$(ls "$path_cache"/ventoy-*/Ventoy2Disk.sh)")/Ventoy2Disk.sh" -I "$str_dev"
    path_mnt="$(mktemp -d)"
    ${SUDO-sudo} mount "$(drive_partition "$str_dev")" "$path_mnt"
    ${SUDO-sudo} rsync -rt --no-perms --no-owner --no-group "$path_drive/" "$path_mnt/"
    ${SUDO-sudo} umount "$path_mnt"
    rmdir "$path_mnt"
}
