#!/usr/bin/env bash
# shellcheck disable=SC2034
set -euo pipefail

CLI_VERSION="0.0.0"
STAMPED_DEFAULT_OS="${DEFAULT_OS}"

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
for str_lib in common prompt verify device flex fydeos flash; do
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/../lib/$str_lib.sh"
done
PATH="$PATH:$PROJECT_ROOT/.tools/bin"
DOWNLOAD_DIR="${CROS_DOWNLOAD_DIR:-$PROJECT_ROOT/downloads}"
IMAGE_PATH=""

print_usage() {
    echo "Usage: ${PROJECT_NAME} [options] flash [flash-options]"
    echo
    echo "Flash the latest ChromeOS Flex or a FydeOS image to a removable USB pendrive."
    echo
    echo "flash options:"
    echo "  --target DEV     pendrive device (asked first when omitted)"
    echo "  --os OS          chromeos-flex | fydeos (default: $STAMPED_DEFAULT_OS)"
    echo "  --channel NAME   ChromeOS Flex channel (default: STABLE)"
    echo "  --file PATH      FydeOS image you downloaded (.img.xz, .bin.zip, .img, .bin)"
    echo "  --sha256 HASH    SHA-256 FydeOS publishes for that file"
    echo "  --tool TOOL      auto | bmaptool | dd (default: auto)"
    echo "  --confirm NAME   device name, answering the erase confirmation"
    echo "  --dry-run        resolve and verify, write nothing"
    echo
    echo "Options:"
    echo "  -V, --version    Print version and exit"
    echo "  -h, --help       Show this help"
}

print_version() {
    local str_version
    if str_version=$(git -C "$PROJECT_ROOT" describe --tags --always 2>/dev/null) &&
        [ -n "$str_version" ]; then
        echo "${PROJECT_NAME} ${str_version#v}"
    else
        echo "${PROJECT_NAME} $CLI_VERSION"
    fi
}

parse_flash_args() {
    ARG_TARGET="" ARG_OS="" ARG_CHANNEL=STABLE ARG_FILE="" ARG_SHA256=""
    ARG_TOOL=auto ARG_CONFIRM="" ARG_DRY=0
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --target) ARG_TARGET="${2:?--target needs a value}" && shift ;;
            --os) ARG_OS="${2:?--os needs a value}" && shift ;;
            --channel) ARG_CHANNEL="${2:?--channel needs a value}" && shift ;;
            --file) ARG_FILE="${2:?--file needs a value}" && shift ;;
            --sha256) ARG_SHA256="${2:?--sha256 needs a value}" && shift ;;
            --tool) ARG_TOOL="${2:?--tool needs a value}" && shift ;;
            --confirm) ARG_CONFIRM="${2:?--confirm needs a value}" && shift ;;
            --dry-run) ARG_DRY=1 ;;
            *)
                print_status "error" "Unknown flash option: $1"
                return 1
                ;;
        esac
        shift
    done
}

resolve_image() {
    if [ -z "$ARG_OS" ]; then
        ask ARG_OS "OS to flash [chromeos-flex/fydeos] (default: $STAMPED_DEFAULT_OS): "
        ARG_OS="${ARG_OS:-$STAMPED_DEFAULT_OS}"
    fi
    case "$ARG_OS" in
        chromeos-flex)
            flex_resolve "$DOWNLOAD_DIR" "$ARG_CHANNEL"
            print_status "info" "ChromeOS Flex $FLEX_VERSION ($ARG_CHANNEL): $FLEX_URL"
            IMAGE_PATH="$DOWNLOAD_DIR/$FLEX_FILE"
            ;;
        fydeos) fydeos_prepare "$ARG_FILE" "$ARG_SHA256" "$DOWNLOAD_DIR" "$ARG_DRY" ;;
        *)
            print_status "error" "Unknown OS '$ARG_OS' (chromeos-flex or fydeos)"
            return 1
            ;;
    esac
}

cmd_flash() {
    parse_flash_args "$@"
    if [ -z "$ARG_TARGET" ]; then
        ask ARG_TARGET "Pendrive device path (e.g. /dev/sdb): "
    fi
    device_resolve "$ARG_TARGET"
    print_status "success" "Target: $DEVICE_PATH (removable)"

    resolve_image
    flash_argv "$ARG_TOOL" "$IMAGE_PATH" "$DEVICE_PATH"
    if [ "$ARG_DRY" = 1 ]; then
        print_status "info" "[dry-run] would write: ${LIST_FLASH_CMD[*]}"
        device_describe
        return 0
    fi

    if [ "$ARG_OS" = chromeos-flex ]; then
        flex_download "$DOWNLOAD_DIR"
    fi
    device_fits "$(stat -c %s "$IMAGE_PATH")"
    device_confirm "$ARG_CONFIRM"
    flash_image
    print_status "success" "Flashed $IMAGE_PATH to $DEVICE_PATH"
}

main() {
    case "${1:-}" in
        -V | --version) print_version ;;
        -h | --help | "") print_usage ;;
        flash)
            shift
            cmd_flash "$@"
            ;;
        *)
            print_status "error" "Unknown command: $1"
            print_usage
            exit 1
            ;;
    esac
}

main "$@"
