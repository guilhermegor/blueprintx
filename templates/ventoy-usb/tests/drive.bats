#!/usr/bin/env bats

load helpers/common

lsblk_stub() {
    printf '#!/bin/sh\necho "%s"\n' "$1" >"$TMP/lsblk"
    chmod +x "$TMP/lsblk"
    export LSBLK="$TMP/lsblk"
}

@test "drive refuses an implicit device" {
    run "$CLI" drive --dry-run
    [ "$status" -ne 0 ]
    [[ "$output" == *"no device given"* ]]
}

@test "drive refuses a path outside /dev" {
    run "$CLI" drive --device ./sdb --dry-run
    [ "$status" -ne 0 ]
}

@test "drive refuses a non-removable device" {
    lsblk_stub "disk 0"
    run "$CLI" drive --device /dev/sda --dry-run
    [ "$status" -ne 0 ]
    [[ "$output" == *"not a removable disk"* ]]
}

@test "drive refuses a partition even when removable" {
    lsblk_stub "part 1"
    run "$CLI" drive --device /dev/sdb1 --dry-run
    [ "$status" -ne 0 ]
}

@test "dry-run on a removable disk prints the plan and writes nothing" {
    lsblk_stub "disk 1"
    export SUDO="false"
    run "$CLI" drive --device /dev/sdb --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"dry-run: would ERASE /dev/sdb"* ]]
}

@test "a wrong confirmation aborts before anything runs" {
    lsblk_stub "disk 1"
    export SUDO="false"
    run "$CLI" drive --device /dev/sdb <<<"/dev/other"
    [ "$status" -ne 0 ]
    [[ "$output" == *"confirmation did not match"* ]]
}
