#!/usr/bin/env bash
# Marks dist/esm/*.js as ES modules. The root package.json deliberately has NO
# "type" field (Node defaults an absent field to CommonJS, same as an explicit
# "type": "commonjs" — but the explicit form breaks Docusaurus 3.x's webpack
# build with an opaque "sourceType: module" parse error; verified by bisecting
# a vanilla Docusaurus site with only that one field flipped, see docs/ (#134)).
# So dist/cjs/*.js needs no marker of its own, but the ESM output still needs
# its own nested package.json — Node's dual-package hazard workaround, without
# a bundler. Run by npm's "postbuild:esm" lifecycle hook.
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
