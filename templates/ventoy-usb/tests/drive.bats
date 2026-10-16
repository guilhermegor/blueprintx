#!/usr/bin/env bats

load helpers/common

make_stubs() {
    mkdir -p "$TMP/vt" "$BUILD_DIR/drive/isos/Linux/Desktop" "$BUILD_DIR/drive/ventoy" "$TMP/mnt"
    printf '#!/bin/sh\necho "$@" >>"%s/ventoy.log"\n' "$TMP" >"$TMP/vt/Ventoy2Disk.sh"
    cat >"$TMP/lsblk" <<STUB
#!/bin/sh
case "\$*" in
    *PKNAME*) [ "\$LAST" = "/dev/sdb1" ] && echo sdb ;;
    *TYPE,RM*) echo "\$STUB_TYPE_RM" ;;
    *LABEL*) printf 'Ventoy\nVTOYEFI\n' | { [ "\$STUB_VENTOY" = 1 ] && cat; } ;;
    *) echo "sdb  Stub Disk 16G" ;;
esac
STUB
    sed -i '2i for LAST in "$@"; do :; done' "$TMP/lsblk"
    printf '#!/bin/sh\necho /dev/sdb1\n' >"$TMP/findmnt"
    chmod +x "$TMP/lsblk" "$TMP/findmnt"
    export LSBLK="$TMP/lsblk" FINDMNT="$TMP/findmnt" VENTOY_DIR="$TMP/vt" DRIVE_MNT="$TMP/mnt"
    export STUB_TYPE_RM="disk 1" STUB_VENTOY=1
    write_manifest 'u|core|isos/Linux/Desktop|latesturl|https://h/u.iso|^u-[0-9]+\.iso$|none:t|||none'
    echo new >"$BUILD_DIR/drive/isos/Linux/Desktop/u-2.iso"
    printf 'u\tisos/Linux/Desktop/u-2.iso\n' >"$BUILD_DIR/resolved.tsv"
}

@test "drive without --target and without a terminal refuses" {
    make_stubs
    run "$CLI" drive --dry-run </dev/null
    [ "$status" -ne 0 ]
    [[ "$output" == *"no target given"* ]]
}

@test "drive refuses a non-removable device" {
    make_stubs
    STUB_TYPE_RM="disk 0" run "$CLI" drive --target /dev/sda --dry-run
    [ "$status" -ne 0 ]
    [[ "$output" == *"not a removable disk"* ]]
}

@test "drive refuses a partition-typed device" {
    make_stubs
    STUB_TYPE_RM="part 1" run "$CLI" drive --target /dev/sdb --dry-run
    [ "$status" -ne 0 ]
}

@test "a mount-point target resolves to its parent device" {
    make_stubs
    STUB_TYPE_RM="disk 0" run "$CLI" drive --target /media/x
    [[ "$output" == *"/dev/sdb is not a removable disk"* ]]
}

@test "sync mode never runs Ventoy2Disk, copies new files and replaces the older version" {
    make_stubs
    mkdir -p "$TMP/mnt/isos/Linux/Desktop"
    echo old >"$TMP/mnt/isos/Linux/Desktop/u-1.iso"
    run "$CLI" drive --target /dev/sdb </dev/null
    [ "$status" -eq 0 ]
    [[ "$output" == *"sync mode"* ]]
    [ ! -e "$TMP/ventoy.log" ]
    [ -f "$TMP/mnt/isos/Linux/Desktop/u-2.iso" ]
    [ ! -e "$TMP/mnt/isos/Linux/Desktop/u-1.iso" ]
}

@test "an extra item is kept by default and deleted only on an explicit yes" {
    make_stubs
    mkdir -p "$TMP/mnt/.Trash-1000"
    echo x >"$TMP/mnt/stray.txt"
    run "$CLI" drive --target /dev/sdb </dev/null
    [ -e "$TMP/mnt/stray.txt" ]
    [ -d "$TMP/mnt/.Trash-1000" ]
    run "$CLI" drive --target /dev/sdb <<<$'y\nn'
    [ ! -e "$TMP/mnt/stray.txt" ]
    [ -d "$TMP/mnt/.Trash-1000" ]
}

@test "--yes-delete-extras deletes extras without asking" {
    make_stubs
    echo x >"$TMP/mnt/stray.txt"
    run "$CLI" drive --target /dev/sdb --yes-delete-extras </dev/null
    [ ! -e "$TMP/mnt/stray.txt" ]
}

@test "install mode aborts on a wrong confirmation and never runs Ventoy2Disk" {
    make_stubs
    STUB_VENTOY=0 run "$CLI" drive --target /dev/sdb <<<"/dev/other"
    [ "$status" -ne 0 ]
    [[ "$output" == *"ERASED"* ]]
    [[ "$output" == *"confirmation did not match"* ]]
    [ ! -e "$TMP/ventoy.log" ]
}

@test "install mode runs Ventoy2Disk -I after the typed confirmation, then syncs" {
    make_stubs
    STUB_VENTOY=0 run "$CLI" drive --target /dev/sdb <<<"/dev/sdb"
    [ "$status" -eq 0 ]
    grep -q -- "-I /dev/sdb" "$TMP/ventoy.log"
    [ -f "$TMP/mnt/isos/Linux/Desktop/u-2.iso" ]
}

@test "dry-run changes nothing in either mode" {
    make_stubs
    echo old >"$TMP/mnt/stray.txt"
    run "$CLI" drive --target /dev/sdb --dry-run
    [ "$status" -eq 0 ]
    [ ! -e "$TMP/mnt/isos/Linux/Desktop/u-2.iso" ]
    [ -e "$TMP/mnt/stray.txt" ]
    STUB_VENTOY=0 run "$CLI" drive --target /dev/sdb --dry-run
    [ "$status" -eq 0 ]
    [ ! -e "$TMP/ventoy.log" ]
}

@test "persistence is copied only when missing and a changed one warns" {
    make_stubs
    mkdir -p "$BUILD_DIR/drive/persistance" "$TMP/mnt/persistance"
    echo new >"$BUILD_DIR/drive/persistance/persistence_ext4_8GB_casper-rw.dat"
    echo old >"$TMP/mnt/persistance/persistence_ext4_4GB_casper-rw.dat"
    run "$CLI" drive --target /dev/sdb </dev/null
    [[ "$output" == *"saved session data"* ]]
    [ -f "$TMP/mnt/persistance/persistence_ext4_8GB_casper-rw.dat" ]
    [ ! -e "$TMP/mnt/persistance/persistence_ext4_4GB_casper-rw.dat" ]
    echo keep >"$TMP/mnt/persistance/persistence_ext4_8GB_casper-rw.dat"
    run "$CLI" drive --target /dev/sdb </dev/null
    [ "$(cat "$TMP/mnt/persistance/persistence_ext4_8GB_casper-rw.dat")" = keep ]
}

@test "a symlink on the drive is removed itself and its target is never followed" {
    make_stubs
    mkdir -p "$TMP/outside"
    echo keep >"$TMP/outside/precious"
    ln -s "$TMP/outside" "$TMP/mnt/link"
    run "$CLI" drive --target /dev/sdb --yes-delete-extras </dev/null
    [ ! -e "$TMP/mnt/link" ]
    [ -f "$TMP/outside/precious" ]
}

sync_persistence() {
    make_stubs
    mkdir -p "$BUILD_DIR/drive/persistance" "$TMP/mnt/persistance"
    echo new >"$BUILD_DIR/drive/persistance/persistence_ext4_4GB_casper-rw.dat"
    printf v5.0 >"$BUILD_DIR/drive/persistance/.persistence-release"
    echo session >"$TMP/mnt/persistance/persistence_ext4_4GB_casper-rw.dat"
    printf v4.0 >"$TMP/mnt/persistance/.persistence-release"
}

@test "sync replaces the drive image when the build carries a newer release" {
    sync_persistence
    run "$CLI" drive --target /dev/sdb </dev/null
    [[ "$output" == *"saved session data"* ]]
    [ "$(cat "$TMP/mnt/persistance/persistence_ext4_4GB_casper-rw.dat")" = new ]
    [ "$(cat "$TMP/mnt/persistance/.persistence-release")" = v5.0 ]
}

@test "sync with --keep-persistence keeps the session" {
    sync_persistence
    run "$CLI" drive --target /dev/sdb --keep-persistence </dev/null
    [ "$(cat "$TMP/mnt/persistance/persistence_ext4_4GB_casper-rw.dat")" = session ]
}

@test "a symlinked directory pointing outside the mount is never traversed" {
    make_stubs
    mkdir -p "$TMP/outside/sub"
    echo keep >"$TMP/outside/sub/precious"
    ln -s "$TMP/outside" "$TMP/mnt/isos"
    run "$CLI" drive --target /dev/sdb --yes-delete-extras </dev/null
    [ -f "$TMP/outside/sub/precious" ]
}

@test "files are never replaced through a symlinked parent that escapes the mount" {
    make_stubs
    mkdir -p "$TMP/outside"
    echo keep >"$TMP/outside/u-1.iso"
    mkdir -p "$TMP/mnt/isos/Linux"
    ln -s "$TMP/outside" "$TMP/mnt/isos/Linux/Desktop"
    run "$CLI" drive --target /dev/sdb </dev/null
    [ -f "$TMP/outside/u-1.iso" ]
    [[ "$output" == *"resolves outside the drive"* ]]
}
