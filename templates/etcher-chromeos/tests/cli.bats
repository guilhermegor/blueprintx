#!/usr/bin/env bats

CLI="$BATS_TEST_DIRNAME/../bin/${PROJECT_NAME}"
LIB="$BATS_TEST_DIRNAME/../lib"

setup() {
    STUBS="$BATS_TEST_TMPDIR/stubs"
    FIX="$BATS_TEST_TMPDIR/fix"
    export STUB_LOG="$BATS_TEST_TMPDIR/dd.log"
    mkdir -p "$STUBS" "$FIX"
    : >"$STUB_LOG"
    printf 'fake-chromeos-image' >"$FIX/image.bin"
    python3 -I - "$FIX" <<'PY'
import hashlib, json, os, sys, zipfile

str_dir = sys.argv[1]
bytes_img = open(os.path.join(str_dir, "image.bin"), "rb").read()
with zipfile.ZipFile(os.path.join(str_dir, "image.zip"), "w") as zf:
    zf.writestr("flex.bin", bytes_img)
json.dump([{
    "channel": "STABLE", "version": "1.2.3", "file": "flex.bin",
    "url": "https://dl.example.test/flex.bin.zip", "filesize": len(bytes_img),
    "zipfilesize": os.path.getsize(os.path.join(str_dir, "image.zip")),
    "sha1": hashlib.sha1(bytes_img).hexdigest(),
}], open(os.path.join(str_dir, "manifest.json"), "w"))
PY
    cat >"$STUBS/lsblk" <<'STUB'
#!/usr/bin/env bash
case "$*" in
    *"-dno TYPE"*) echo "${STUB_TYPE:-disk}" ;;
    *"-no PKNAME"*) echo sdz ;;
    *"-dno RM"*) echo "${STUB_RM:-1}" ;;
    *"-nro MOUNTPOINT"*) echo "${STUB_MOUNT:-}" ;;
    *"-bdno SIZE"*) echo "${STUB_SIZE:-32000000000}" ;;
    *) echo "NAME MODEL SIZE" ;;
esac
STUB
    cat >"$STUBS/dd" <<'STUB'
#!/usr/bin/env bash
echo "dd $*" >>"$STUB_LOG"
STUB
    cat >"$STUBS/sync" <<'STUB'
#!/usr/bin/env bash
STUB
    cat >"$STUBS/curl" <<'STUB'
#!/usr/bin/env bash
while [ "$#" -gt 0 ]; do
    case "$1" in -o) str_out="$2" && shift ;; esac
    str_url="$1"
    shift
done
case "$str_url" in
    *.json) cp "$STUB_FIX/manifest.json" "$str_out" ;;
    *.zip) cp "$STUB_FIX/image.zip" "$str_out" ;;
    *) exit 22 ;;
esac
STUB
    chmod +x "$STUBS"/*
    export STUB_FIX="$FIX" CROS_SUDO="" PATH="$STUBS:$PATH"
    export CROS_FLEX_MANIFEST_URL="https://dl.example.test/recovery2.json"
    export CROS_DOWNLOAD_DIR="$BATS_TEST_TMPDIR/dl"
    DEV="$BATS_TEST_TMPDIR/fakedisk"
}

@test "--version prints the project name and a version" {
    run "$CLI" --version
    [ "$status" -eq 0 ]
    [[ "$output" == "${PROJECT_NAME} "* ]]
}

@test "--help prints usage" {
    run "$CLI" --help
    [ "$status" -eq 0 ]
    [[ "$output" == "Usage: ${PROJECT_NAME}"* ]]
}

@test "an unknown command fails with an error and usage" {
    run "$CLI" bogus-command
    [ "$status" -eq 1 ]
    [[ "$output" == *"Unknown command: bogus-command"* ]]
}

@test "manifest parsing picks the newest entry of the requested channel" {
    source "$LIB/common.sh"
    source "$LIB/flex.sh"
    run flex_pick_entry "$BATS_TEST_DIRNAME/fixtures/recovery.json" STABLE
    [ "$status" -eq 0 ]
    [[ "$output" == "16805.33.0"$'\t'"https://dl.example.test/new.bin.zip"* ]]
    [[ "$output" == *"b7215251a8bfca5a9098402e076b7e5288a7b461" ]]
}

@test "manifest parsing fails on a channel the manifest lacks" {
    source "$LIB/common.sh"
    source "$LIB/flex.sh"
    run flex_pick_entry "$BATS_TEST_DIRNAME/fixtures/recovery.json" CANARY
    [ "$status" -ne 0 ]
}

@test "flash asks for the pendrive path first" {
    run bash -c "printf '%s\n' '$DEV' | '$CLI' flash --os chromeos-flex --dry-run"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Target: $DEV (removable)"* ]]
}

@test "dry-run resolves the image and writes nothing" {
    run "$CLI" flash --target "$DEV" --os chromeos-flex --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"[dry-run] would write: dd if="* ]]
    [ ! -s "$STUB_LOG" ]
    [ ! -e "$CROS_DOWNLOAD_DIR/flex.bin" ]
}

@test "a confirmed flash downloads, verifies and writes with dd" {
    run "$CLI" flash --target "$DEV" --os chromeos-flex --tool dd --confirm fakedisk
    [ "$status" -eq 0 ]
    grep -q "of=$DEV bs=4M conv=fsync status=progress" "$STUB_LOG"
}

@test "a checksum mismatch aborts before anything is written" {
    sed -i 's/"sha1": "[0-9a-f]*"/"sha1": "0000000000000000000000000000000000000000"/' "$FIX/manifest.json"
    run "$CLI" flash --target "$DEV" --os chromeos-flex --confirm fakedisk
    [ "$status" -ne 0 ]
    [[ "$output" == *"sha1 mismatch"* ]]
    [ ! -s "$STUB_LOG" ]
    [ ! -e "$CROS_DOWNLOAD_DIR/flex.bin" ]
}

@test "a non-removable device is refused" {
    STUB_RM=0 run "$CLI" flash --target "$DEV" --os chromeos-flex --confirm fakedisk
    [ "$status" -ne 0 ]
    [[ "$output" == *"not a removable device"* ]]
    [ ! -s "$STUB_LOG" ]
}

@test "a device with mounted partitions is refused" {
    STUB_MOUNT=/media/usb run "$CLI" flash --target "$DEV" --os chromeos-flex --confirm fakedisk
    [ "$status" -ne 0 ]
    [[ "$output" == *"mounted partitions"* ]]
}

@test "an unconfirmed device is not written" {
    run "$CLI" flash --target "$DEV" --os chromeos-flex --confirm wrongname
    [ "$status" -ne 0 ]
    [[ "$output" == *"Not confirmed"* ]]
    [ ! -s "$STUB_LOG" ]
}

@test "no confirmation on stdin is not a confirmation" {
    run "$CLI" flash --target "$DEV" --os chromeos-flex </dev/null
    [ "$status" -ne 0 ]
    [[ "$output" == *"Not confirmed"* ]]
    [ ! -s "$STUB_LOG" ]
}

@test "an image larger than the device is refused" {
    STUB_SIZE=5 run "$CLI" flash --target "$DEV" --os chromeos-flex --confirm fakedisk
    [ "$status" -ne 0 ]
    [[ "$output" == *"larger than"* ]]
    [ ! -s "$STUB_LOG" ]
}

@test "fydeos refuses an image whose SHA-256 does not match" {
    cp "$FIX/image.bin" "$FIX/fyde.img"
    run "$CLI" flash --target "$DEV" --os fydeos --file "$FIX/fyde.img" --sha256 deadbeef --dry-run
    [ "$status" -ne 0 ]
    [[ "$output" == *"sha256 mismatch"* ]]
}

@test "fydeos accepts an image whose SHA-256 matches" {
    cp "$FIX/image.bin" "$FIX/fyde.img"
    str_hash="$(sha256sum "$FIX/fyde.img" | cut -d' ' -f1)"
    run "$CLI" flash --target "$DEV" --os fydeos --file "$FIX/fyde.img" --sha256 "$str_hash" --confirm fakedisk
    [ "$status" -eq 0 ]
    grep -q "if=$FIX/fyde.img of=$DEV" "$STUB_LOG"
}
