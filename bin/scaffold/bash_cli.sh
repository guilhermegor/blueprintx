#!/usr/bin/env bash
# Scaffolds the bash-cli skeleton: a standalone Bash CLI starter with git-tag
# versioning, `make install` stamping the version, bats tests, and shell lint
# (shellcheck + shfmt). Mechanics mirror ts_lib.sh / python_lib_minimal.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=bin/lib/scaffold_git_remote.sh
source "$SCRIPT_DIR/../lib/scaffold_git_remote.sh"

PROJECT_ROOT="${1:-}"
PROJECT_NAME="${2:-}"
PROJECT_DESCRIPTION="${3:-}"
LICENSE_CHOICE="${LICENSE_CHOICE:-MIT}"
GITHUB_USERNAME="${GITHUB_USERNAME:-}"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SKELETON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/bash-cli"
# Language-agnostic assets shared by every skeleton (CODEOWNERS, PR template, the
# shared print_status lib/common.sh).
SHARED_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/common"
LICENSES_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/licenses"
DEFAULT_GITHUB_USERNAME="${GITHUB_USERNAME:-your-github-username}"


validate_inputs() {
    if [ -z "$PROJECT_ROOT" ] || [ -z "$PROJECT_NAME" ]; then
        exit_error "Usage: $0 <project_root_dir> <project_name>"
    fi
    print_status "success" "Input validation passed"
}

resolve_github_username() {
    if [ -n "$GITHUB_USERNAME" ]; then
        print_status "config" "GitHub username (env): $GITHUB_USERNAME"
        return
    fi

    if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
        local gh_user
        gh_user=$(gh api user -q .login 2>/dev/null || true)
        if [ -n "$gh_user" ]; then
            GITHUB_USERNAME="$gh_user"
            print_status "config" "GitHub username (gh): $GITHUB_USERNAME"
            return
        fi
    fi

    local input
    read -r -p "$(prompt_main "GitHub username (default: $DEFAULT_GITHUB_USERNAME): ")" input || true
    GITHUB_USERNAME="${input:-$DEFAULT_GITHUB_USERNAME}"
    print_status "config" "GitHub username (prompt): $GITHUB_USERNAME"
}

create_directory_structure() {
    local project_path="$1"
    print_status "info" "Creating directory structure..."
    mkdir -p "$project_path"/bin
    mkdir -p "$project_path"/lib
    mkdir -p "$project_path"/tests
    mkdir -p "$project_path"/.github/workflows
    print_status "success" "Directory structure created"
}

# envsubst does no error checking of its own; restricting the substitution list to
# the one variable per call (same idiom as ts_lib.sh) means every other ${...} in
# these files — Make variables, GitHub Actions `${{ }}` expressions, bash parameter
# expansions like ${1:-} — passes through untouched.
copy_skeleton_files() {
    local project_path="$1"
    print_status "info" "Copying bash-cli skeleton files..."

    export PROJECT_NAME PROJECT_DESCRIPTION
    envsubst '${PROJECT_NAME}' \
        < "$SKELETON_TEMPLATE_ROOT/bin/cli.sh" \
        > "$project_path/bin/$PROJECT_NAME"
    chmod +x "$project_path/bin/$PROJECT_NAME"

    envsubst '${PROJECT_NAME}' \
        < "$SKELETON_TEMPLATE_ROOT/tests/cli.bats" \
        > "$project_path/tests/cli.bats"

    envsubst '${PROJECT_NAME}' \
        < "$SKELETON_TEMPLATE_ROOT/Makefile" \
        > "$project_path/Makefile"

    envsubst '${PROJECT_NAME}' \
        < "$SKELETON_TEMPLATE_ROOT/CLAUDE.md" \
        > "$project_path/CLAUDE.md"

    envsubst '${PROJECT_NAME} ${PROJECT_DESCRIPTION}' \
        < "$SKELETON_TEMPLATE_ROOT/README.md" \
        > "$project_path/README.md"

    envsubst '${PROJECT_NAME}' \
        < "$SKELETON_TEMPLATE_ROOT/.github/workflows/release.yml" \
        > "$project_path/.github/workflows/release.yml"

    cp "$SKELETON_TEMPLATE_ROOT/.github/workflows/ci.yml" "$project_path/.github/workflows/ci.yml"
    cp "$SKELETON_TEMPLATE_ROOT/.pre-commit-config.yaml" "$project_path/.pre-commit-config.yaml"
    cp "$SKELETON_TEMPLATE_ROOT/.gitignore" "$project_path/.gitignore"

    # Shared print_status/resolve_default_branch implementation (templates/common) —
    # one implementation across every skeleton, bash-cli included (blueprintx CLAUDE.md).
    cp "$SHARED_TEMPLATE_ROOT/bin/lib/common.sh" "$project_path/lib/common.sh"

    print_status "success" "Skeleton files copied"
}

copy_common_templates() {
    local project_path="$1"
    print_status "info" "Applying common templates..."

    cp "$SHARED_TEMPLATE_ROOT/.editorconfig" "$project_path/.editorconfig"
    cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "$project_path/.gitattributes"
    cp "$SHARED_TEMPLATE_ROOT/.github/CLAUDE.md" "$project_path/.github/CLAUDE.md"
    cp "$SHARED_TEMPLATE_ROOT/.github/CODEOWNERS" "$project_path/.github/CODEOWNERS"
    cp "$SHARED_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
    envsubst < "$LICENSES_TEMPLATE_ROOT/${LICENSE_CHOICE}" > "$project_path/LICENSE"

    print_status "success" "Common templates applied"
}

apply_branch_protection() {
    local branch="main"
    local repo="${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}"

    if ! command -v gh >/dev/null 2>&1 || ! gh auth status >/dev/null 2>&1; then
        print_status "info" "gh CLI unavailable/unauthenticated; skipping main branch protection."
        return
    fi
    if ! gh repo view "$repo" >/dev/null 2>&1; then
        print_status "warning" "GitHub repo $repo not reachable; skipping branch protection."
        return
    fi

    read -r -p "$(prompt_main "Protect branch '$branch' on GitHub now? [y/N]: ")" protect_ans || true
    case "$protect_ans" in
        y | Y)
            local reviews_json='"required_pull_request_reviews": null,'
            if gh api --method PUT \
                -H "Accept: application/vnd.github+json" \
                "/repos/$repo/branches/$branch/protection" \
                --input - <<EOF
{
  "required_status_checks": { "strict": true, "contexts": [] },
  "enforce_admins": true,
  $reviews_json
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": true
}
EOF
            then
                print_status "success" "Branch '$branch' protected on GitHub."
            else
                print_status "warning" "Failed to protect branch '$branch'; adjust settings manually in GitHub."
            fi
            ;;
        *) print_status "info" "Skipped branch protection" ;;
    esac
}

initialize_git_repo() {
    local project_path="$1"
    if ! command -v git >/dev/null 2>&1; then
        print_status "warning" "git not found — skipping repo initialization"
        return
    fi
    if git -C "$project_path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        print_status "info" "Git repo already initialized; skipping"
        return
    fi
    (
        cd "$project_path" || exit 1
        git init -q -b main || true
        git add . || true
        git commit -q -m "feat: first commit" >/dev/null 2>&1 || true
    )
    print_status "success" "Initialized git repo (branch main) with first commit"
}

prompt_git_remote_setup() {
    if scaffold_prompt_git_remote_setup "$1"; then
        apply_branch_protection "$1"
    fi
}

apply_offline_mode() {
    local project_path="$1"
    print_status "info" "No GitHub remote connected — switching to offline mode"
    # GitHub-only assets (Actions workflows, CODEOWNERS, PR template) are not useful
    # without a GitHub remote; remove them and ship the offline git-diff workflow.
    rm -rf "$project_path/.github"
    mkdir -p "$project_path/bin/lib"
    cp "$SHARED_TEMPLATE_ROOT/bin/lib/common.sh" "$project_path/bin/lib/common.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_diff_export.sh" "$project_path/bin/git_diff_export.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_diff_apply.sh" "$project_path/bin/git_diff_apply.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_diff_check.sh" "$project_path/bin/git_diff_check.sh"
    chmod +x "$project_path/bin/git_diff_export.sh" \
        "$project_path/bin/git_diff_apply.sh" \
        "$project_path/bin/git_diff_check.sh"
    mkdir -p "$project_path/git_diffs"
    touch "$project_path/git_diffs/.keep"
    print_status "success" "git-diff workflow enabled (bin/git_diff_export.sh | git_diff_check.sh | git_diff_apply.sh)"
    commit_offline_artifacts "$project_path"
}

commit_offline_artifacts() {
    local project_path="$1"
    git -C "$project_path" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
    git -C "$project_path" add -A
    git -C "$project_path" commit -q --no-verify -m "chore: enable offline git workflow" || true
}

main() {
    PROJECT_PATH="$PROJECT_ROOT/$PROJECT_NAME"

    print_section "Bash CLI (bash-cli) scaffold"
    print_status "config" "Target: $PROJECT_PATH"

    validate_inputs
    resolve_github_username
    create_directory_structure "$PROJECT_PATH"
    copy_skeleton_files "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    scaffold_purge_caches "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    if [ "$SCAFFOLD_REMOTE_VERIFIED" != "1" ] \
        || ! git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        apply_offline_mode "$PROJECT_PATH"
    fi

    print_status "success" "bash-cli scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
    print_status "info" "Run 'make lint && make test' to get started"
}

main
