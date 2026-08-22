#!/usr/bin/env bash
# Git remote / GitHub repo setup, shared by every scaffold regardless of language.
#
# ⚠️ WHY THIS IS A SEPARATE FILE FROM scaffold_python_templates.sh, and not one
# "scaffold_common.sh". It was one file for exactly as long as it took
# bin/ci/check_test_copy_lists.py to go wrong: that gate treats a scaffold plus the
# libs it SOURCES as the reachable set, but lib-minimal sources this half for the git
# prompt while never calling the Python copy functions -- so the union claimed four
# shared tests reached lib-minimal when nothing copies them there. Over-reporting
# reachability is the DANGEROUS direction for that gate: it is the one that lets a test
# silently never run while the gate says it does.
#
# Splitting the file makes `source` mean what the gate assumes it means, with no call
# graph to maintain: a scaffold sources only the halves it uses.
#
# This is a sourced lib: define-only, no work on source. Reads GITHUB_USERNAME,
# DEFAULT_GITHUB_USERNAME, PROJECT_NAME and PROJECT_DESCRIPTION from the caller.

# Git remote / GitHub repo setup — LANGUAGE-AGNOSTIC (used by the Python and TS scaffolds
# alike, unlike the copy_common_templates half above, which is Python-tier-specific).
#
# This replaced six near-identical copies (65, 65, 65, 65, 67, 64 lines). After the
# `warn` -> `warning` fix they reduced to exactly TWO axes of variation, which is what
# made one implementation honest rather than a lowest-common-denominator merge:
#
#   1. an optional `--homepage` on the created repo (lib-minimal sets the Pages docs URL);
#   2. what runs AFTER the prompt (nothing for the service tiers, which defer branch
#      protection to commit_and_push_github_assets; apply_branch_protection for
#      lib-minimal; that plus prompt_pages_setup for the React SPA).
#
# Axis 1 is a variable the caller may set; axis 2 stays in the caller's own wrapper,
# because "what happens next" is genuinely per-tier policy and folding it in would mean
# a flag that means "which tier am I", which is how a shared function rots.

# Set by the caller before scaffold_prompt_git_remote_setup; empty means no --homepage.
: "${SCAFFOLD_REPO_HOMEPAGE:=}"

scaffold_add_git_remote() {
	local str_project_path="$1"

	if git -C "$str_project_path" remote get-url origin >/dev/null 2>&1; then
		print_status "warning" "Remote 'origin' already exists; skipped add"
		return 0
	fi
	git -C "$str_project_path" remote add origin \
		"git@github.com:${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}.git" || true
}

scaffold_create_github_repo() {
	# Returns 0 when the repo was created AND pushed, so the caller can skip its own push.
	#
	# ⚠️ The exit status is the whole point. The version this replaced set `push_done=1`
	# INSIDE a `( cd … )` subshell, so the assignment never reached the parent and the
	# follow-up push always ran. ShellCheck had been reporting it as SC2030/SC2031 the
	# entire time — at `info` severity, below the `--severity=warning` floor the gate used,
	# so nobody ever saw it. Testing the subshell's status keeps the `cd` contained without
	# needing a variable to escape it.
	local str_project_path="$1"
	local str_slug="${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}"
	local str_vis_choice str_vis_flag
	local -a list_homepage=()

	if ! command -v gh >/dev/null 2>&1; then
		print_status "info" \
			"gh CLI not found; to publish run: git push -u origin main (ensure repo exists on GitHub)."
		return 1
	fi

	read -r -p "Create GitHub repo ${str_slug} and push now? [y/N]: " str_create_ans || true
	case "$str_create_ans" in
	y | Y) ;;
	*)
		print_status "info" "Skipped GitHub repo creation/push"
		return 1
		;;
	esac

	read -r -p "Visibility [1] Public (default)  [2] Private: " str_vis_choice || true
	str_vis_flag="--public"
	[ "$str_vis_choice" = "2" ] && str_vis_flag="--private"
	[ -n "$SCAFFOLD_REPO_HOMEPAGE" ] && list_homepage=(--homepage "$SCAFFOLD_REPO_HOMEPAGE")

	if (cd "$str_project_path" && gh repo create "$str_slug" --source . --remote origin --push \
		"${list_homepage[@]}" --description "$PROJECT_DESCRIPTION" "$str_vis_flag"); then
		gh repo edit "$str_slug" --default-branch main "${list_homepage[@]}" >/dev/null 2>&1 || true
		print_status "success" "Repository created and pushed via gh."
		return 0
	fi

	print_status "warning" "gh repo create failed; check authentication or if the repo already exists."
	print_status "info" "Manual fallback: create the repo on GitHub and run 'git push -u origin main'."
	return 1
}

scaffold_push_initial_commit() {
	local str_project_path="$1"

	if ! git -C "$str_project_path" remote get-url origin >/dev/null 2>&1; then
		print_status "warning" \
			"Remote 'origin' missing; cannot push. Create repo and run 'git push -u origin main'."
		return 0
	fi
	if git -C "$str_project_path" push -u origin main >/dev/null 2>&1; then
		print_status "success" "Pushed to origin/main."
	else
		print_status "warning" \
			"Push to origin/main failed; create the repo on GitHub and retry 'git push -u origin main'."
	fi
}

scaffold_prompt_git_remote_setup() {
	local str_project_path="$1"
	local str_answer

	print_status "info" \
		"Optional: add a remote origin / create a GitHub repo (the local repo is already initialized)"
	read -r -p "Add remote origin and (optionally) create the GitHub repo now? [y/N]: " str_answer || true

	case "$str_answer" in
	y | Y) ;;
	*)
		print_status "info" "Skipped remote setup"
		return 0
		;;
	esac

	scaffold_add_git_remote "$str_project_path"
	if ! scaffold_create_github_repo "$str_project_path"; then
		scaffold_push_initial_commit "$str_project_path"
	fi
	print_status "success" "Git repo initialized."
}
