#!/usr/bin/env bash

repo_from_remote() {
	git remote get-url origin 2>/dev/null |
		sed -nE 's#^(git@github\.com:|ssh://git@github\.com/|https?://([^@/]+@)?github\.com/)([^/]+/[^/]+)/?$#\3#p' |
		sed -E 's#\.git$##' || true
}

report_gh_failure() {
	local str_task="$1" str_err="$2" str_limit int_remaining int_reset str_when
	str_limit="$(gh api rate_limit --jq '.resources.graphql | "\(.remaining) \(.reset)"' 2>/dev/null || true)"
	int_remaining="${str_limit%% *}"
	int_reset="${str_limit##* }"
	if [ "$int_remaining" = "0" ]; then
		str_when="$(date -d "@$int_reset" 2>/dev/null || date -r "$int_reset" 2>/dev/null || echo "epoch $int_reset")"
		print_status "warning" "GitHub GraphQL rate limit exhausted — resets at $str_when; re-run 'poetry run poe $str_task' after the reset${str_err:+ — gh said: $str_err}" >&2
		return 0
	fi
	print_status "warning" "gh repo view failed: ${str_err:-no output}" >&2
}

resolve_repo() {
	local str_task="${1:-}" str_slug str_err
	str_slug="$(repo_from_remote)"
	if [ -n "$str_slug" ]; then
		echo "$str_slug"
		return 0
	fi
	str_slug="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)"
	if [ -n "$str_slug" ]; then
		echo "$str_slug"
		return 0
	fi
	str_err="$(gh repo view --json nameWithOwner 2>&1 >/dev/null || true)"
	if [ -z "$(git remote)" ]; then
		print_status "warning" "No GitHub remote resolved — push the repo to GitHub first" >&2
	else
		report_gh_failure "$str_task" "$str_err"
	fi
	return 1
}
