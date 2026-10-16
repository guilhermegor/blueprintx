#!/usr/bin/env bash

LIST_FLASH_CMD=()

flash_argv() {
    local str_choice="$1" str_image="$2" str_dev="$3" str_bmap=""
    str_bmap="$(command -v bmaptool || true)"
    if [ "$str_choice" = auto ]; then
        str_choice="dd"
        [ -z "$str_bmap" ] || str_choice="bmaptool"
    fi
    case "$str_choice" in
        bmaptool)
            if [ -z "$str_bmap" ]; then
                print_status "error" "bmaptool not found; run 'make tools' or use --tool dd"
                return 1
            fi
            LIST_FLASH_CMD=("$str_bmap" copy --nobmap "$str_image" "$str_dev")
            ;;
        dd) LIST_FLASH_CMD=(dd "if=$str_image" "of=$str_dev" bs=4M conv=fsync status=progress) ;;
        *)
            print_status "error" "unknown flash tool '$str_choice' (auto, dd, bmaptool)"
            return 1
            ;;
    esac
}

flash_image() {
    local -a list_sudo=()
    if [ "$(id -u)" != 0 ]; then
        read -r -a list_sudo <<<"${CROS_SUDO-sudo}"
    fi
    "${list_sudo[@]+"${list_sudo[@]}"}" "${LIST_FLASH_CMD[@]}"
    "${list_sudo[@]+"${list_sudo[@]}"}" sync
}
