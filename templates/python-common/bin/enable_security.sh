#!/usr/bin/env bash
# Flip the free, API-settable GitHub security toggles for this repo.
#
# WHY THIS EXISTS: a published project should have supply-chain + vulnerability-reporting hygiene
# on, but the Settings → Security checkboxes are not reproducible and are silently forgotten on a
# fork or a fresh clone — the same rationale that put the branch ruleset in enable_repo_rules.sh.
# The three toggles below are plain PUTs (204 No Content); secret scanning + push protection are
# NOT a fourth toggle — see enable_secret_scanning for why they need their own PATCH.
#
# Sibling of enable_repo_rules.sh / enable_pages.sh: these are repo-settings writes, so CI's
# GITHUB_TOKEN (an App installation token) CANNOT make them — only a maintainer's `gh auth` with
# repo-admin can. Hence `poe init`, not CI. Idempotent + non-blocking throughout.
#
# NOT scripted here (it needs no API call): GitHub auto-detects a root SECURITY.md and flips
# "Security policy" to Enabled by itself. The scaffold ships that file.
#
# Version bumps vs security fixes are DIFFERENT features:
#   * automated-security-fixes (below)  — Dependabot opens PRs for known VULNERABILITIES.
#   * .github/dependabot.yml (shipped)  — Dependabot opens PRs for ordinary VERSION updates.
#
# GitGuardian (blueprintx#155) was evaluated for the secret-detection role this file's toggles
# fill and deferred: these are public repos with a GitHub remote, so the native toggles below are
# free and need no third-party app/token/config. Reconsider only if the scaffold starts covering
# private repos (where secret scanning becomes a paid SKU) or the offline tier wants a local,
# pre-commit-time scanner — a separate decision from "which SaaS provider".
#
# blueprintx#164 self-audit (2026-09-04, read-only `gh api` reads, no writes — full numbers in
# docs/backlog/repo_rules_self_audit_164_20260904_062813.md): this script had never been run
# against BlueprintX itself either, but found NO divergence — `vulnerability-alerts`,
# `automated-security-fixes`, and `private-vulnerability-reporting` were already enabled on
# blueprintx. Unlike enable_repo_rules.sh, this file has no read-only/`verify` mode at all;
# noted as a gap, not fixed here (a dry-run mode is a second script surface, out of scope for a
# read-only audit).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

require_gh() {
	# gh must be installed and authenticated. Missing either is a skip, not a failure.
	if ! command -v gh >/dev/null 2>&1; then
		print_status "warning" "gh CLI not found — skipping security toggles (run 'poe enable_security' later)"
		return 1
	fi
	if ! gh auth status >/dev/null 2>&1; then
		print_status "warning" "gh not authenticated — skipping security toggles (run 'gh auth login', then 'poe enable_security')"
		return 1
	fi
	return 0
}

resolve_repo() {
	# Print owner/repo for the current checkout, or empty when no GitHub remote resolves.
	gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true
}

enable_toggle() {
	# PUT one security toggle. $1 = owner/repo, $2 = API path segment, $3 = human label.
	local str_repo="$1" str_path="$2" str_label="$3"
	if gh api -X PUT "repos/$str_repo/$str_path" >/dev/null 2>&1; then
		print_status "success" "$str_label enabled"
	else
		print_status "warning" "Could not enable $str_label (needs repo-admin rights, or it is unavailable for this repo) — check Settings → Code security"
	fi
}

enable_secret_scanning() {
	# Secret scanning + push protection live on the repo object itself, set via
	# PATCH /repos/{owner}/{repo} with a security_and_analysis body — NOT a toggle path, so
	# enable_toggle's PUT cannot express this. $1 = owner/repo.
	#
	# Both fields ship in ONE PATCH, secret_scanning listed first: push protection depends on
	# scanning already being on, and GitHub applies a security_and_analysis body's fields in the
	# order given.
	#
	# Free on public repos only — a private repo is on the paid Secret Protection SKU and this
	# call 422s/403s there, same as any other toggle in this file: warn and keep going.
	local str_repo="$1"
	local json_body='{"security_and_analysis":{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}}'
	if gh api -X PATCH "repos/$str_repo" --input - <<<"$json_body" >/dev/null 2>&1; then
		print_status "success" "Secret scanning + push protection enabled"
	else
		print_status "warning" "Could not enable secret scanning / push protection (private repos need the paid Secret Protection SKU, or repo-admin rights) — check Settings → Code security"
	fi
}

main() {
	print_status "section" "GitHub Security Toggles"
	# A skip (no gh / not authed) must not fail init — return 0 either way.
	if ! require_gh; then
		return 0
	fi

	local str_repo
	str_repo="$(resolve_repo)"
	if [ -z "$str_repo" ]; then
		print_status "warning" "No GitHub remote resolved — skipping (push the repo to GitHub first)"
		return 0
	fi

	# Private vulnerability reporting — the intake channel SECURITY.md points researchers at.
	enable_toggle "$str_repo" "private-vulnerability-reporting" "Private vulnerability reporting"
	# Dependabot alerts must be on BEFORE automated security fixes, which depend on them.
	enable_toggle "$str_repo" "vulnerability-alerts" "Dependabot alerts"
	enable_toggle "$str_repo" "automated-security-fixes" "Dependabot security updates"
	# PATCH-based, not a toggle path — see enable_secret_scanning.
	enable_secret_scanning "$str_repo"
}

main "$@"
