#!/usr/bin/env bash
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
DEFAULT_OS="chromeos-flex"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SKELETON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/etcher-chromeos"
SHARED_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/common"
LICENSES_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/licenses"
DEFAULT_GITHUB_USERNAME="${GITHUB_USERNAME:-your-github-username}"


validate_inputs() {
    if [ -z "$PROJECT_ROOT" ] || [ -z "$PROJECT_NAME" ]; then
        exit_error "Usage: $0 <project_root_dir> <project_name>"
    fi
    if ! is_valid_project_name "$PROJECT_NAME"; then
        exit_error "Invalid project name '$PROJECT_NAME'. Use a letter or underscore first, then letters, digits, '-' or '_'."
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
    prompt_read input "$(prompt_main "GitHub username (default: $DEFAULT_GITHUB_USERNAME): ")"
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

copy_skeleton_files() {
    local project_path="$1"
    print_status "info" "Copying etcher-chromeos skeleton files..."

    export PROJECT_NAME PROJECT_DESCRIPTION DEFAULT_OS
    envsubst '${PROJECT_NAME} ${DEFAULT_OS}' \
        < "$SKELETON_TEMPLATE_ROOT/bin/cli.sh" \
        > "$project_path/bin/$PROJECT_NAME"
    chmod +x "$project_path/bin/$PROJECT_NAME"
    cp "$SKELETON_TEMPLATE_ROOT/bin/fetch_tools.sh" "$project_path/bin/fetch_tools.sh"
    chmod +x "$project_path/bin/fetch_tools.sh"
    cp "$SKELETON_TEMPLATE_ROOT"/lib/*.sh "$project_path/lib/"

    envsubst '${PROJECT_NAME}' \
        < "$SKELETON_TEMPLATE_ROOT/tests/cli.bats" \
        > "$project_path/tests/cli.bats"
    cp -r "$SKELETON_TEMPLATE_ROOT/tests/fixtures" "$project_path/tests/fixtures"

    envsubst '${PROJECT_NAME}' \
        < "$SKELETON_TEMPLATE_ROOT/Makefile" \
        > "$project_path/Makefile"

    envsubst '${PROJECT_NAME}' \
        < "$SKELETON_TEMPLATE_ROOT/AGENTS.md" \
        > "$project_path/AGENTS.md"
    cp "$SKELETON_TEMPLATE_ROOT/CLAUDE.md" "$project_path/CLAUDE.md"
    cp "$SKELETON_TEMPLATE_ROOT/Dockerfile" "$project_path/Dockerfile"

    envsubst '${PROJECT_NAME} ${PROJECT_DESCRIPTION}' \
        < "$SKELETON_TEMPLATE_ROOT/README.md" \
        > "$project_path/README.md"

    envsubst '${PROJECT_NAME}' \
        < "$SKELETON_TEMPLATE_ROOT/.github/workflows/release.yml" \
        > "$project_path/.github/workflows/release.yml"

    cp "$SKELETON_TEMPLATE_ROOT/.github/workflows/ci.yml" "$project_path/.github/workflows/ci.yml"
    cp "$SKELETON_TEMPLATE_ROOT/.pre-commit-config.yaml" "$project_path/.pre-commit-config.yaml"
    cp "$SKELETON_TEMPLATE_ROOT/.gitignore" "$project_path/.gitignore"

    cp "$SHARED_TEMPLATE_ROOT/bin/lib/common.sh" "$project_path/lib/common.sh"

    print_status "success" "Skeleton files copied"
}

prompt_default_os() {
    local str_answer
    prompt_read str_answer "$(prompt_main "Default OS to flash [chromeos-flex/fydeos] (default: chromeos-flex): ")"
    case "$str_answer" in
        fydeos) DEFAULT_OS="fydeos" ;;
        "" | chromeos-flex) DEFAULT_OS="chromeos-flex" ;;
        *) exit_error "Unknown OS '$str_answer'. Use chromeos-flex or fydeos." ;;
    esac
    print_status "config" "Default OS: $DEFAULT_OS"
}

copy_common_templates() {
    local project_path="$1"
    print_status "info" "Applying common templates..."

    cp "$SHARED_TEMPLATE_ROOT/.editorconfig" "$project_path/.editorconfig"
    cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "$project_path/.gitattributes"
    cp "$SHARED_TEMPLATE_ROOT/.coderabbit.yaml" "$project_path/.coderabbit.yaml"
    mkdir -p "$project_path/.greptile" && cp "$SHARED_TEMPLATE_ROOT/.greptile/config.json" "$SKELETON_TEMPLATE_ROOT/.greptile/"* "$project_path/.greptile/"
    cp "$SHARED_TEMPLATE_ROOT/PRINCIPLES.md" "$project_path/PRINCIPLES.md"
    cp "$SHARED_TEMPLATE_ROOT/.github/CLAUDE.md" "$project_path/.github/CLAUDE.md"
    GITHUB_USERNAME="$GITHUB_USERNAME" envsubst '${GITHUB_USERNAME}' < "$SHARED_TEMPLATE_ROOT/.github/CODEOWNERS" > "$project_path/.github/CODEOWNERS"
    cp "$SHARED_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
    mkdir -p "$project_path/.github/ISSUE_TEMPLATE" && cp "$SHARED_TEMPLATE_ROOT/.github/ISSUE_TEMPLATE/feature_or_fix.md" "$project_path/.github/ISSUE_TEMPLATE/feature_or_fix.md"
    cp "$BLUEPRINTX_ROOT/templates/ts-common/.github/.review-bots.yaml" "$project_path/.github/.review-bots.yaml"
    copy_repo_policy_workflows "$project_path"
    copy_repo_rules_provisioner "$project_path" "$SKELETON_TEMPLATE_ROOT/bin/required-checks.txt"
    envsubst < "$LICENSES_TEMPLATE_ROOT/${LICENSE_CHOICE}" > "$project_path/LICENSE"
    cp -r "$SHARED_TEMPLATE_ROOT/.specs" "$project_path/.specs"

    print_status "success" "Common templates applied"
}

apply_branch_protection() {
    local project_path="$1"
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

    protect_ans=""
    prompt_read protect_ans "$(prompt_main "Protect branch '$branch' on GitHub now? [y/N]: ")"
    case "$protect_ans" in
        y | Y)
            local reviews_approvals=0
            (cd "$project_path" && RULESET_APPROVALS="$reviews_approvals" bash bin/enable_repo_rules.sh)
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
    if ! (
        cd "$project_path" || exit 1
        git init -q -b main &&
            git add . &&
            git commit -q -m "feat: first commit"
    ); then
        exit_error "Could not create the initial commit in '$project_path'. Set git user.name and user.email, then re-run."
    fi
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
    rm -rf "$project_path/.github"
    remove_repo_policy_scripts "$project_path"
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

    print_section "Etcher ChromeOS flasher (etcher-chromeos) scaffold"
    print_status "config" "Target: $PROJECT_PATH"

    validate_inputs
    resolve_github_username
    prompt_default_os
    scaffold_prompt_review_bot_roster
    create_directory_structure "$PROJECT_PATH"
    copy_skeleton_files "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    scaffold_prune_review_bot_roster "$PROJECT_PATH"
    scaffold_purge_caches "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    if [ "$SCAFFOLD_REMOTE_VERIFIED" != "1" ] \
        || ! git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        apply_offline_mode "$PROJECT_PATH"
    fi

    print_status "success" "etcher-chromeos scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
    print_status "info" "Run 'make lint && make test && make tools' to get started"
}

main
