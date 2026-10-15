#!/usr/bin/env bash

# shellcheck source=bin/lib/scaffold_kanban.sh
source "$(dirname "${BASH_SOURCE[0]}")/scaffold_kanban.sh"

: "${SCAFFOLD_REPO_HOMEPAGE:=}"

: "${INCLUDE_REVIEW_BOT_ROSTER:=true}"

scaffold_prompt_review_bot_roster() {
	local str_answer
	prompt_read str_answer "$(prompt_main "Do you have (or will you install) a PR review bot such as CodeRabbit on this repo? [Y/n]: ")"
	case "$str_answer" in
	n | N)
		# shellcheck disable=SC2034
		INCLUDE_REVIEW_BOT_ROSTER=false
		print_status "config" ".review-bots.yaml: not shipped — the review-thread required check will self-skip (pass) until a reviewer is declared"
		;;
	*)
		# shellcheck disable=SC2034
		INCLUDE_REVIEW_BOT_ROSTER=true
		;;
	esac
}

scaffold_prune_review_bot_roster() {
	local str_project_path="$1"
	[[ "${INCLUDE_REVIEW_BOT_ROSTER:-true}" == "true" ]] ||
		rm -f "$str_project_path/.github/.review-bots.yaml"
}

SCAFFOLD_REMOTE_VERIFIED=0

scaffold_repo_slug() {
	printf '%s' "${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}"
}

scaffold_remote_slug() {
	local str_url="${1%.git}"
	local str_rest
	str_url="${str_url%/}"

	case "$str_url" in
	*@github.com:*) str_rest="${str_url##*@github.com:}" ;;
	github.com:*) str_rest="${str_url#github.com:}" ;;
	*://*)
		str_rest="${str_url#*://}"
		str_rest="${str_rest#*@}"
		case "$str_rest" in
		github.com/*) str_rest="${str_rest#github.com/}" ;;
		*) str_rest="$str_url" ;;
		esac
		;;
	*) str_rest="$str_url" ;;
	esac
	printf '%s' "$str_rest"
}

scaffold_add_git_remote() {
	local str_project_path="$1"
	local str_slug str_url
	local -a list_urls=()
	str_slug="$(scaffold_repo_slug)"

	if git -C "$str_project_path" remote get-url origin >/dev/null 2>&1; then
		mapfile -t list_urls < <(
			git -C "$str_project_path" remote get-url --all origin 2>/dev/null
			git -C "$str_project_path" remote get-url --push --all origin 2>/dev/null
		)
		for str_url in "${list_urls[@]}"; do
			if [ "$(scaffold_remote_slug "$str_url")" != "$str_slug" ]; then
				print_status "error" \
					"Remote 'origin' points at a different repository — refusing to continue."
				print_status "info" "  configured: ${str_url}"
				print_status "info" "  expected:   git@github.com:${str_slug}.git"
				print_status "info" \
					"Remove or retarget 'origin' yourself, then re-run — never guessing which you meant."
				return 1
			fi
		done
		print_status "info" "Remote 'origin' already points at ${str_slug}"
		return 0
	fi
	git -C "$str_project_path" remote add origin "git@github.com:${str_slug}.git"
}

scaffold_create_github_repo() {
	local str_project_path="$1"
	local str_slug str_vis_choice str_vis_flag
	str_slug="$(scaffold_repo_slug)"
	local -a list_homepage=()

	if ! command -v gh >/dev/null 2>&1; then
		print_status "info" \
			"gh CLI not found; to publish run: git push -u origin main (ensure repo exists on GitHub)."
		return 1
	fi

	str_create_ans=""
	prompt_read str_create_ans "Create GitHub repo ${str_slug} and push now? [y/N]: "
	case "$str_create_ans" in
	y | Y) ;;
	*)
		print_status "info" "Skipped GitHub repo creation/push"
		return 1
		;;
	esac

	prompt_read str_vis_choice "Visibility [1] Public (default)  [2] Private: "
	str_vis_flag="--public"
	[ "$str_vis_choice" = "2" ] && str_vis_flag="--private"
	[ -n "$SCAFFOLD_REPO_HOMEPAGE" ] && list_homepage=(--homepage "$SCAFFOLD_REPO_HOMEPAGE")

	if gh repo create "$str_slug" "${list_homepage[@]}" \
		--description "$PROJECT_DESCRIPTION" "$str_vis_flag"; then
		scaffold_set_secret_scan_key
		if ! git -C "$str_project_path" push -u origin HEAD:main; then
			print_status "warning" \
				"Repo ${str_slug} created but the push failed - incomplete; skipped: default branch, kanban."
			print_status "info" "Fix the error above, then run: git push -u origin HEAD:main"
			return 0
		fi
		gh repo edit "$str_slug" --default-branch main "${list_homepage[@]}" >/dev/null 2>&1 || true
		print_status "success" "Repository created and pushed via gh."
		scaffold_kanban_setup
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

scaffold_set_review_trigger_secret() {
	local str_slug
	str_slug="$(scaffold_repo_slug)"

	if [ -z "${GH_PAT_REVIEW_TRIGGER:-}" ]; then
		print_status "warning" \
			"GH_PAT_REVIEW_TRIGGER not in the environment — the review trigger will be red on the first PR"
		print_status "info" \
			"  gh secret set GH_PAT_REVIEW_TRIGGER --repo ${str_slug} --body '<github_pat_...>'"
		return 0
	fi
	if ! command -v gh >/dev/null 2>&1; then
		return 0
	fi
	if gh secret set GH_PAT_REVIEW_TRIGGER --repo "$str_slug" \
		--body "$GH_PAT_REVIEW_TRIGGER" >/dev/null 2>&1; then
		print_status "success" "Review-trigger secret set on ${str_slug}"
	else
		print_status "warning" "Could not set GH_PAT_REVIEW_TRIGGER on ${str_slug} — set it by hand"
	fi
}

scaffold_set_secret_scan_key() {
	local str_slug
	str_slug="$(scaffold_repo_slug)"

	if [ -z "${GITGUARDIAN_API_KEY:-}" ]; then
		return 0
	fi
	if ! command -v gh >/dev/null 2>&1; then
		print_status "warning" "gh unavailable — skipping the secret-scan workflow (no key can be set)"
		unset GITGUARDIAN_API_KEY
		return 0
	fi
	if printf '%s' "$GITGUARDIAN_API_KEY" |
		gh secret set GITGUARDIAN_API_KEY --repo "$str_slug" >/dev/null 2>&1; then
		print_status "success" "GitGuardian secret-scan key set on ${str_slug}"
	else
		print_status "warning" \
			"Could not set GITGUARDIAN_API_KEY on ${str_slug} — skipping the secret-scan workflow"
		unset GITGUARDIAN_API_KEY
	fi
}

scaffold_prompt_git_remote_setup() {
	local str_project_path="$1"
	local str_answer
	SCAFFOLD_REMOTE_VERIFIED=0

	print_status "info" \
		"Optional: add a remote origin / create a GitHub repo (the local repo is already initialized)"
	prompt_read str_answer "Add remote origin and (optionally) create the GitHub repo now? [y/N]: "

	case "$str_answer" in
	y | Y) ;;
	*)
		print_status "info" "Skipped remote setup"
		return 1
		;;
	esac

	scaffold_add_git_remote "$str_project_path" || return 1
	# shellcheck disable=SC2034
	SCAFFOLD_REMOTE_VERIFIED=1
	if ! scaffold_create_github_repo "$str_project_path"; then
		scaffold_set_secret_scan_key
		scaffold_push_initial_commit "$str_project_path"
	fi
	scaffold_set_review_trigger_secret
	git -C "$str_project_path" rev-parse '@{u}' >/dev/null 2>&1 || return 1
	print_status "success" "Git repo initialized."
}
