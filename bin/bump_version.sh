#!/usr/bin/env bash
set -euo pipefail

PYPROJECT="$(dirname "$0")/../pyproject.toml"

# ── Read current version ───────────────────────────────────────────────────
current=$(grep -E '^version = ' "$PYPROJECT" | head -1 | sed 's/version = "\(.*\)"/\1/')
major=$(echo "$current" | cut -d. -f1)
minor=$(echo "$current" | cut -d. -f2)
patch=$(echo "$current" | cut -d. -f3)

echo "Current version: $current"
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

sed -i "s/^version = \"${current}\"/version = \"${new_version}\"/" "$PYPROJECT"

echo ""
echo "Bumped: $current → $new_version"
echo "Updated: pyproject.toml"
echo ""
echo "Next: trigger the release workflow with version ${new_version}"
