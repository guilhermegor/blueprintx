#!/usr/bin/env bats

load helpers/common

ENTRY='u|core|isos/Linux/Desktop|latesturl|https://h/u.iso|^u\.iso$|none:test|casper-rw||none'

build_tree() {
    write_manifest "$ENTRY"
    fixture "https://h/u.iso" "uu"
    mkdir -p "$TMP/vt"
    printf '#!/bin/bash\nwhile [ $# -gt 0 ]; do [ "$1" = -o ] && : >"$2"; shift; done\n' >"$TMP/vt/CreatePersistentImg.sh"
    export VENTOY_DIR="$TMP/vt"
    run "$CLI" layout
    run "$CLI" fetch
    run "$CLI" persistence
    run "$CLI" config
}

@test "config derives the image path from where the ISO landed" {
    build_tree
    run "$CLI" check
    [ "$status" -eq 0 ]
    grep -q '"image": "/isos/Linux/Desktop/u.iso"' "$BUILD_DIR/drive/ventoy/ventoy.json"
    grep -q '/persistance/persistence_ext4_4GB_casper-rw.dat' "$BUILD_DIR/drive/ventoy/ventoy.json"
}

@test "should fail: a persistence image path that does not exist in the tree" {
    build_tree
    sed -i 's|/isos/Linux/Desktop/u.iso|/isos/Linux/u.iso|' "$BUILD_DIR/drive/ventoy/ventoy.json"
    run "$CLI" check
    [ "$status" -ne 0 ]
    [[ "$output" == *"/isos/Linux/u.iso does not exist"* ]]
}

@test "should fail: a missing persistence backend" {
    build_tree
    rm "$BUILD_DIR/drive/persistance/"*.dat
    run "$CLI" check
    [ "$status" -ne 0 ]
}

@test "config refuses a persistence entry whose image was never resolved" {
    write_manifest "$ENTRY"
    : >"$TMP/empty.tsv"
    mkdir -p "$BUILD_DIR/drive/ventoy"
    : >"$BUILD_DIR/resolved.tsv"
    run "$CLI" config
    [ "$status" -ne 0 ]
    [[ "$output" == *"no resolved image"* ]]
}

@test "persistence size follows the conf" {
    printf 'PERSISTENCE_SIZE_MB=8192\n' >"$TMP/size.conf"
    export VENTOY_USB_CONF="$TMP/size.conf"
    build_tree
    [ -f "$BUILD_DIR/drive/persistance/persistence_ext4_8GB_casper-rw.dat" ]
}

@test "a changed persistence size replaces the old image and warns" {
    build_tree
    printf 'PERSISTENCE_SIZE_MB=8192\n' >"$TMP/size.conf"
    export VENTOY_USB_CONF="$TMP/size.conf"
    run "$CLI" persistence
    [[ "$output" == *"saved session data"* ]]
    [ ! -e "$BUILD_DIR/drive/persistance/persistence_ext4_4GB_casper-rw.dat" ]
    [ -f "$BUILD_DIR/drive/persistance/persistence_ext4_8GB_casper-rw.dat" ]
}

@test "persistence is left alone when the image already exists" {
    build_tree
    echo keep >"$BUILD_DIR/drive/persistance/persistence_ext4_4GB_casper-rw.dat"
    run "$CLI" persistence
    [ "$(cat "$BUILD_DIR/drive/persistance/persistence_ext4_4GB_casper-rw.dat")" = keep ]
}

@test "persistence is downloaded from ventoy/backend and verified against the release notes" {
    command -v 7z || skip "7z missing"
    export GITHUB_API="https://api.test"
    mkdir -p "$TMP/z/images" "$TMP/z/d"
    printf 'blank-ext4' >"$TMP/z/d/persistence_ext4_4GB_casper-rw.dat"
    (cd "$TMP/z/d" && 7z a -bso0 -bsp0 ../images/persistence_ext4_4GB_casper-rw.dat.7z persistence_ext4_4GB_casper-rw.dat)
    (cd "$TMP/z" && 7z a -bso0 -bsp0 images.zip images)
    fixture_file "https://github.com/ventoy/backend/images.zip" "$TMP/z/images.zip"
    sum="$(sha256sum "$TMP/z/images/persistence_ext4_4GB_casper-rw.dat.7z" | cut -d' ' -f1)"
    jq -n --arg b "$sum  persistence_ext4_4GB_casper-rw.dat.7z" \
        '{body: $b, assets: [{name: "images.zip", browser_download_url: "https://github.com/ventoy/backend/images.zip"}]}' \
        >"$TMP/rel.json"
    fixture_file "https://api.test/repos/ventoy/backend/releases/latest" "$TMP/rel.json"
    fixture_file "https://github.com/ventoy/backend/images.zip" "$TMP/z/images.zip"
    write_manifest "$ENTRY"
    mkdir -p "$BUILD_DIR/drive/persistance"
    export SUDO="false"
    run "$CLI" persistence
    [ "$status" -eq 0 ]
    [[ "$output" == *"downloaded from ventoy/backend"* ]]
    [ "$(cat "$BUILD_DIR/drive/persistance/persistence_ext4_4GB_casper-rw.dat")" = blank-ext4 ]
}

@test "a tampered persistence archive falls back to CreatePersistentImg.sh" {
    command -v 7z || skip "7z missing"
    export GITHUB_API="https://api.test"
    mkdir -p "$TMP/z/images" "$TMP/vt"
    printf 'x' >"$TMP/z/images/persistence_ext4_4GB_casper-rw.dat.7z"
    (cd "$TMP/z" && 7z a -bso0 -bsp0 images.zip images)
    fixture_file "https://github.com/ventoy/backend/images.zip" "$TMP/z/images.zip"
    jq -n --arg b "$(printf '%064d' 1)  persistence_ext4_4GB_casper-rw.dat.7z" \
        '{body: $b, assets: [{name: "images.zip", browser_download_url: "https://github.com/ventoy/backend/images.zip"}]}' \
        >"$TMP/rel.json"
    fixture_file "https://api.test/repos/ventoy/backend/releases/latest" "$TMP/rel.json"
    printf '#!/bin/bash\nwhile [ $# -gt 0 ]; do [ "$1" = -o ] && echo fallback >"$2"; shift; done\n' >"$TMP/vt/CreatePersistentImg.sh"
    export VENTOY_DIR="$TMP/vt"
    write_manifest "$ENTRY"
    mkdir -p "$BUILD_DIR/drive/persistance"
    run "$CLI" persistence
    [ "$status" -eq 0 ]
    [[ "$output" == *"CreatePersistentImg.sh"* ]]
    [ "$(cat "$BUILD_DIR/drive/persistance/persistence_ext4_4GB_casper-rw.dat")" = fallback ]
}

backend_release() {
    export GITHUB_API="https://api.test"
    rm -rf "$TMP/z"
    mkdir -p "$TMP/z/images" "$TMP/z/d"
    printf '%s' "$2" >"$TMP/z/d/persistence_ext4_4GB_casper-rw.dat"
    (cd "$TMP/z/d" && 7z a -bso0 -bsp0 ../images/persistence_ext4_4GB_casper-rw.dat.7z persistence_ext4_4GB_casper-rw.dat)
    (cd "$TMP/z" && 7z a -bso0 -bsp0 images.zip images)
    fixture_file "https://github.com/ventoy/backend/images.zip" "$TMP/z/images.zip"
    sum="$(sha256sum "$TMP/z/images/persistence_ext4_4GB_casper-rw.dat.7z" | cut -d' ' -f1)"
    jq -n --arg t "$1" --arg b "$sum  persistence_ext4_4GB_casper-rw.dat.7z" \
        '{tag_name: $t, body: $b, assets: [{name: "images.zip", browser_download_url: "https://github.com/ventoy/backend/images.zip"}]}' \
        >"$TMP/rel.json"
    fixture_file "https://api.test/repos/ventoy/backend/releases/latest" "$TMP/rel.json"
}

prepare_persistence() {
    write_manifest "$ENTRY"
    mkdir -p "$BUILD_DIR/drive/persistance"
    echo "$1" >"$BUILD_DIR/drive/persistance/persistence_ext4_4GB_casper-rw.dat"
    printf '%s' "$2" >"$BUILD_DIR/drive/persistance/.persistence-release"
}

@test "a newer ventoy/backend release replaces the image, warns and records the release" {
    command -v 7z || skip "7z missing"
    backend_release v5.0 fresh
    prepare_persistence session v4.0
    run "$CLI" persistence
    [ "$status" -eq 0 ]
    [[ "$output" == *"saved session data is lost"* ]]
    [ "$(cat "$BUILD_DIR/drive/persistance/persistence_ext4_4GB_casper-rw.dat")" = fresh ]
    [ "$(cat "$BUILD_DIR/drive/persistance/.persistence-release")" = v5.0 ]
}

@test "--keep-persistence leaves the image alone" {
    command -v 7z || skip "7z missing"
    backend_release v5.0 fresh
    prepare_persistence session v4.0
    run "$CLI" persistence --keep-persistence
    [ "$(cat "$BUILD_DIR/drive/persistance/persistence_ext4_4GB_casper-rw.dat")" = session ]
}

@test "the same release keeps the image" {
    command -v 7z || skip "7z missing"
    backend_release v5.0 fresh
    prepare_persistence session v5.0
    run "$CLI" persistence
    [ "$(cat "$BUILD_DIR/drive/persistance/persistence_ext4_4GB_casper-rw.dat")" = session ]
}
