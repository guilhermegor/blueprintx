#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="${PINS_REPO_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"

main() {
	local str_hits
	str_hits="$(
		find "$REPO_ROOT/.github/workflows" "$REPO_ROOT/templates" \
			-path '*/.github/workflows/*' -o -path "$REPO_ROOT/.github/workflows/*" |
			grep -E '\.ya?ml$' | sort -u |
			xargs -r grep -nE '^[[:space:]]*(-[[:space:]]*)?python-version:.*[0-9]+\.[0-9]+\.[0-9]+' || true
	)"
	if [ -n "$str_hits" ]; then
		echo "Patch-level python-version pin(s); pin the minor only (e.g. \"3.12\"):" >&2
		printf '%s\n' "$str_hits" | sed 's/^/    /' >&2
		exit 1
	fi
	echo "workflow python-version pins OK (minor-level only)."
}

main "$@"
