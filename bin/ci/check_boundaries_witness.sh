#!/usr/bin/env bash
set -uo pipefail

project_dir="${1:?usage: $0 <scaffolded-project-dir>}"
cd "$project_dir" || exit 2

witness="src/capabilities/example/domain/boundaries-witness.ts"
if [[ -e "$witness" || -L "$witness" ]]; then
    echo "FAIL: witness path already exists: $witness" >&2
    exit 2
fi
trap 'rm -f "$witness"' EXIT
printf "import '../ui/pages/ExamplePage';\n" > "$witness"

output="$(npx --no-install eslint "$witness" 2>&1)"
status=$?
echo "$output"

if [[ $status -ne 1 ]]; then
    echo "FAIL: eslint exited $status, expected 1 (a lint error from the boundaries gate)" >&2
    exit 1
fi
if ! grep -q 'boundaries/dependencies' <<<"$output"; then
    echo "FAIL: eslint failed, but not under boundaries/dependencies" >&2
    exit 1
fi
echo "OK: cross-layer import rejected by boundaries/dependencies"
