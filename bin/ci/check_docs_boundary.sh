#!/usr/bin/env bash
# Fails when docs/ holds working material (backlog, lessons, specs, security policy) instead
# of published documentation. Usage: check_docs_boundary.sh [--root <dir>]. Design: docs/docs-boundary-gate.md

set -euo pipefail

# dotglob: include .superpowers-style entries; nullglob: empty dir yields no entries
shopt -s dotglob nullglob

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
case "$(basename "$SCRIPT_DIR")" in
ci) REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)" ;;
*) REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)" ;;
esac
if [ "${1:-}" = "--root" ]; then
	# A bad --root must fail: every later check would see "no docs/" and report success.
	[ -n "${2:-}" ] && [ -d "$2" ] || {
		echo "ERROR: --root needs an existing directory (got '${2:-}')" >&2
		exit 2
	}
	REPO_ROOT="$(cd "$2" && pwd)"
	shift 2
fi
[ "$#" -eq 0 ] || {
	echo "ERROR: unexpected argument '$1' (usage: check_docs_boundary.sh [--root <dir>])" >&2
	exit 2
}
DOCS_DIR="$REPO_ROOT/docs"
errors=0
checked=0

# No docs/ is not an error.
if [ ! -d "$DOCS_DIR" ]; then
	echo "check_docs_boundary: no docs/ directory — nothing to check."
	exit 0
fi

# Unreadable docs/ must fail, never pass as clean.
if [ ! -r "$DOCS_DIR" ]; then
	echo "ERROR: docs/ exists but is not readable" >&2
	exit 1
fi

is_denied() {
	# $1 = path relative to docs/, e.g. "backlog" or "guide/lessons-learned.md".
	# Prints the reason and returns 0 on a match; returns 1 (no output) otherwise.
	local rel="$1" base parts segment
	base="$(basename "$rel")"
	case "$rel" in
	backlog | backlog/*)
		echo "working material, not published docs — move it OUT of docs/: an in-repo" \
			"progress ledger belongs beside the work it tracks, and anything a reader" \
			"of the project needs belongs in README.md or CONTRIBUTING.md"
		return 0
		;;
	esac
	case "${base,,}" in
	*lesson*)
		echo "a lessons store, not published docs — keep lessons outside docs/; if a" \
			"lesson has become a rule this project follows, state the RULE in" \
			"CONTRIBUTING.md and drop the narrative"
		return 0
		;;
	design.md | plan.md)
		echo "a spec/plan artifact — belongs in .specs/features/<feature-name>/," \
			"not docs/"
		return 0
		;;
	security.md | threat*.md)
		echo "security policy is not a docs/ page — GitHub reads SECURITY.md from the" \
			"repository root, .github/ or docs/ root only, so a nested copy is invisible" \
			"to the advisory UI; move it to the root SECURITY.md"
		return 0
		;;
	esac
	IFS='/' read -ra parts <<<"$rel"
	for segment in "${parts[@]}"; do
		case "${segment,,}" in
		.superpowers*)
			echo "harness/tooling working material, not published docs — it belongs in" \
				"the tool's own home (.superpowers/ at the repo root), never under the" \
				"published site"
			return 0
			;;
		esac
	done
	return 1
}

# Judge what git would publish; see docs/docs-boundary-gate.md.
unset GIT_DIR GIT_WORK_TREE
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
bool_own_repo=0
if [ -z "$(git -C "$REPO_ROOT" rev-parse --show-prefix 2>/dev/null || echo x)" ]; then
	bool_own_repo=1
fi

is_git_ignored() {
	[ "$bool_own_repo" -eq 1 ] || return 1
	git -C "$REPO_ROOT" check-ignore -q -- "$1" 2>/dev/null
}

walk() {
	# $1 = absolute directory to walk.
	local dir="$1" entry rel reason
	for entry in "$dir"/*; do
		[ -e "$entry" ] || continue
		# An ignored entry is skipped whole, like a denied directory.
		if is_git_ignored "$entry"; then
			continue
		fi
		rel="${entry#"$DOCS_DIR"/}"
		checked=$((checked + 1))
		if reason="$(is_denied "$rel")"; then
			echo "ERROR: docs/$rel — $reason" >&2
			errors=$((errors + 1))
			continue # denied dir: already flagged as a whole, don't enumerate its contents
		fi
		# Symlinks are classified, then treated as leaves (no loops).
		if [ -L "$entry" ]; then
			continue
		fi
		if [ -d "$entry" ]; then
			# An unreadable directory must fail, never pass quietly.
			if [ ! -r "$entry" ] || [ ! -x "$entry" ]; then
				echo "ERROR: docs/$rel — directory is not readable/searchable, so its" \
					"contents cannot be checked; this is a broken check, not a clean one" >&2
				errors=$((errors + 1))
				continue
			fi
			walk "$entry"
		fi
	done
}

walk "$DOCS_DIR"

# An empty docs/ is a failed check, not a clean one.
if [ "$checked" -eq 0 ]; then
	echo "ERROR: docs/ exists but contains nothing to check" >&2
	exit 1
fi

if [ "$errors" -gt 0 ]; then
	echo "check_docs_boundary: $errors error(s) found." >&2
	exit 1
fi

echo "check_docs_boundary: docs/ boundary is clean ($checked entries checked)."
