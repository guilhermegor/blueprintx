#!/usr/bin/env bats

load helpers/common

fetch_one() {
    write_manifest "$1"
    run "$CLI" fetch
}

@test "dirsums picks the newest matching name and verifies it" {
    iso="payload-5"
    fixture "https://h/d/SHA256SUMS" "$(sha_of old) *u-24.04.3.iso
$(sha_of "$iso") *u-24.04.5.1.iso"
    fixture "https://h/d/u-24.04.5.1.iso" "$iso"
    fetch_one 'u|core|isos/Others|dirsums|https://h/d/|^u-24\.04(\.[0-9]+)*\.iso$|sums:SHA256SUMS|'
    [ "$status" -eq 0 ]
    [ -f "$BUILD_DIR/drive/isos/Others/u-24.04.5.1.iso" ]
    [ ! -e "$BUILD_DIR/drive/isos/Others/u-24.04.3.iso" ]
}

@test "dirsums reads the BSD checksum format" {
    iso="rocky"
    fixture "https://h/r/CHECKSUM" "# R-10.2-boot.iso: 5 bytes
SHA256 (R-10.2-boot.iso) = $(sha_of "$iso")"
    fixture "https://h/r/R-10.2-boot.iso" "$iso"
    fetch_one 'r|core|isos/Others|dirsums|https://h/r/|^R-10\.[0-9]+-boot\.iso$|sums:CHECKSUM|'
    [ "$status" -eq 0 ]
    [ -f "$BUILD_DIR/drive/isos/Others/R-10.2-boot.iso" ]
}

@test "a checksum mismatch fails and leaves no payload" {
    fixture "https://h/d/SHA256SUMS" "$(sha_of expected) *a.iso"
    fixture "https://h/d/a.iso" "tampered"
    fetch_one 'a|core|isos/Others|dirsums|https://h/d/|^a\.iso$|sums:SHA256SUMS|'
    [ "$status" -ne 0 ]
    [[ "$output" == *"checksum mismatch"* ]]
    [ -z "$(find "$BUILD_DIR/drive/isos/Others" -type f)" ]
}

@test "github uses the release asset digest" {
    iso="gh-payload"
    export GITHUB_API="https://api.test"
    fixture "https://api.test/repos/o/r/releases/latest" \
        "{\"assets\":[{\"name\":\"m.iso\",\"browser_download_url\":\"https://h/m.iso\",\"digest\":\"sha256:$(sha_of "$iso")\"}]}"
    fixture "https://h/m.iso" "$iso"
    fetch_one 'm|core|isos/Others|github|o/r|^m\.iso$|gh-digest|'
    [ "$status" -eq 0 ]
    [ -f "$BUILD_DIR/drive/isos/Others/m.iso" ]
}

@test "github without a digest fails closed" {
    export GITHUB_API="https://api.test"
    fixture "https://api.test/repos/o/r/releases/latest" \
        '{"assets":[{"name":"m.iso","browser_download_url":"https://h/m.iso"}]}'
    fixture "https://h/m.iso" "x"
    fetch_one 'm|core|isos/Others|github|o/r|^m\.iso$|gh-digest|'
    [ "$status" -ne 0 ]
    [[ "$output" == *"fail closed"* ]]
}

@test "pinned none:<reason> downloads unverified with a warning" {
    fixture "https://h/p.iso" "pp"
    fetch_one 'p|core|isos/Others|pinned|https://h/p.iso|-|none:vendor ships no checksum|'
    [ "$status" -eq 0 ]
    [[ "$output" == *"unverified"* ]]
}

@test "manual entries are skipped with a clear message" {
    fetch_one 'w|core|isos/Windows|manual|https://ms/|Win.iso|none:manual|'
    [ "$status" -eq 0 ]
    [[ "$output" == *"manual: w"* ]]
}
