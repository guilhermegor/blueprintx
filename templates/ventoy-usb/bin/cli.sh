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
TOOLS_DIR="${TOOLS_DIR:-$PROJECT_ROOT/.tools}"
export BUILD_DIR TOOLS_DIR

print_usage() {
    echo "Usage: ${PROJECT_NAME} [options] <command>"
    echo
    echo "Commands:"
    echo "  layout       Create the empty drive tree under build/drive"
    echo "  tools        Download the latest Ventoy release into .tools/ (checksum-verified)"
    echo "  fetch        Download and verify the latest version of every manifest entry"
    echo "  persistence  Create the empty persistence image (needs root)"
    echo "  config       Generate ventoy/ventoy.json from the manifest"
    echo "  check        Fail if ventoy.json points at a path missing from the tree"
    echo "  build        layout + fetch + payload overlay + persistence + config + check"
    echo "  drive        Sync the tree to the pendrive; installs Ventoy first if it is absent"
    echo
    echo "Options:"
    echo "  --target PATH  Pendrive mount point or /dev/sdX; asked for when omitted"
    echo "  --dry-run      Print what 'drive' would do and touch nothing"
    echo "  --yes-delete-extras  Delete drive items outside the layout without asking"
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

overlay_payload() {
    [ -d "$PROJECT_ROOT/payload" ] || return 0
    rsync -a --exclude=.gitkeep "$PROJECT_ROOT/payload/" "$DRIVE_DIR/"
}

cmd_fetch() {
    fetch_all "$MANIFEST_FILE" "$DRIVE_DIR" "$BUILD_DIR/resolved.tsv"
}

cmd_build() {
    local int_rc=0
    layout_create "$MANIFEST_FILE" "$DRIVE_DIR"
    cmd_fetch || int_rc=1
    overlay_payload
    persistence_create "$MANIFEST_FILE" "$DRIVE_DIR" "$PERSISTENCE_SIZE_MB"
    ventoy_json_generate "$MANIFEST_FILE" "$DRIVE_DIR" "$BUILD_DIR/resolved.tsv" "$PERSISTENCE_SIZE_MB"
    ventoy_json_check "$DRIVE_DIR"
    return "$int_rc"
}

main() {
    local str_cmd="" str_target="" int_dry=0 int_yes=0
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
            --target)
                str_target="${2:-}"
                shift
                ;;
            --dry-run) int_dry=1 ;;
            --yes-delete-extras) int_yes=1 ;;
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
        tools) tools_ensure "$MANIFEST_FILE" ;;
        fetch) cmd_fetch ;;
        persistence) persistence_create "$MANIFEST_FILE" "$DRIVE_DIR" "$PERSISTENCE_SIZE_MB" ;;
        config) ventoy_json_generate "$MANIFEST_FILE" "$DRIVE_DIR" "$BUILD_DIR/resolved.tsv" "$PERSISTENCE_SIZE_MB" ;;
        check) ventoy_json_check "$DRIVE_DIR" ;;
        build) cmd_build ;;
        drive)
            DRY_RUN="$int_dry"
            export DRY_RUN
            drive_write "$str_target" "$MANIFEST_FILE" "$DRIVE_DIR" "$BUILD_DIR/resolved.tsv" "$int_yes"
            ;;
        *)
            print_status "error" "Unknown command: $str_cmd"
            print_usage
            return 1
            ;;
    esac
}

main "$@"
