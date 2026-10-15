#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYPROJECT="$REPO_ROOT/pyproject.toml"
BLUEPRINTX_SH="$REPO_ROOT/bin/blueprintx.sh"
STUB="0.0.0"

py_version=$(grep -E '^version = ' "$PYPROJECT" | head -1 | sed -E 's/^version = "(.*)"/\1/')
cli_version=$(grep -E '^BLUEPRINTX_VERSION=' "$BLUEPRINTX_SH" | head -1 | sed -E 's/^BLUEPRINTX_VERSION="(.*)"/\1/')

if [ "$py_version" != "$STUB" ] || [ "$cli_version" != "$STUB" ]; then
	echo "In-repo version literals must stay at the \"${STUB}\" stub (the real version is the git tag):" >&2
	echo "  pyproject.toml     = ${py_version}" >&2
	echo "  bin/blueprintx.sh  = ${cli_version}" >&2
	echo "Do not hand-bump — cut a release via the Release action (or push a vX.Y.Z tag)." >&2
	exit 1
fi

echo "Version literals at the ${STUB} stub; real version comes from the git tag."
