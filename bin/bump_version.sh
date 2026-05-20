#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(dirname "$0")"
PYPROJECT="$SCRIPT_DIR/../pyproject.toml"
BLUEPRINTX_SH="$SCRIPT_DIR/blueprintx.sh"

# ── Read each file's own current version independently ─────────────────────
# pyproject.toml is the canonical source for the bump menu. blueprintx.sh is
# read separately so a pre-existing drift between the two is corrected rather
# than silently skipped (see the per-file verification below).
read_version() {
	local file="$1" prefix="$2"
	grep -E "^${prefix}" "$file" | head -1 | sed -E "s/^${prefix}\"(.*)\"/\1/"
}

# Rewrites the version line in a file, then verifies the new value is actually
# present. A sed that matches nothing exits 0 — without this check a failed
# substitution would pass silently (the original bug that let the two files
# drift). Matches the existing value with a wildcard so drift self-heals.
write_version() {
	local file="$1" prefix="$2" new="$3"
	sed -i -E "s/^(${prefix})\"[^\"]*\"/\1\"${new}\"/" "$file"
	if ! grep -qF "${prefix}\"${new}\"" "$file"; then
		echo "Error: failed to set version in ${file}" >&2
		echo "  Expected a line matching: ${prefix}\"${new}\"" >&2
		exit 1
	fi
}

current=$(read_version "$PYPROJECT" 'version = ')
current_cli=$(read_version "$BLUEPRINTX_SH" 'BLUEPRINTX_VERSION=')
major=$(echo "$current" | cut -d. -f1)
minor=$(echo "$current" | cut -d. -f2)
patch=$(echo "$current" | cut -d. -f3)

echo "Current version: $current (pyproject.toml)"
if [ "$current_cli" != "$current" ]; then
	echo "Note: bin/blueprintx.sh is out of sync at ${current_cli} — it will be resynced."
fi
echo ""
echo "Select bump type:"
echo "  1) major  → $((major + 1)).0.0"
echo "  2) minor  → ${major}.$((minor + 1)).0"
echo "  3) patch  → ${major}.${minor}.$((patch + 1))"
echo "  4) custom"
echo ""
read -rp "Choice [1-4]: " choice

case "$choice" in
	1) new_version="$((major + 1)).0.0" ;;
	2) new_version="${major}.$((minor + 1)).0" ;;
	3) new_version="${major}.${minor}.$((patch + 1))" ;;
	4)
		read -rp "Enter version (e.g. 2.3.0): " new_version
		if ! echo "$new_version" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
			echo "Error: version must be in MAJOR.MINOR.PATCH format" >&2
			exit 1
		fi
		;;
	*)
		echo "Invalid choice" >&2
		exit 1
		;;
esac

write_version "$PYPROJECT" 'version = ' "$new_version"
write_version "$BLUEPRINTX_SH" 'BLUEPRINTX_VERSION=' "$new_version"

echo ""
echo "Bumped: $current → $new_version"
echo "Updated: pyproject.toml, bin/blueprintx.sh (both verified)"
echo ""
echo "Next: trigger the release workflow with version ${new_version}"
