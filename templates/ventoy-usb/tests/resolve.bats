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
    fetch_one 'u|core|isos/Others|dirsums|https://h/d/|^u-24\.04(\.[0-9]+)*\.iso$|sums:SHA256SUMS|||same-origin-digest'
    [ "$status" -eq 0 ]
    [ -f "$BUILD_DIR/drive/isos/Others/u-24.04.5.1.iso" ]
    [ ! -e "$BUILD_DIR/drive/isos/Others/u-24.04.3.iso" ]
}

@test "dirsums reads the BSD checksum format" {
    iso="rocky"
    fixture "https://h/r/CHECKSUM" "# R-10.2-boot.iso: 5 bytes
SHA256 (R-10.2-boot.iso) = $(sha_of "$iso")"
    fixture "https://h/r/R-10.2-boot.iso" "$iso"
    fetch_one 'r|core|isos/Others|dirsums|https://h/r/|^R-10\.[0-9]+-boot\.iso$|sums:CHECKSUM|||same-origin-digest'
    [ "$status" -eq 0 ]
    [ -f "$BUILD_DIR/drive/isos/Others/R-10.2-boot.iso" ]
}

@test "a checksum mismatch fails and leaves no payload" {
    fixture "https://h/d/SHA256SUMS" "$(sha_of expected) *a.iso"
    fixture "https://h/d/a.iso" "tampered"
    fetch_one 'a|core|isos/Others|dirsums|https://h/d/|^a\.iso$|sums:SHA256SUMS|||same-origin-digest'
    [ "$status" -ne 0 ]
    [[ "$output" == *"checksum mismatch"* ]]
    [ -z "$(find "$BUILD_DIR/drive/isos/Others" -type f)" ]
}

@test "github uses the release asset digest" {
    iso="gh-payload"
    export GITHUB_API="https://api.test"
    fixture "https://api.test/repos/o/r/releases/latest" \
        "{\"assets\":[{\"name\":\"m.iso\",\"browser_download_url\":\"https://github.com/o/r/m.iso\",\"digest\":\"sha256:$(sha_of "$iso")\"}]}"
    fixture "https://github.com/o/r/m.iso" "$iso"
    fetch_one 'm|core|isos/Others|github|o/r|^m\.iso$|gh-digest|||same-origin-digest'
    [ "$status" -eq 0 ]
    [ -f "$BUILD_DIR/drive/isos/Others/m.iso" ]
}

@test "github without a digest fails closed" {
    export GITHUB_API="https://api.test"
    fixture "https://api.test/repos/o/r/releases/latest" \
        '{"assets":[{"name":"m.iso","browser_download_url":"https://github.com/o/r/m.iso"}]}'
    fixture "https://github.com/o/r/m.iso" "x"
    fetch_one 'm|core|isos/Others|github|o/r|^m\.iso$|gh-digest|||same-origin-digest'
    [ "$status" -ne 0 ]
    [[ "$output" == *"fail closed"* ]]
}

@test "latesturl none:<reason> downloads unverified with a warning" {
    fixture "https://h/p.iso" "pp"
    fetch_one 'p|core|isos/Others|latesturl|https://h/p.iso|^p\.iso$|none:vendor ships no checksum|||none'
    [ "$status" -eq 0 ]
    [[ "$output" == *"unverified"* ]]
    [ -f "$BUILD_DIR/drive/isos/Others/p.iso" ]
}

@test "latesturl re-downloads when the remote size changes" {
    fixture "https://h/p.iso" "pp"
    fetch_one 'p|core|isos/Others|latesturl|https://h/p.iso|^p\.iso$|none:no checksum|||none'
    fixture "https://h/p.iso" "ppppp"
    fetch_one 'p|core|isos/Others|latesturl|https://h/p.iso|^p\.iso$|none:no checksum|||none'
    [ "$(cat "$BUILD_DIR/drive/isos/Others/p.iso")" = "ppppp" ]
}

@test "a newer version replaces the older one of the same entry without a prompt" {
    iso="payload-6"
    mkdir -p "$BUILD_DIR/drive/isos/Others"
    : >"$BUILD_DIR/drive/isos/Others/u-24.04.3.iso"
    : >"$BUILD_DIR/drive/isos/Others/unrelated.iso"
    fixture "https://h/d/SHA256SUMS" "$(sha_of "$iso") *u-24.04.5.iso"
    fixture "https://h/d/u-24.04.5.iso" "$iso"
    fetch_one 'u|core|isos/Others|dirsums|https://h/d/|^u-24\.04(\.[0-9]+)*\.iso$|sums:SHA256SUMS|||same-origin-digest'
    [ "$status" -eq 0 ]
    [ ! -e "$BUILD_DIR/drive/isos/Others/u-24.04.3.iso" ]
    [ -e "$BUILD_DIR/drive/isos/Others/unrelated.iso" ]
}

@test "sfrss picks the newest file and verifies the feed md5" {
    iso="sf-payload"
    md5="$(printf '%s' "$iso" | md5sum | cut -d' ' -f1)"
    fixture "https://sourceforge.net/projects/p/rss?path=/64-bit&limit=100" "<item>
<title><![CDATA[/64-bit/P-2.1.2-64-bit-1-BETA.iso]]></title>
<media:hash algo=\"md5\">0000</media:hash>
</item>
<item>
<title><![CDATA[/64-bit/P-2.1.3-64-bit-2-BETA.iso]]></title>
<media:hash algo=\"md5\">$md5</media:hash>
</item>"
    fixture "https://downloads.sourceforge.net/project/p/64-bit/P-2.1.3-64-bit-2-BETA.iso" "$iso"
    fetch_one 'p|android|isos/Android|sfrss|p/64-bit|^P-[0-9.]+-64-bit-[0-9]+-BETA\.iso$|rss-hash|||same-origin-digest'
    [ "$status" -eq 0 ]
    [ -f "$BUILD_DIR/drive/isos/Android/P-2.1.3-64-bit-2-BETA.iso" ]
}

@test "dirindex picks the newest href by file name and reads the sidecar" {
    iso="tn"
    fixture "https://h/" '<a href="T-A/1.0/T-1.0.iso">x</a><a href="T-B/2.0/T-2.0.iso">y</a><a href="T-B/3.0-BETA/T-3.0-BETA.iso">z</a>'
    fixture "https://h/T-B/2.0/T-2.0.iso.sha256" "$(sha_of "$iso")"
    fixture "https://h/T-B/2.0/T-2.0.iso" "$iso"
    fetch_one 'tn|core|isos/Others|dirindex|https://h/|^T-[A-Z]/[0-9.]+/T-[0-9.]+\.iso$|sidecar:.sha256|||same-origin-digest'
    [ "$status" -eq 0 ]
    [ -f "$BUILD_DIR/drive/isos/Others/T-2.0.iso" ]
}

@test "archive verifies against the sha1 in the item metadata" {
    iso="tiny"
    sha1="$(printf '%s' "$iso" | sha1sum | cut -d' ' -f1)"
    fixture "https://archive.org/metadata/it" "{\"files\":[{\"name\":\"a.iso\",\"mtime\":\"5\",\"sha1\":\"$sha1\"}]}"
    fixture "https://archive.org/download/it/a.iso" "$iso"
    fetch_one 'it|windows|isos/Windows|archive|it|^a\.iso$|archive-hash|||same-origin-digest'
    [ "$status" -eq 0 ]
    [ -f "$BUILD_DIR/drive/isos/Windows/a.iso" ]
}

@test "a Microsoft refusal fails that entry only and the rest still download" {
    fixture "https://www.microsoft.com/en-us/software-download/windows11" '<option value="3813">x</option>'
    fixture "https://vlscppe.microsoft.com/tags" "ok"
    write_manifest 'w|windows|isos/Windows|windows|Brazilian Portuguese|\.iso$|none:no hash page|||none' \
        'p|core|isos/Others|latesturl|https://h/p.iso|^p\.iso$|none:no checksum|||none'
    fixture "https://h/p.iso" "pp"
    run "$CLI" fetch
    [ "$status" -ne 0 ]
    [[ "$output" == *"w: could not resolve"* ]]
    [ -f "$BUILD_DIR/drive/isos/Others/p.iso" ]
}

@test "manual entries are skipped with a clear message" {
    fetch_one 'w|core|isos/Windows|manual|https://ms/|^Win\.iso$|none:manual|||none'
    [ "$status" -eq 0 ]
    [[ "$output" == *"manual: w"* ]]
    [[ "$output" == *"payload/isos/Windows"* ]]
}

make_signed_sums() {
    export GNUPGHOME="$TMP/gh"
    mkdir -m700 "$GNUPGHOME"
    gpg --batch -q --passphrase '' --quick-gen-key "test <t@example.com>" ed25519 sign 0 2>/dev/null
    FPR="$(gpg --with-colons --list-keys | awk -F: '$1 == "fpr" { print $10; exit }')"
    printf '%s' "$1" >"$TMP/sums"
    gpg --batch -q --yes --detach-sign -o "$TMP/sums.gpg" "$TMP/sums"
    gpg --batch -q --armor --export "$FPR" >"$TMP/key.asc"
    unset GNUPGHOME
    fixture "https://h/d/SHA256SUMS" "$1"
    fixture_file "https://h/d/SHA256SUMS.gpg" "$TMP/sums.gpg"
    fixture_file "https://h/key.asc" "$TMP/key.asc"
}

@test "gpg trust: a checksum file signed by the pinned key is accepted" {
    command -v gpg || skip "gpg missing"
    iso="signed"
    make_signed_sums "$(sha_of "$iso") *s.iso
"
    fixture "https://h/d/s.iso" "$iso"
    fetch_one "s|core|isos/Others|dirsums|https://h/d/|^s\\.iso\$|sums:SHA256SUMS|||gpg:$FPR:.gpg:https://h/key.asc"
    [ "$status" -eq 0 ]
    [[ "$output" == *"trust: gpg"* ]]
    [ -f "$BUILD_DIR/drive/isos/Others/s.iso" ]
}

@test "gpg trust: a tampered checksum file fails that entry" {
    command -v gpg || skip "gpg missing"
    iso="signed"
    make_signed_sums "$(sha_of "$iso") *s.iso
"
    fixture "https://h/d/SHA256SUMS" "$(sha_of evil) *s.iso
"
    fixture "https://h/d/s.iso" "evil"
    fetch_one "s|core|isos/Others|dirsums|https://h/d/|^s\\.iso\$|sums:SHA256SUMS|||gpg:$FPR:.gpg:https://h/key.asc"
    [ "$status" -ne 0 ]
    [[ "$output" == *"fail closed"* ]]
    [ ! -e "$BUILD_DIR/drive/isos/Others/s.iso" ]
}

@test "gpg trust: a key with another fingerprint is refused" {
    command -v gpg || skip "gpg missing"
    make_signed_sums "$(sha_of x) *s.iso
"
    fixture "https://h/d/s.iso" "x"
    fetch_one "s|core|isos/Others|dirsums|https://h/d/|^s\\.iso\$|sums:SHA256SUMS|||gpg:0000000000000000000000000000000000000000:.gpg:https://h/key.asc"
    [ "$status" -ne 0 ]
}

@test "trust level must match the checksum kind" {
    write_manifest 'm|core|isos/Others|github|o/r|^m\.iso$|gh-digest|||none'
    run "$CLI" layout
    [ "$status" -ne 0 ]
    [[ "$output" == *"trust level"* ]]
}

@test "two-origin: GitHub digest and ventoy.net must agree" {
    iso="vt"
    export GITHUB_API="https://api.test"
    fixture "https://api.test/repos/o/r/releases/latest" \
        "{\"assets\":[{\"name\":\"ventoy-1.0-linux.tar.gz\",\"browser_download_url\":\"https://github.com/o/r/x.tgz\",\"digest\":\"sha256:$(sha_of "$iso")\"}]}"
    fixture "https://github.com/o/r/x.tgz" "$iso"
    fixture "https://www.ventoy.net/en/download.html" "{\"linsha\":\"$(sha_of "$iso")\"}"
    fetch_one 'v|tool|@tools|github|o/r|^ventoy-[0-9.]+-linux\.tar\.gz$|gh-digest|||two-origin'
    [ "$status" -eq 0 ]
    rm -rf "$BUILD_DIR" "$TOOLS_DIR"
    fixture "https://www.ventoy.net/en/download.html" "{\"linsha\":\"$(sha_of other)\"}"
    fetch_one 'v|tool|@tools|github|o/r|^ventoy-[0-9.]+-linux\.tar\.gz$|gh-digest|||two-origin'
    [ "$status" -ne 0 ]
    [[ "$output" == *"disagree"* ]]
}

@test "two-origin: an unreachable second origin only warns" {
    iso="vt"
    export GITHUB_API="https://api.test"
    fixture "https://api.test/repos/o/r/releases/latest" \
        "{\"assets\":[{\"name\":\"ventoy-1.0-linux.tar.gz\",\"browser_download_url\":\"https://github.com/o/r/x.tgz\",\"digest\":\"sha256:$(sha_of "$iso")\"}]}"
    fixture "https://github.com/o/r/x.tgz" "$iso"
    fetch_one 'v|tool|@tools|github|o/r|^ventoy-[0-9.]+-linux\.tar\.gz$|gh-digest|||two-origin'
    [ "$status" -eq 0 ]
    [[ "$output" == *"one origin only"* ]]
}

@test "a hostile asset name is refused before any path is built" {
    export GITHUB_API="https://api.test"
    fixture "https://api.test/repos/o/r/releases/latest" \
        '{"assets":[{"name":"../evil.iso","browser_download_url":"https://github.com/o/r/e","digest":"sha256:00"}]}'
    fetch_one 'm|core|isos/Others|github|o/r|evil\.iso$|gh-digest|||same-origin-digest'
    [ "$status" -ne 0 ]
    [[ "$output" == *"unexpected file name"* ]]
}

@test "a truncated cached payload is downloaded again" {
    iso="payload-9"
    fixture "https://h/d/SHA256SUMS" "$(sha_of "$iso") *u-24.04.5.iso"
    fixture "https://h/d/u-24.04.5.iso" "$iso"
    fetch_one 'u|core|isos/Others|dirsums|https://h/d/|^u-24\.04(\.[0-9]+)*\.iso$|sums:SHA256SUMS|||same-origin-digest'
    : >"$BUILD_DIR/drive/isos/Others/u-24.04.5.iso"
    fetch_one 'u|core|isos/Others|dirsums|https://h/d/|^u-24\.04(\.[0-9]+)*\.iso$|sums:SHA256SUMS|||same-origin-digest'
    [ "$(cat "$BUILD_DIR/drive/isos/Others/u-24.04.5.iso")" = "$iso" ]
}
