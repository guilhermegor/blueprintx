#!/usr/bin/env bash
# Provision the `pr-quality-gate` branch ruleset + the repo settings the PR gate depends on.
#
# WHY THIS EXISTS: merge protection that lives in a maintainer's memory is protection a fresh
# clone or fork silently lacks. The ENTIRE ruleset is writable through the REST API, so nothing
# here needs a click in Settings → Rules. Like enable_pages.sh, these are repo-settings writes:
# CI's GITHUB_TOKEN (an App installation token) CANNOT make them — only a maintainer's `gh auth`
# with repo-admin can. Hence `poe init`, not CI.
#
# WHAT IT APPLIES (idempotent — looked up BY NAME, then PUT if it exists / POST if it does not;
# never a blind POST, which would duplicate the ruleset):
#   * pull_request              — required_approving_review_count: 0 (see below) +
#                                 required_review_thread_resolution: true, so review comments are
#                                 binding (unresolved → no merge) instead of decorative.
#   * code_scanning             — CodeQL, security alerts high_or_higher, alerts at `errors`.
#   * copilot_code_review       — its OWN rule type (NOT a pull_request parameter — see below).
#   * non_fast_forward, deletion — no force-push, no branch deletion.
#   * required_status_checks    — ONLY when REQUIRED_CHECKS below is non-empty (see the warning).
# Plus the settings the gate cannot set itself: code-scanning default setup, allow_auto_merge,
# delete_branch_on_merge, and the `do-not-merge` opt-out label.
#
# ⚠️ required_approving_review_count MUST be 0: GitHub forbids an author approving their own PR,
# so any value >= 1 locks a solo maintainer out of merging their own work. Zero still forces every
# change through a PR — that is the actual guardrail.
#
# ⚠️ Copilot automatic code review is REST-settable, but as its own rule type. The intuitive
# `pull_request.parameters.automatic_copilot_code_review_enabled` returns HTTP 422 "Unexpected
# parameter", which makes the feature LOOK UI-only — it is not.
#
# ⚠️ THE AUTOMATIC/MANUAL BOUNDARY IS REPO CONFIG vs ACCOUNT PLAN. Every repository setting here
# is scriptable. What is NOT is the account's entitlement: the copilot_code_review rule only fires
# if the author has access to Copilot code review, and code review is NOT part of Copilot Free.
# Without a qualifying plan the rule sits correctly configured and INERT — no review appears and
# nothing errors. The silence is the trap; the ruleset JSON looks perfect either way. Every OTHER
# rule (PR required, CI green, CodeQL clean) works regardless of any Copilot plan.
#   Do NOT diagnose this via `gh api user/copilot_billing` → 404: that endpoint is for org seat
#   management and 404s for a personal account even when Copilot Free is active. Read the plan page.
#
# DELIBERATELY NOT ENABLED (each would be a second source of truth for a gate this scaffold
# already owns): "Require code quality results" (subjective AI severity on the merge path — ruff,
# mypy and the bin/check_*.py gates already enforce quality deterministically) and "Restrict code
# coverage" (preview; the floor is single-sourced in .coveragerc fail_under).
#
# Idempotent + non-blocking: gh absent / unauthenticated / not repo-admin → WARN and return 0 so
# `init` still completes.
#
# `bash enable_repo_rules.sh verify` — read-only guard (blueprintx#307), no admin needed: asserts
# `strict_required_status_checks_policy` / `required_status_checks.strict` is true, on whichever
# mechanism (ruleset or classic branch protection) the repo actually has. Unlike every other path
# in this file, `verify` DOES fail loud (non-zero exit) — see verify_strict_required_checks.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

RULESET_NAME="pr-quality-gate"

# ⚠️ DO NOT GUESS CHECK NAMES — but do not leave this empty either.
#
# A required status check that never reports blocks every PR FOREVER (GitHub waits for a result
# that will never arrive), and the names must match the check-run names exactly — which for a
# matrix job include the expanded matrix values. That is why the rest of this list is yours to
# populate from a REAL PR once CI has run:
#
#   gh api repos/:owner/:repo/commits/<pr-head-sha>/check-runs --jq '.check_runs[].name' | sort -u
#
# The seeded entry is NOT a guess: it is the `name:` of the job in the `review_threads.yaml`
# this same template ships, so it is correct by construction, and it triggers `on: pull_request`,
# so it reports on EVERY pull request from the moment it opens — the one property a required
# check must have.
#
# ⚠️ SUPERSEDED 2026-08-24 (blueprintx#196). This block used to add that the job was safe to
# require because it asserted only the REPLY half (`REVIEW_THREADS_REQUIRE_RESOLVED=0`), leaving
# RESOLUTION to the ruleset's `required_review_thread_resolution` — which evaluates at the merge
# button and "cannot go stale". The trigger reasoning holds; the delegation does not: that
# setting DROPS a thread marked `isOutdated`, and a thread outdates when the author's own commit
# rewrites the commented lines. So the job now runs with `REVIEW_THREADS_REQUIRE_RESOLVED=1` and
# asserts BOTH halves. The accepted cost is that a resolve leaves the check red until the run is
# re-run by hand — resolving fires no workflow trigger. The ruleset setting is still provisioned
# below as the merge-button layer; it is simply no longer the ONLY thing asserting resolution.
#
# 🔴 Why this matters more than it looks: an EMPTY list means CI runs on every PR and blocks
# nothing. Measured blueprintx 2026-08-16: a PR merged with **32 of 47 checks passed** and no
# rule objected, because the only things standing between a red check and `main` were a hook and
# a habit — and both are probabilistic. A gate nobody can bypass by forgetting is the whole point.
REQUIRED_CHECKS=("Review threads answered")

require_gh() {
	# gh must be installed and authenticated. Missing either is a skip, not a failure.
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
	# Print owner/repo for the current checkout, or empty when no GitHub remote resolves.
	gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true
}

build_rules_json() {
	# Emit the rules array. required_status_checks is appended only when REQUIRED_CHECKS is set,
	# because an unsatisfiable required check is a permanent merge block (see the warning above).
	local str_checks_rule=""
	if [ ${#REQUIRED_CHECKS[@]} -gt 0 ]; then
		local str_contexts=""
		local str_check
		for str_check in "${REQUIRED_CHECKS[@]}"; do
			str_contexts+="$(printf '{"context":"%s"},' "$str_check")"
		done
		str_contexts="${str_contexts%,}"
		# 🔴 strict_required_status_checks_policy MUST be true (blueprintx#307). This is
		# GitHub's "Require branches to be up to date before merging" — with it false, a PR
		# can merge on a green run that was evaluated against a base that no longer exists
		# (measured on blueprintx#302: 6 tier checks were red only because a dependency,
		# #293, had not merged yet; a rebase, not a re-run, fixed the verdict). Textual
		# conflicts are already blocked by git; this is the semantic-conflict case git
		# cannot see. The cost is real (a PR whose base moved must be updated before
		# merging) and is the accepted trade for a signal that means what it says.
		str_checks_rule=$(printf ',{"type":"required_status_checks","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[%s]}}' "$str_contexts")
	fi

	cat <<EOF
[
  {"type":"pull_request","parameters":{
    "required_approving_review_count":0,
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
  {"type":"deletion"}${str_checks_rule}
]
EOF
}

build_ruleset_json() {
	# The full ruleset payload. `~DEFAULT_BRANCH` survives a branch rename and ports to any repo.
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
	# Idempotent: find the ruleset BY NAME, then PUT (update) or POST (create). $1 = owner/repo.
	local str_repo="$1"
	local str_id
	str_id=$(gh api "repos/$str_repo/rulesets" --jq \
		".[] | select(.name == \"$RULESET_NAME\") | .id" 2>/dev/null | head -1 || true)

	# Keep the API's own words: never discard output whose failure you then explain. The old
	# form swallowed stderr and blamed admin rights for every failure, including the ones that
	# were a malformed payload.
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
	# Read the SERVER back instead of echoing what we meant to send. `apply_ruleset` returns 0
	# even when the API refused it (deliberately — this step must never abort `init`), so a
	# summary built from REQUIRED_CHECKS would announce a gate that may not exist. A
	# provisioning step that reports its own INPUT has verified nothing; that is the same
	# failure this ruleset exists to remove, one level up. $1 = owner/repo.
	#
	# blueprintx#307: also assert `strict_required_status_checks_policy` is true, not merely
	# that checks exist — an unstrict required check still lets a PR merge on a run that never
	# saw its base. This is the ONLY line in the function that can return non-zero: callers
	# choose whether that aborts them (`main`'s init flow swallows it — see the header, `poe
	# init` must never fail; the `verify` subcommand does not).
	local str_repo="$1"
	local str_id str_live str_strict
	# ⚠️ A failed READ must never be reported as an empty ANSWER. Swallowing the error turns a
	# permission failure, a rate limit or a dropped connection into "nothing blocks a merge" —
	# a job announcing the exact blindness it exists to remove. "I could not check" and "I
	# checked and found nothing" are different verdicts and must print differently.
	if ! str_id="$(gh api "repos/$str_repo/rulesets" --jq \
		".[] | select(.name == \"$RULESET_NAME\") | .id" 2>&1)"; then
		print_status "warning" "Could not READ rulesets from $str_repo (so the blocking set is UNKNOWN, not empty): ${str_id:-no output from gh}"
		return 0
	fi
	str_id="$(printf '%s\n' "$str_id" | head -1)"
	if [ -z "$str_id" ]; then
		print_status "warning" "Ruleset '$RULESET_NAME' is NOT present on $str_repo — nothing blocks a merge"
		return 0
	fi
	if ! str_live="$(gh api "repos/$str_repo/rulesets/$str_id" --jq \
		'[.rules[]? | select(.type == "required_status_checks")
		  | .parameters.required_status_checks[]?.context] | join(", ")' 2>&1)"; then
		print_status "warning" "Could not READ ruleset '$RULESET_NAME' from $str_repo (so the blocking set is UNKNOWN, not empty): ${str_live:-no output from gh}"
		return 0
	fi
	if [ -z "$str_live" ]; then
		print_status "warning" "Ruleset '$RULESET_NAME' is active but declares NO required status checks — CI runs and blocks NOTHING. Populate REQUIRED_CHECKS in bin/enable_repo_rules.sh from a real PR's check-run names, then re-run."
		return 0
	fi
	print_status "config" "Merge-blocking checks live on $str_repo: $str_live"

	if ! str_strict="$(gh api "repos/$str_repo/rulesets/$str_id" --jq \
		'[.rules[]? | select(.type == "required_status_checks")
		  | .parameters.strict_required_status_checks_policy] | first' 2>&1)"; then
		print_status "warning" "Could not READ the strict policy on $str_repo (so it is UNKNOWN, not enforced): ${str_strict:-no output from gh}"
		return 0
	fi
	if [ "$str_strict" != "true" ]; then
		print_status "error" "strict_required_status_checks_policy is NOT true on $str_repo (ruleset '$RULESET_NAME') — a PR can merge on a green run that never saw its base (blueprintx#307)"
		return 1
	fi
	print_status "success" "strict_required_status_checks_policy is enforced on $str_repo (ruleset '$RULESET_NAME', verified)"
}

assert_branch_protection_strict() {
	# BlueprintX's OWN `main` is on CLASSIC branch protection, not the ruleset this script
	# provisions (blueprintx#164 — this script has never been run against this repo). The
	# ruleset check above is silent about that: an ABSENT ruleset reads as "nothing blocks",
	# true for that mechanism but silent on whether a repo enforces the same setting through
	# classic protection instead. Read it back explicitly so #307 is guarded either way.
	# $1 = owner/repo, $2 = branch.
	local str_repo="$1" str_branch="$2"
	local str_strict
	if ! str_strict="$(gh api "repos/$str_repo/branches/$str_branch/protection" --jq \
		'.required_status_checks.strict' 2>&1)"; then
		print_status "warning" "Could not READ classic branch protection on $str_repo:$str_branch (so strict is UNKNOWN, not enforced): ${str_strict:-no output from gh}"
		return 0
	fi
	if [ "$str_strict" = "null" ] || [ -z "$str_strict" ]; then
		print_status "warning" "$str_repo:$str_branch has no required_status_checks under classic branch protection — nothing to assert strict on"
		return 0
	fi
	if [ "$str_strict" != "true" ]; then
		print_status "error" "required_status_checks.strict is NOT true on $str_repo:$str_branch (classic branch protection) — a PR can merge on a green run that never saw its base (blueprintx#307)"
		return 1
	fi
	print_status "success" "required_status_checks.strict is enforced on $str_repo:$str_branch (classic branch protection, verified)"
}

verify_strict_required_checks() {
	# Read-only CI guard for blueprintx#307. Unlike the rest of this script — which must
	# NEVER abort `poe init` (see the file header) — this mode exists to fail: it is what
	# `.github/workflows/verify_branch_protection.yml` runs against BlueprintX itself, and
	# what a generated project's own CI can run the same way. No writes, so it needs only
	# read access, unlike the provisioning steps in `main`. Checks BOTH mechanisms (see the
	# two assert functions above) since either may be the one a repo actually has configured.
	if ! require_gh; then
		return 1
	fi
	local str_repo str_branch
	str_repo="$(resolve_repo)"
	if [ -z "$str_repo" ]; then
		print_status "error" "No GitHub remote resolved — cannot verify branch protection"
		return 1
	fi
	str_branch="$(gh api "repos/$str_repo" --jq .default_branch 2>/dev/null || echo main)"

	local int_status=0
	report_blocking_checks "$str_repo" || int_status=1
	assert_branch_protection_strict "$str_repo" "$str_branch" || int_status=1
	return "$int_status"
}

enable_code_scanning() {
	# The code_scanning rule needs a tool to gate on. Already-configured → the PATCH is a no-op.
	local str_repo="$1"
	if gh api -X PATCH "repos/$str_repo/code-scanning/default-setup" -f state=configured >/dev/null 2>&1; then
		print_status "success" "CodeQL default setup configured"
	else
		print_status "warning" "Could not configure CodeQL default setup (needs repo-admin, or the language is unsupported) — enable it in Settings → Code security"
	fi
}

enable_merge_settings() {
	# Prerequisites the PR gate CANNOT set itself. Without allow_auto_merge the
	# enablePullRequestAutoMerge mutation SILENTLY NO-OPS — the feature is inert with no error.
	local str_repo="$1"
	if gh api -X PATCH "repos/$str_repo" -F allow_auto_merge=true -F delete_branch_on_merge=true >/dev/null 2>&1; then
		# Read the setting BACK: a green API call is not proof the mutation took.
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
	# The PR gate's opt-OUT escape hatch: safe classes auto-merge by default; this label disables it.
	local str_repo="$1"
	gh label create "do-not-merge" --repo "$str_repo" --color "b60205" \
		--description "Block this PR from auto-merging (PR gate opt-out)" --force >/dev/null 2>&1 &&
		print_status "success" "Label 'do-not-merge' present (auto-merge opt-out)" ||
		print_status "warning" "Could not create the 'do-not-merge' label on $str_repo"
}

main() {
	# `verify` is the read-only CI guard (blueprintx#307) — see verify_strict_required_checks
	# for why it is the one path here allowed to return non-zero.
	if [ "${1:-}" = "verify" ]; then
		verify_strict_required_checks
		return $?
	fi

	print_status "section" "Repository Rules & Merge Settings"
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

	enable_code_scanning "$str_repo"
	enable_merge_settings "$str_repo"
	ensure_optout_label "$str_repo"
	apply_ruleset "$str_repo"

	# Say which checks actually block, every time, and say it from the SERVER's answer. A step
	# silent about the blocking set is indistinguishable from one that provisioned nothing —
	# and "nothing blocks" is the failure this list exists to prevent, so it must never be the
	# quiet outcome. It can now return 1 (blueprintx#307, strict is not enforced) — swallowed
	# here so `init` still completes; `poe enable_repo_rules verify` is the path that doesn't.
	report_blocking_checks "$str_repo" || true

	# Classic branch protection is a secondary mechanism most generated projects won't use,
	# but the read is one API call and closes the same gap for a repo — like BlueprintX itself
	# — that predates this script or manages protection outside it. Non-blocking, same as
	# every other step above.
	local str_branch
	str_branch="$(gh api "repos/$str_repo" --jq .default_branch 2>/dev/null || echo main)"
	assert_branch_protection_strict "$str_repo" "$str_branch" || true
}

main "$@"
