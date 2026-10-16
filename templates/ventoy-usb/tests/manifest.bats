#!/usr/bin/env bats

load helpers/common

@test "the shipped manifest parses" {
    run bash -c "source '$ROOT/lib/common.sh'; source '$ROOT/lib/manifest.sh'; manifest_entries '$ROOT/sources.manifest' | wc -l"
    [ "$status" -eq 0 ]
    [ "$output" -gt 20 ]
}

@test "an entry without a checksum fails closed" {
    write_manifest "x|core|isos/Others|github|o/r|^x$|||"
    run "$CLI" layout
    [ "$status" -ne 0 ]
    [[ "$output" == *"fail closed"* ]]
}

@test "none: without a reason is rejected" {
    write_manifest "x|core|isos/Others|latesturl|https://h/x.iso|^x\.iso$|none:||"
    run "$CLI" layout
    [ "$status" -ne 0 ]
}

@test "a wrong field count is rejected" {
    write_manifest "x|core|isos/Others|latesturl"
    run "$CLI" layout
    [ "$status" -ne 0 ]
    [[ "$output" == *"9 '|'-separated fields"* ]]
}

@test "windows and android groups follow the conf" {
    source "$ROOT/lib/common.sh"
    source "$ROOT/lib/manifest.sh"
    INCLUDE_WINDOWS=n INCLUDE_ANDROID=n run manifest_entries "$ROOT/sources.manifest"
    [ "$status" -eq 0 ]
    [[ "$output" != *"|windows|"* ]]
    [[ "$output" != *"|android|"* ]]
    [[ "$output" == *"|core|"* ]]
}
