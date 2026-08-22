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

# Set BY this lib, read by the caller's `main`: 1 only once `origin` has been verified to be
# the repository this scaffold names.
#
# ⚠️ A RETURN VALUE IS NOT ENOUGH, because `main` asks its question much later and asks it of
# git, not of us. Every tier selects online mode with `rev-parse @{u}` — "is there an upstream
# tracking branch?" — which is TRUE for a pre-existing clone whose origin points at someone
# else's repository. So a mismatch could be refused here, swallowed by the caller's `|| true`,
# and the scaffold would still take the online path and push the generated assets there.
# Raised by review on #215; the `|| true` alone was not the fix it looked like.
SCAFFOLD_REMOTE_VERIFIED=0

scaffold_repo_slug() {
	printf '%s' "${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}"
}

scaffold_remote_slug() {
	# Reduce a GitHub remote URL to its `owner/repo`, so ssh, scp-style and https
	# spellings of the SAME repository compare equal. Anything else returns unchanged
	# and therefore never equals a slug.
	#
	# ⚠️ THE HOST MUST BE MATCHED AS A HOST, NOT AS A SUBSTRING. The first version of
	# this matched `*github.com[:/]*` and cut at the LAST occurrence, so
	# `https://evil.example/github.com/octocat/widget.git` reduced to `octocat/widget`
	# and the guard accepted a remote pointing at an arbitrary host — defeating the
	# whole check for exactly the crafted input it exists to stop. Measured, not
	# theorised. Raised by review on #215.
	local str_url="${1%.git}"
	local str_rest
	str_url="${str_url%/}"

	case "$str_url" in
	# scp-style: [user@]github.com:owner/repo
	*@github.com:*) str_rest="${str_url##*@github.com:}" ;;
	github.com:*) str_rest="${str_url#github.com:}" ;;
	# URL forms: <scheme>://[user[:password]@]github.com/owner/repo
	*://*)
		str_rest="${str_url#*://}"
		str_rest="${str_rest#*@}"
		case "$str_rest" in
		# Anchored: `github.com.evil.com/...` and `evil.example/github.com/...` both miss.
		github.com/*) str_rest="${str_rest#github.com/}" ;;
		*) str_rest="$str_url" ;;
		esac
		;;
	*) str_rest="$str_url" ;;
	esac
	printf '%s' "$str_rest"
}

scaffold_add_git_remote() {
	# Returns non-zero when `origin` exists but points somewhere other than the
	# repository this scaffold was told to create.
	#
	# ⚠️ The verification is the point (#212). This used to treat "origin exists" as
	# "nothing to do" and move on — after which `gh repo create --push`, the follow-up
	# push, and branch protection all operated against whatever that remote happened to
	# be. Scaffolding into an existing clone therefore wrote to someone else's
	# repository. Low likelihood, and the highest-consequence operations in this file.
	local str_project_path="$1"
	local str_slug str_url
	local -a list_urls=()
	str_slug="$(scaffold_repo_slug)"

	if git -C "$str_project_path" remote get-url origin >/dev/null 2>&1; then
		# ⚠️ EVERY url, fetch AND push. `remote.origin.pushurl` may differ from the fetch
		# URL, so checking only `get-url origin` lets a remote that FETCHES from the right
		# repository PUSH the generated project somewhere else — and pushing is the whole
		# risk here. `--all` also covers a remote with several configured URLs.
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
	# Returns 0 when the repo was created AND pushed, so the caller can skip its own push.
	#
	# ⚠️ The exit status is the whole point. The version this replaced set `push_done=1`
	# INSIDE a `( cd … )` subshell, so the assignment never reached the parent and the
	# follow-up push always ran. ShellCheck had been reporting it as SC2030/SC2031 the
	# entire time — at `info` severity, below the `--severity=warning` floor the gate used,
	# so nobody ever saw it. Testing the subshell's status keeps the `cd` contained without
	# needing a variable to escape it.
	local str_project_path="$1"
	local str_slug str_vis_choice str_vis_flag
	str_slug="$(scaffold_repo_slug)"
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

scaffold_set_review_trigger_secret() {
	# Give the new repo the PAT its coderabbit_trigger workflow needs, from the environment.
	#
	# ⚠️ WHY THE SCAFFOLD DOES THIS AT ALL. Actions secrets are per-repository and `gh repo
	# create` copies none, so every scaffolded project starts with the workflow present and the
	# secret absent — the job red on its first PR. The scaffolder is already authenticated with
	# `gh` right here (it just created the repo and is about to protect the branch), so this is
	# one call at the only moment the information and the authority coexist.
	#
	# ⚠️ NEVER PERSIST THE VALUE IN THIS REPO. It is read from the environment — the shell gets
	# it from a git-ignored `~/.claude/.env` — so no BlueprintX file ever holds a credential.
	# A `.env` here would be a SECOND copy of the same secret on disk, and the second copy is
	# the one nobody remembers to rotate.
	#
	# Absent variable is a warning, not a failure: scaffolding must not abort over an optional
	# reviewer integration. The workflow itself is the thing that fails loudly, later, on the
	# first PR — where the person who can fix it is looking.
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
	# --body, never a redirect: a trailing newline in a stored token 401s exactly like an
	# expired one, and the error says nothing about which. Measured, twice.
	if gh secret set GH_PAT_REVIEW_TRIGGER --repo "$str_slug" \
		--body "$GH_PAT_REVIEW_TRIGGER" >/dev/null 2>&1; then
		print_status "success" "Review-trigger secret set on ${str_slug}"
	else
		print_status "warning" "Could not set GH_PAT_REVIEW_TRIGGER on ${str_slug} — set it by hand"
	fi
}

scaffold_prompt_git_remote_setup() {
	# Returns 0 only when `origin` is present AND verified to be the repository this
	# scaffold names — so a caller can gate branch protection / Pages on the remote
	# itself rather than on "the prompt returned" (#212). Declining is a normal
	# non-zero: there is no remote, so there is nothing to protect.
	local str_project_path="$1"
	local str_answer
	SCAFFOLD_REMOTE_VERIFIED=0

	print_status "info" \
		"Optional: add a remote origin / create a GitHub repo (the local repo is already initialized)"
	read -r -p "Add remote origin and (optionally) create the GitHub repo now? [y/N]: " str_answer || true

	case "$str_answer" in
	y | Y) ;;
	*)
		print_status "info" "Skipped remote setup"
		return 1
		;;
	esac

	scaffold_add_git_remote "$str_project_path" || return 1
	# Read by each scaffold's `main` (a different file), which shellcheck cannot follow.
	# shellcheck disable=SC2034
	SCAFFOLD_REMOTE_VERIFIED=1
	if ! scaffold_create_github_repo "$str_project_path"; then
		scaffold_push_initial_commit "$str_project_path"
	fi
	scaffold_set_review_trigger_secret
	print_status "success" "Git repo initialized."
}
