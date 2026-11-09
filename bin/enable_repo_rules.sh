#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

RULESET_NAME="pr-quality-gate"

REQUIRED_CHECKS_FILE="$SCRIPT_DIR/required-checks.txt"
REQUIRED_CHECKS=()
REQUIRED_CHECKS_FILE_MISSING=0

load_required_checks() {
	[ -f "$REQUIRED_CHECKS_FILE" ] || return 0
	local str_line
	while IFS= read -r str_line || [ -n "$str_line" ]; do
		case "$str_line" in '' | '#'*) continue ;; esac
		REQUIRED_CHECKS+=("$str_line")
	done <"$REQUIRED_CHECKS_FILE"
}

[ -f "$REQUIRED_CHECKS_FILE" ] || REQUIRED_CHECKS_FILE_MISSING=1
load_required_checks

require_gh() {
	if ! command -v gh >/dev/null 2>&1; then
		print_status "warning" "gh CLI not found — skipping ruleset provisioning (run 'poe enable_repo_rules' later)"
		return 1
	fi
	if ! gh auth status >/dev/null 2>&1; then
		print_status "warning" "gh not authenticated — skipping ruleset provisioning (run 'gh auth login', then 'poe enable_repo_rules')"
		return 1
	fi
	return 0
}

resolve_repo() {
	gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true
}

build_rules_json() {
	local str_checks_rule=""
	if [ ${#REQUIRED_CHECKS[@]} -gt 0 ]; then
		local str_contexts=""
		local str_check
		for str_check in "${REQUIRED_CHECKS[@]}"; do
			str_contexts+="$(printf '{"context":"%s"},' "$str_check")"
		done
		str_contexts="${str_contexts%,}"
		str_checks_rule=$(printf ',{"type":"required_status_checks","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[%s]}}' "$str_contexts")
	fi

	cat <<EOF
[
  {"type":"pull_request","parameters":{
    "required_approving_review_count":${RULESET_APPROVALS:-0},
    "dismiss_stale_reviews_on_push":false,
    "require_code_owner_review":false,
    "require_last_push_approval":false,
    "required_review_thread_resolution":true
  }},
  {"type":"code_scanning","parameters":{"code_scanning_tools":[
    {"tool":"CodeQL","security_alerts_threshold":"high_or_higher","alerts_threshold":"errors"}
  ]}},
  {"type":"copilot_code_review","parameters":{
    "review_on_push":true,
    "review_draft_pull_requests":false
  }},
  {"type":"non_fast_forward"},
  {"type":"required_linear_history"},
  {"type":"deletion"}${str_checks_rule}
]
EOF
}

build_ruleset_json() {
	local str_rules
	str_rules="$(build_rules_json)"
	cat <<EOF
{
  "name": "$RULESET_NAME",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "rules": $str_rules
}
EOF
}

apply_ruleset() {
	local str_repo="$1"
	local str_id
	str_id=$(gh api "repos/$str_repo/rulesets" --jq \
		".[] | select(.name == \"$RULESET_NAME\") | .id" 2>/dev/null | head -1 || true)

	if [ -n "$str_id" ] && [ "$REQUIRED_CHECKS_FILE_MISSING" = "1" ]; then
		print_status "warning" "$REQUIRED_CHECKS_FILE is missing and ruleset '$RULESET_NAME' (id $str_id) already exists — skipping the update so its required_status_checks rule is never silently dropped. Restore the file, then re-run 'poe enable_repo_rules'."
		return 0
	fi

	local str_err
	if [ -n "$str_id" ]; then
		print_status "info" "Updating existing ruleset '$RULESET_NAME' (id $str_id)..."
		if str_err="$(build_ruleset_json | gh api -X PUT "repos/$str_repo/rulesets/$str_id" --input - 2>&1 >/dev/null)"; then
			print_status "success" "Ruleset '$RULESET_NAME' updated"
			return 0
		fi
	else
		print_status "info" "Creating ruleset '$RULESET_NAME' on ~DEFAULT_BRANCH..."
		if str_err="$(build_ruleset_json | gh api -X POST "repos/$str_repo/rulesets" --input - 2>&1 >/dev/null)"; then
			print_status "success" "Ruleset '$RULESET_NAME' created"
			return 0
		fi
	fi

	print_status "warning" "Could not apply ruleset to $str_repo: ${str_err:-no output from gh} — a maintainer with repo-admin rights must run 'poe enable_repo_rules'"
	return 0
}

report_blocking_checks() {
	local str_repo="$1"
	local str_id str_live str_strict
	if ! str_id="$(gh api "repos/$str_repo/rulesets" --jq \
		".[] | select(.name == \"$RULESET_NAME\") | .id" 2>&1)"; then
		print_status "warning" "Could not READ rulesets from $str_repo (so the blocking set is UNKNOWN, not empty): ${str_id:-no output from gh}"
		return 2
	fi
	str_id="$(printf '%s\n' "$str_id" | head -1)"
	if [ -z "$str_id" ]; then
		print_status "warning" "Ruleset '$RULESET_NAME' is NOT present on $str_repo — nothing blocks a merge"
		return 2
	fi
	if ! str_live="$(gh api "repos/$str_repo/rulesets/$str_id" --jq \
		'[.rules[]? | select(.type == "required_status_checks")
		  | .parameters.required_status_checks[]?.context] | join(", ")' 2>&1)"; then
		print_status "warning" "Could not READ ruleset '$RULESET_NAME' from $str_repo (so the blocking set is UNKNOWN, not empty): ${str_live:-no output from gh}"
		return 2
	fi
	if [ -z "$str_live" ]; then
		print_status "warning" "Ruleset '$RULESET_NAME' is active but declares NO required status checks — CI runs and blocks NOTHING. Populate REQUIRED_CHECKS in bin/enable_repo_rules.sh from a real PR's check-run names, then re-run."
		return 2
	fi
	print_status "config" "Merge-blocking checks live on $str_repo: $str_live"

	if ! str_strict="$(gh api "repos/$str_repo/rulesets/$str_id" --jq \
		'[.rules[]? | select(.type == "required_status_checks")
		  | .parameters.strict_required_status_checks_policy] | first' 2>&1)"; then
		print_status "warning" "Could not READ the strict policy on $str_repo (so it is UNKNOWN, not enforced): ${str_strict:-no output from gh}"
		return 2
	fi
	if [ "$str_strict" = "null" ] || [ -z "$str_strict" ]; then
		print_status "warning" "strict_required_status_checks_policy is absent on $str_repo (ruleset '$RULESET_NAME') — UNKNOWN, not enforced"
		return 2
	fi
	if [ "$str_strict" != "true" ]; then
		print_status "error" "strict_required_status_checks_policy is NOT true on $str_repo (ruleset '$RULESET_NAME') — a PR can merge on a green run that never saw its base (blueprintx#307)"
		return 1
	fi
	print_status "success" "strict_required_status_checks_policy is enforced on $str_repo (ruleset '$RULESET_NAME', verified)"
}

assert_branch_protection_strict() {
	local str_repo="$1" str_branch="$2"
	local str_strict
	if ! str_strict="$(gh api "repos/$str_repo/branches/$str_branch/protection" --jq \
		'.required_status_checks.strict' 2>&1)"; then
		print_status "warning" "Could not READ classic branch protection on $str_repo:$str_branch (so strict is UNKNOWN, not enforced): ${str_strict:-no output from gh}"
		return 2
	fi
	if [ "$str_strict" = "null" ] || [ -z "$str_strict" ]; then
		print_status "warning" "$str_repo:$str_branch has no required_status_checks under classic branch protection — nothing to assert strict on"
		return 2
	fi
	if [ "$str_strict" != "true" ]; then
		print_status "error" "required_status_checks.strict is NOT true on $str_repo:$str_branch (classic branch protection) — a PR can merge on a green run that never saw its base (blueprintx#307)"
		return 1
	fi
	print_status "success" "required_status_checks.strict is enforced on $str_repo:$str_branch (classic branch protection, verified)"
}

verify_strict_required_checks() {
	if ! require_gh; then
		return 1
	fi
	local str_repo str_branch
	str_repo="$(resolve_repo)"
	if [ -z "$str_repo" ]; then
		print_status "error" "No GitHub remote resolved — cannot verify branch protection"
		return 1
	fi
	if ! str_branch="$(gh api "repos/$str_repo" --jq .default_branch 2>&1)"; then
		print_status "error" "Could not resolve the default branch for $str_repo (so it is UNKNOWN, not 'main'): ${str_branch:-no output from gh}"
		return 1
	fi

	local int_ruleset_result int_protection_result
	report_blocking_checks "$str_repo" && int_ruleset_result=0 || int_ruleset_result=$?
	assert_branch_protection_strict "$str_repo" "$str_branch" && int_protection_result=0 || int_protection_result=$?

	if [ "$int_ruleset_result" -eq 1 ] || [ "$int_protection_result" -eq 1 ]; then
		return 1
	fi
	if [ "$int_ruleset_result" -ne 0 ] && [ "$int_protection_result" -ne 0 ]; then
		print_status "error" "Neither mechanism confirmed strict enforcement on $str_repo (both absent or unreadable) — absence is not proof (blueprintx#307)"
		return 1
	fi
	return 0
}

enable_code_scanning() {
	local str_repo="$1"
	if gh api -X PATCH "repos/$str_repo/code-scanning/default-setup" -f state=configured >/dev/null 2>&1; then
		print_status "success" "CodeQL default setup configured"
	else
		print_status "warning" "Could not configure CodeQL default setup (needs repo-admin, or the language is unsupported) — enable it in Settings → Code security"
	fi
}

enable_merge_settings() {
	local str_repo="$1"
	if gh api -X PATCH "repos/$str_repo" -F allow_auto_merge=true -F delete_branch_on_merge=true >/dev/null 2>&1; then
		local str_state
		str_state=$(gh api "repos/$str_repo" --jq .allow_auto_merge 2>/dev/null || echo "unknown")
		if [ "$str_state" = "true" ]; then
			print_status "success" "allow_auto_merge + delete_branch_on_merge enabled (verified)"
		else
			print_status "warning" "allow_auto_merge reads back as '$str_state' — auto-merge will silently no-op until it is true"
		fi
	else
		print_status "warning" "Could not set merge settings on $str_repo (needs repo-admin rights)"
	fi
}

ensure_optout_label() {
	local str_repo="$1"
	gh label create "do-not-merge" --repo "$str_repo" --color "b60205" \
		--description "Block this PR from auto-merging (PR gate opt-out)" --force >/dev/null 2>&1 &&
		print_status "success" "Label 'do-not-merge' present (auto-merge opt-out)" ||
		print_status "warning" "Could not create the 'do-not-merge' label on $str_repo"
}

check_ruleset_present() {
	require_gh || return 0
	local str_repo str_ids
	str_repo="${GITHUB_REPOSITORY:-$(resolve_repo)}"
	if [ -z "$str_repo" ]; then
		print_status "warning" "Could not resolve the repository (ruleset presence UNKNOWN, not confirmed)"
		return 0
	fi
	if ! str_ids="$(gh api "repos/$str_repo/rulesets" --jq \
		".[] | select(.name == \"$RULESET_NAME\") | .id" 2>&1)"; then
		print_status "warning" "Could not READ rulesets from $str_repo (presence UNKNOWN): ${str_ids:-no output from gh}"
		return 0
	fi
	[ -n "$str_ids" ] && return 0
	[ "${GITHUB_ACTIONS:-}" = "true" ] && echo "::warning title=Ruleset missing::'$RULESET_NAME' is not enabled on $str_repo, so merges are unprotected. A maintainer with admin rights must run 'poe enable_repo_rules'."
	print_status "error" "Ruleset '$RULESET_NAME' is NOT present on $str_repo — run 'poe enable_repo_rules' (needs repo-admin)"
	return 1
}

pr_has_codeql_analysis() {
	local str_repo="$1" int_pr="$2" str_sha="$3"
	local str_merge str_ref str_shas
	str_merge="$(gh api "repos/$str_repo/git/ref/pull/$int_pr/merge" --jq .object.sha 2>/dev/null || true)"
	for str_ref in head merge; do
		str_shas="$(gh api "repos/$str_repo/code-scanning/analyses?tool_name=CodeQL&ref=refs/pull/$int_pr/$str_ref" \
			--jq '.[].commit_sha' 2>/dev/null)" || return 2
		grep -qxF -e "$str_sha" -e "${str_merge:-$str_sha}" <<<"$str_shas" && return 0
	done
	return 1
}

report_stranded_prs() {
	local str_repo="$1"
	local str_prs int_pr str_sha int_rc
	local list_stranded=() list_unknown=()
	if ! str_prs="$(gh pr list --repo "$str_repo" --state open --limit 1000 --json number,headRefOid \
		--jq '.[] | "\(.number) \(.headRefOid)"' 2>&1)"; then
		print_status "warning" "Could not LIST open PRs on $str_repo (stranded PRs UNKNOWN, not none): ${str_prs:-no output from gh}"
		return 0
	fi
	while read -r int_pr str_sha; do
		[ -n "$int_pr" ] || continue
		pr_has_codeql_analysis "$str_repo" "$int_pr" "$str_sha" && int_rc=0 || int_rc=$?
		case "$int_rc" in
		1) list_stranded+=("#$int_pr") ;;
		2) list_unknown+=("#$int_pr") ;;
		esac
	done <<<"$str_prs"
	[ ${#list_unknown[@]} -eq 0 ] || print_status "warning" "Could not read CodeQL analyses for open PRs ${list_unknown[*]} (UNKNOWN, not confirmed stranded)"
	[ ${#list_stranded[@]} -gt 0 ] || return 0
	print_status "warning" "Open PRs with no CodeQL analysis on their head: ${list_stranded[*]} — the code_scanning rule blocks their merge (HTTP 405) until each gets a fresh push, e.g. 'git commit --allow-empty -m \"chore: trigger CodeQL\" && git push'"
}

main() {
	if [ "${1:-}" = "verify" ]; then
		verify_strict_required_checks
		return $?
	fi
	if [ "${1:-}" = "check_ruleset" ]; then
		check_ruleset_present
		return $?
	fi
	if [ "${1:-}" = "stranded" ]; then
		require_gh || return 0
		report_stranded_prs "${GITHUB_REPOSITORY:-$(resolve_repo)}"
		return 0
	fi

	print_status "section" "Repository Rules & Merge Settings"
	if ! require_gh; then
		return 0
	fi

	local str_repo
	str_repo="$(resolve_repo)"
	if [ -z "$str_repo" ]; then
		print_status "warning" "No GitHub remote resolved — skipping (push the repo to GitHub first)"
		return 0
	fi

	enable_code_scanning "$str_repo"
	enable_merge_settings "$str_repo"
	ensure_optout_label "$str_repo"
	apply_ruleset "$str_repo"
	report_stranded_prs "$str_repo"

	report_blocking_checks "$str_repo" || true

	local str_branch
	str_branch="$(gh api "repos/$str_repo" --jq .default_branch 2>/dev/null || echo main)"
	assert_branch_protection_strict "$str_repo" "$str_branch" || true
}

main "$@"
