#!/usr/bin/env bash
# Asserts the version is identical in both sources of truth:
#   - pyproject.toml      (version = "X.Y.Z")
#   - bin/blueprintx.sh   (BLUEPRINTX_VERSION="X.Y.Z")
# Drift here means `blueprintx --version` lies. See bin/bump_version.sh.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYPROJECT="$REPO_ROOT/pyproject.toml"
BLUEPRINTX_SH="$REPO_ROOT/bin/blueprintx.sh"

py_version=$(grep -E '^version = ' "$PYPROJECT" | head -1 | sed -E 's/^version = "(.*)"/\1/')
cli_version=$(grep -E '^BLUEPRINTX_VERSION=' "$BLUEPRINTX_SH" | head -1 | sed -E 's/^BLUEPRINTX_VERSION="(.*)"/\1/')

if [ "$py_version" != "$cli_version" ]; then
	echo "Version mismatch between sources of truth:" >&2
	echo "  pyproject.toml     = ${py_version}" >&2
	echo "  bin/blueprintx.sh  = ${cli_version}" >&2
	echo "Run 'make bump_version' (it syncs both) or fix the drift manually." >&2
	exit 1
fi

echo "Version in sync: ${py_version}"
