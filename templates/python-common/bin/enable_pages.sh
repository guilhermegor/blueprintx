#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

MKDOCS_YML="$SCRIPT_DIR/../mkdocs.yml"
PAGES_BRANCH="gh-pages"

require_gh() {
	if ! command -v gh >/dev/null 2>&1; then
		print_status "warning" "gh CLI not found — skipping Pages enablement (enable once in Settings → Pages)"
		return 1
	fi
	if ! gh auth status >/dev/null 2>&1; then
		print_status "warning" "gh not authenticated — skipping Pages enablement (run 'gh auth login', then 'poe enable_pages')"
		return 1
	fi
	return 0
}

repo_from_remote() {
	git remote get-url origin 2>/dev/null |
		sed -nE 's#^(git@github\.com:|ssh://git@github\.com/|https?://([^@/]+@)?github\.com/)([^/]+/[^/]+)/?$#\3#p' |
		sed -E 's#\.git$##' || true
}

report_gh_failure() {
	local str_err="$1" str_limit int_remaining int_reset str_when
	str_limit="$(gh api rate_limit --jq '.resources.graphql | "\(.remaining) \(.reset)"' 2>/dev/null || true)"
	int_remaining="${str_limit%% *}"
	int_reset="${str_limit##* }"
	if [ "$int_remaining" = "0" ]; then
		str_when="$(date -d "@$int_reset" 2>/dev/null || date -r "$int_reset" 2>/dev/null || echo "epoch $int_reset")"
		print_status "warning" "GitHub GraphQL rate limit exhausted — resets at $str_when; re-run 'poetry run poe enable_pages' after the reset${str_err:+ — gh said: $str_err}" >&2
		return 0
	fi
	print_status "warning" "gh repo view failed: ${str_err:-no output}" >&2
}

resolve_repo() {
	local str_slug
	str_slug="$(repo_from_remote)"
	if [ -n "$str_slug" ]; then
		echo "$str_slug"
		return 0
	fi
	local str_err
	str_slug="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)"
	if [ -n "$str_slug" ]; then
		echo "$str_slug"
		return 0
	fi
	str_err="$(gh repo view --json nameWithOwner 2>&1 >/dev/null || true)"
	if [ -z "$(git remote)" ]; then
		print_status "warning" "No GitHub remote resolved — push the repo to GitHub first" >&2
	else
		report_gh_failure "$str_err"
	fi
	return 1
}

uses_mike() {
	[ -f "$MKDOCS_YML" ] && grep -Eq '^[[:space:]]*provider:[[:space:]]*mike[[:space:]]*$' "$MKDOCS_YML"
}

remote_branch_exists() {
	local str_repo="$1" str_branch="$2"
	gh api "repos/$str_repo/branches/$str_branch" >/dev/null 2>&1
}

set_pages_source() {
	local str_repo="$1"
	local str_method="POST"
	gh api "repos/$str_repo/pages" >/dev/null 2>&1 && str_method="PUT"

	if uses_mike; then
		if ! remote_branch_exists "$str_repo" "$PAGES_BRANCH"; then
			print_status "info" "No '$PAGES_BRANCH' branch yet — leaving Pages untouched (the first 'mike deploy' in the release workflow creates it, then re-run 'poe enable_pages')"
			return 0
		fi
		print_status "info" "Setting GitHub Pages source to branch '$PAGES_BRANCH' for $str_repo (mike versioned docs)..."
		if printf '{"source":{"branch":"%s","path":"/"}}' "$PAGES_BRANCH" |
			gh api -X "$str_method" "repos/$str_repo/pages" --input - >/dev/null 2>&1; then
			print_status "success" "GitHub Pages now serves the versioned docs from '$PAGES_BRANCH'"
			return 0
		fi
	else
		print_status "info" "Enabling GitHub Pages (source = GitHub Actions) for $str_repo..."
		if gh api -X "$str_method" "repos/$str_repo/pages" -f build_type=workflow >/dev/null 2>&1; then
			print_status "success" "GitHub Pages enabled — the docs deploy workflow can now publish"
			return 0
		fi
	fi

	print_status "warning" "Could not set Pages source for $str_repo (needs repo-admin rights) — a maintainer must run 'poe enable_pages' or set it in Settings → Pages"
	return 0
}

enable_pages() {
	local str_repo
	if ! str_repo="$(resolve_repo)"; then
		return 0
	fi
	set_pages_source "$str_repo"
}

main() {
	print_status "section" "GitHub Pages Enablement"
	if ! require_gh; then
		return 0
	fi
	enable_pages
}

main "$@"
