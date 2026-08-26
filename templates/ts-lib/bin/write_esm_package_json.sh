#!/usr/bin/env bash
# Marks dist/esm/*.js as ES modules. The root package.json stays
# "type": "commonjs" (so dist/cjs/*.js needs no marker of its own), so the
# ESM output needs its own nested package.json — Node's dual-package hazard
# workaround, without a bundler. Run by npm's "postbuild:esm" lifecycle hook.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

write_esm_marker() {
    local dist_esm="$PROJECT_ROOT/dist/esm"
    mkdir -p "$dist_esm"
    printf '{\n  "type": "module"\n}\n' > "$dist_esm/package.json"
}

main() {
    write_esm_marker
}

main
