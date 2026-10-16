#!/usr/bin/env bash

DEVICE_PATH=""

device_resolve() {
    local str_real str_type str_parent str_removable
    str_real="$(readlink -f -- "$1")"
    str_type="$(lsblk -dno TYPE -- "$str_real" 2>/dev/null | tr -d ' ')" || true
    case "$str_type" in
        disk) DEVICE_PATH="$str_real" ;;
        part)
            str_parent="$(lsblk -no PKNAME -- "$str_real" | head -n1)"
            DEVICE_PATH="/dev/$str_parent"
            ;;
        *)
            print_status "error" "$1 is not a block device"
            return 1
            ;;
    esac
    str_removable="$(lsblk -dno RM -- "$DEVICE_PATH" | tr -d ' ')"
    if [ "$str_removable" != "1" ]; then
        print_status "error" "$DEVICE_PATH is not a removable device; refusing to touch it"
        return 1
    fi
    if lsblk -nro MOUNTPOINT -- "$DEVICE_PATH" | grep -q .; then
        print_status "error" "$DEVICE_PATH has mounted partitions; unmount them first"
        return 1
    fi
}

device_size() {
    lsblk -bdno SIZE -- "$DEVICE_PATH" | tr -d ' '
}

device_describe() {
    lsblk -o NAME,MODEL,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINT -- "$DEVICE_PATH"
}

device_fits() {
    local int_image_size="$1" int_device_size
    int_device_size="$(device_size)"
    if [ "$int_image_size" -gt "$int_device_size" ]; then
        print_status "error" "image ($int_image_size bytes) is larger than $DEVICE_PATH ($int_device_size bytes)"
        return 1
    fi
}

device_confirm() {
    local str_name="${DEVICE_PATH##*/}" str_answer="${1:-}"
    print_status "warning" "ALL DATA on $DEVICE_PATH will be ERASED:"
    device_describe
    if [ -z "$str_answer" ]; then
        ask str_answer "Type the device name ($str_name) to confirm: "
    fi
    if [ "$str_answer" != "$str_name" ]; then
        print_status "error" "Not confirmed; nothing was written"
        return 1
    fi
}
