ROOT="$BATS_TEST_DIRNAME/.."
CLI="$ROOT/bin/${PROJECT_NAME}"

setup() {
    TMP="$(mktemp -d)"
    export FIXTURES="$TMP/fixtures" BUILD_DIR="$TMP/build" SUDO=""
    export CURL="$BATS_TEST_DIRNAME/helpers/curl_stub.sh"
    export VENTOY_USB_CONF="$TMP/none.conf"
    mkdir -p "$FIXTURES"
}

teardown() {
    rm -rf "$TMP"
}

fixture() {
    printf '%s' "$2" >"$FIXTURES/$(printf '%s' "$1" | sed 's/[^A-Za-z0-9.-]/_/g')"
}

sha_of() {
    printf '%s' "$1" | sha256sum | cut -d' ' -f1
}

write_manifest() {
    export MANIFEST_FILE="$TMP/test.manifest"
    printf '%s\n' "$@" >"$MANIFEST_FILE"
}
