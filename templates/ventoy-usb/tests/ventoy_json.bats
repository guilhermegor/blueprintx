#!/usr/bin/env bats

load helpers/common

ENTRY='u|core|isos/Linux/Desktop|pinned|https://h/u.iso|-|none:test|casper-rw'

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
