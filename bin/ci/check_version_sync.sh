#!/usr/bin/env bash
# BlueprintX's version is the git tag (see bin/blueprintx.sh print_version) — it is NOT hand-bumped.
# Both in-repo version literals must therefore stay at the "0.0.0" stub:
#   - pyproject.toml      (version = "0.0.0")          — only drives the docs site
#   - bin/blueprintx.sh   (BLUEPRINTX_VERSION="0.0.0") — fallback, stamped from the tag at
#                                                        install time (make install / packaging)
# A non-stub value here means someone hand-bumped out of old habit; the release tag is the source.

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
