#!/usr/bin/env bash
set -euo pipefail

CLI_VERSION="0.0.0"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
for str_lib in manifest resolve layout ventoy_config drive; do
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/../lib/$str_lib.sh"
done

CONF_FILE="${VENTOY_USB_CONF:-$PROJECT_ROOT/ventoy-usb.conf}"
# shellcheck source=/dev/null
[ ! -f "$CONF_FILE" ] || source "$CONF_FILE"
PERSISTENCE_SIZE_MB="${PERSISTENCE_SIZE_MB:-4096}"
MANIFEST_FILE="${MANIFEST_FILE:-$PROJECT_ROOT/sources.manifest}"
BUILD_DIR="${BUILD_DIR:-$PROJECT_ROOT/build}"
DRIVE_DIR="$BUILD_DIR/drive"
CACHE_DIR="$BUILD_DIR/cache"

print_usage() {
    echo "Usage: ${PROJECT_NAME} [options] <command>"
    echo
    echo "Commands:"
    echo "  layout       Create the empty drive tree under build/drive"
    echo "  fetch        Download and verify every manifest entry"
    echo "  persistence  Create the empty persistence image (needs root)"
    echo "  config       Generate ventoy/ventoy.json from the manifest"
    echo "  check        Fail if ventoy.json points at a path missing from the tree"
    echo "  build        layout + fetch + manual overlay + persistence + config + check"
    echo "  drive        Write the tree to --device /dev/sdX (destructive)"
    echo
    echo "Options:"
    echo "  --device DEV   Target for 'drive'; never inferred"
    echo "  --dry-run      Print what 'drive' would do and touch nothing"
    echo "  -V, --version  Print version and exit"
    echo "  -h, --help     Show this help"
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

overlay_manual() {
    [ -d "$PROJECT_ROOT/manual" ] || return 0
    rsync -a "$PROJECT_ROOT/manual/" "$DRIVE_DIR/"
}

cmd_build() {
    layout_create "$MANIFEST_FILE" "$DRIVE_DIR"
    mkdir -p "$CACHE_DIR"
    fetch_all "$MANIFEST_FILE" "$DRIVE_DIR" "$CACHE_DIR" "$BUILD_DIR/resolved.tsv"
    overlay_manual
    persistence_create "$MANIFEST_FILE" "$DRIVE_DIR" "$PERSISTENCE_SIZE_MB" "$CACHE_DIR"
    ventoy_json_generate "$MANIFEST_FILE" "$DRIVE_DIR" "$BUILD_DIR/resolved.tsv" "$PERSISTENCE_SIZE_MB"
    ventoy_json_check "$DRIVE_DIR"
}

main() {
    local str_cmd="" str_device="" int_dry=0
    while [ "$#" -gt 0 ]; do
        case "$1" in
            -V | --version)
                print_version
                return 0
                ;;
            -h | --help)
                print_usage
                return 0
                ;;
            --device)
                str_device="${2:-}"
                shift
                ;;
            --dry-run) int_dry=1 ;;
            -*)
                print_status "error" "Unknown option: $1"
                print_usage
                return 1
                ;;
            *) str_cmd="${str_cmd:-$1}" ;;
        esac
        shift
    done
    case "$str_cmd" in
        "") print_usage ;;
        layout) layout_create "$MANIFEST_FILE" "$DRIVE_DIR" ;;
        fetch)
            mkdir -p "$CACHE_DIR"
            fetch_all "$MANIFEST_FILE" "$DRIVE_DIR" "$CACHE_DIR" "$BUILD_DIR/resolved.tsv"
            ;;
        persistence) persistence_create "$MANIFEST_FILE" "$DRIVE_DIR" "$PERSISTENCE_SIZE_MB" "$CACHE_DIR" ;;
        config) ventoy_json_generate "$MANIFEST_FILE" "$DRIVE_DIR" "$BUILD_DIR/resolved.tsv" "$PERSISTENCE_SIZE_MB" ;;
        check) ventoy_json_check "$DRIVE_DIR" ;;
        build) cmd_build ;;
        drive) drive_write "$str_device" "$DRIVE_DIR" "$CACHE_DIR" "$int_dry" ;;
        *)
            print_status "error" "Unknown command: $str_cmd"
            print_usage
            return 1
            ;;
    esac
}

main "$@"
