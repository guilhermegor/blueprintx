#!/usr/bin/env bash
# npm pack -> install from the tarball -> require() the CJS build and
# import() the ESM build. Runs the package the way a real consumer would
# (through node_modules/, not straight from src/ or dist/), the only way to
# catch a broken "exports" map or a file missing from "files" before it
# reaches npm. ⚠️ Update the require/import checks below if you change the
# public API in src/index.ts — this smoke test is scaffolded against the
# example `greet` export.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$PROJECT_ROOT/bin/lib/common.sh"

TMP_DIR=""

cleanup() {
    [ -n "$TMP_DIR" ] && rm -rf "$TMP_DIR"
}

pack_tarball() {
    local tarball
    tarball="$(cd "$PROJECT_ROOT" && npm pack --silent)"
    echo "$tarball"
}

extract_tarball() {
    local tarball="$1"
    TMP_DIR="$(mktemp -d)"
    trap cleanup EXIT
    tar -xzf "$PROJECT_ROOT/$tarball" -C "$TMP_DIR"
    rm -f "$PROJECT_ROOT/$tarball"
}

smoke_require_cjs() {
    node -e "
      const pkg = require('$TMP_DIR/package');
      if (pkg.greet('World') !== 'Hello, World!') {
        throw new Error('CJS require() smoke failed: unexpected greet() output');
      }
    "
    print_status "success" "require() (CJS) smoke passed"
}

smoke_import_esm() {
    node --input-type=module -e "
      import { greet } from '$TMP_DIR/package/dist/esm/index.js';
      if (greet('World') !== 'Hello, World!') {
        throw new Error('ESM import smoke failed: unexpected greet() output');
      }
    "
    print_status "success" "import() (ESM) smoke passed"
}

main() {
    print_status "info" "Packing tarball with 'npm pack'..."
    local tarball
    tarball="$(pack_tarball)"
    print_status "config" "Tarball: $tarball"

    extract_tarball "$tarball"
    smoke_require_cjs
    smoke_import_esm

    print_status "success" "Package tarball smoke test passed"
}

main
