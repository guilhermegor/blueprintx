#!/usr/bin/env bash
# shellcheck disable=SC2034

fydeos_prepare() {
    local str_file="$1" str_sha256="$2" str_dir="$3" str_dry="$4" str_out
    if [ -z "$str_file" ]; then
        ask str_file "Path to the FydeOS image you downloaded: "
    fi
    if [ ! -f "$str_file" ]; then
        print_status "error" "FydeOS image not found: '$str_file' (download it from fydeos.io/download)"
        return 1
    fi
    if [ -z "$str_sha256" ]; then
        ask str_sha256 "SHA-256 published on the FydeOS download page: "
    fi
    verify_hash sha256 "${str_sha256:-missing}" "$str_file" || return 1
    str_out="$str_dir/$(basename "${str_file%.*}")"
    case "$str_file" in
        *.img.xz) [ "$str_dry" = 1 ] || { mkdir -p "$str_dir" && xz -dc "$str_file" >"$str_out"; } ;;
        *.zip)
            str_out="$str_dir/$(unzip -Z1 "$str_file" | head -n1)"
            [ "$str_dry" = 1 ] || { mkdir -p "$str_dir" && unzip -o -q -d "$str_dir" "$str_file"; }
            ;;
        *.img | *.bin) str_out="$str_file" ;;
        *)
            print_status "error" "unsupported FydeOS image type: $str_file (.img.xz, .bin.zip, .img, .bin)"
            return 1
            ;;
    esac
    IMAGE_PATH="$str_out"
}
