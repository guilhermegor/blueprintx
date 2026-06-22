#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"

PROJECT_ROOT="$1"
PROJECT_NAME="$2"
PROJECT_DESCRIPTION="${3:-}"
PROJECT_VERSION="${4:-0.0.1}"
LICENSE_CHOICE="${LICENSE_CHOICE:-MIT}"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMMON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/python-common"
# Language-agnostic assets shared by every skeleton (CODEOWNERS, PR template)
SHARED_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/common"
LICENSES_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/licenses"
DEFAULT_GITHUB_USERNAME="${GITHUB_USERNAME:-your-github-username}"
PROJECT_DISPLAY_NAME=""

# ============================================================================
# FUNCTIONS
# ============================================================================

validate_inputs() {
    if [ -z "$PROJECT_ROOT" ] || [ -z "$PROJECT_NAME" ]; then
        exit_error "Usage: $0 <project_root_dir> <project_name>"
    fi
    print_status "success" "Input validation passed"
}

format_display_name() {
    local raw="$1"
    local part formatted=""
    raw=${raw//[-_]/ }
    for part in $raw; do
        part=${part,,}
        part=${part^}
        formatted+="${formatted:+ }${part}"
    done
    echo "$formatted"
}

resolve_github_username() {
    # 1) GH_USERNAME env override
    if [ -n "$GITHUB_USERNAME" ]; then
        print_status "config" "GitHub username (env): $GITHUB_USERNAME"
        return
    fi

    # 2) gh CLI (authenticated)
    if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
        local gh_user
        gh_user=$(gh api user -q .login 2>/dev/null || true)
        if [ -n "$gh_user" ]; then
            GITHUB_USERNAME="$gh_user"
            print_status "config" "GitHub username (gh): $GITHUB_USERNAME"
            return
        fi
    fi

    # 3) Fallback prompt
    local input
    read -r -p "GitHub username (default: $DEFAULT_GITHUB_USERNAME): " input || true
    if [ -n "$input" ]; then
        GITHUB_USERNAME="$input"
    else
        GITHUB_USERNAME="$DEFAULT_GITHUB_USERNAME"
    fi
    print_status "config" "GitHub username (prompt): $GITHUB_USERNAME"
}

create_directory_structure() {
    local project_path="$1"

    print_status "info" "Creating directory structure..."

    mkdir -p "$project_path"/src/"$PROJECT_NAME"
    mkdir -p "$project_path"/tests/integration
    mkdir -p "$project_path"/tests/performance
    mkdir -p "$project_path"/tests/unit
    mkdir -p "$project_path"/container
    mkdir -p "$project_path"/bin
    mkdir -p "$project_path"/docs
    mkdir -p "$project_path"/assets
    mkdir -p "$project_path"/.github/workflows
    mkdir -p "$project_path"/.vscode

    print_status "success" "Directory structure created"
}

create_python_files() {
    local project_path="$1"

    print_status "info" "Creating Python files..."

    printf '"""%s package."""\n' "$PROJECT_NAME" > "$project_path/src/$PROJECT_NAME/__init__.py"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/main.py" "$project_path/src/$PROJECT_NAME/main.py"

    # Create test file with project name substitution. Tab-indented and fully
    # annotated/docstringed so a freshly scaffolded project passes `make lint`.
    mkdir -p "$project_path/tests/unit"
    sed "s/\${PROJECT_NAME}/$PROJECT_NAME/g" << 'EOF' > "$project_path/tests/unit/test_main.py"
"""Unit tests for the library entry point."""

import pytest

from ${PROJECT_NAME}.main import main


def test_main(capsys: pytest.CaptureFixture[str]) -> None:
	"""The entry point prints the placeholder greeting to stdout."""
	main()
	captured = capsys.readouterr()
	assert "Hello from lib-minimal!" in captured.out
EOF

    print_status "success" "Python files created"
}

# Runtime type-checking engine (stdlib-only) — single source in
# python-common/optional/typing. lib-minimal vendors it as utils/typing (the same
# layout the MVC tiers use) and rewrites the canonical chassis.typing prefix.
copy_typing_chassis() {
    local project_path="$1"
    mkdir -p "$project_path/src/utils/typing"
    cp "$COMMON_TEMPLATE_ROOT/src/utils/__init__.py" "$project_path/src/utils/__init__.py"
    cp -r "$COMMON_TEMPLATE_ROOT/optional/typing/." "$project_path/src/utils/typing"
    grep -rl "chassis.typing" "$project_path/src/utils/typing" \
        | xargs -r sed -i "s|chassis\.typing|utils.typing|g"
    print_status "success" "Runtime type-checking engine (utils/typing) applied"
}

copy_templates() {
    local project_path="$1"

    print_status "info" "Copying templates..."

    cp "$COMMON_TEMPLATE_ROOT/.gitignore" "$project_path/.gitignore"
    cp "$COMMON_TEMPLATE_ROOT/.python-version" "$project_path/.python-version"
    cp "$SHARED_TEMPLATE_ROOT/.editorconfig" "$project_path/.editorconfig"
    cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "$project_path/.gitattributes"
    PROJECT_DISPLAY_NAME="${PROJECT_DISPLAY_NAME:-$(format_display_name "$PROJECT_NAME")}"
    PROJECT_DISPLAY_NAME="$PROJECT_DISPLAY_NAME" envsubst '${PROJECT_DISPLAY_NAME}' < "$COMMON_TEMPLATE_ROOT/README.md" > "$project_path/README.md"
    cp "$COMMON_TEMPLATE_ROOT/assets/logo_lorem_ipsum.png" "$project_path/assets/logo_lorem_ipsum.png"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.env.example" "$project_path/.env"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.env.example" "$project_path/.env.example"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/CLAUDE.md" "$project_path/CLAUDE.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.coveragerc" "$project_path/.coveragerc"

    print_status "success" "Templates copied and configured"
}

copy_common_templates() {
    local project_path="$1"

    print_status "info" "Applying common Python templates..."

    HOMEPAGE="${HOMEPAGE:-https://example.com/${PROJECT_NAME}}"
    REPOSITORY="${REPOSITORY:-https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}}"
    BUG_REPORTS_URL="${BUG_REPORTS_URL:-${REPOSITORY}/issues}"
    SOURCE_URL="${SOURCE_URL:-${REPOSITORY}}"

    COPYRIGHT_YEAR="$(date +%Y)"
    AUTHOR_NAME="${GITHUB_USERNAME}"
    PROJECT_LICENSE="${LICENSE_CHOICE}"

    export PROJECT_NAME PROJECT_VERSION PROJECT_DESCRIPTION \
        PROJECT_DISPLAY_NAME HOMEPAGE REPOSITORY BUG_REPORTS_URL SOURCE_URL GITHUB_USERNAME \
        COPYRIGHT_YEAR AUTHOR_NAME PROJECT_LICENSE
    envsubst < "$BLUEPRINTX_ROOT/templates/lib-minimal/pyproject.toml" > "$project_path/pyproject.toml"

    cp "$COMMON_TEMPLATE_ROOT/.pre-commit-config.yaml" "$project_path/.pre-commit-config.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.pydocstyle" "$project_path/.pydocstyle"
    cp "$COMMON_TEMPLATE_ROOT/requirements.txt" "$project_path/requirements.txt"
    cp "$COMMON_TEMPLATE_ROOT/.codespellrc" "$project_path/.codespellrc"
    cp "$COMMON_TEMPLATE_ROOT/CONTRIBUTING.md" "$project_path/CONTRIBUTING.md"
    envsubst < "$LICENSES_TEMPLATE_ROOT/${LICENSE_CHOICE}" > "$project_path/LICENSE"
    cp "$COMMON_TEMPLATE_ROOT/Makefile" "$project_path/Makefile"
    cp "$COMMON_TEMPLATE_ROOT/pytest.ini" "$project_path/pytest.ini"
    cp "$COMMON_TEMPLATE_ROOT/ruff.toml" "$project_path/ruff.toml"
    cp "$COMMON_TEMPLATE_ROOT/poetry.toml" "$project_path/poetry.toml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/tests.yaml" "$project_path/.github/workflows/tests.yaml"
    cp "$SHARED_TEMPLATE_ROOT/.github/CODEOWNERS" "$project_path/.github/CODEOWNERS"
    cp "$SHARED_TEMPLATE_ROOT/.github/CLAUDE.md" "$project_path/.github/CLAUDE.md"
    cp "$SHARED_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
    cp "$COMMON_TEMPLATE_ROOT/tasks.sh" "$project_path/tasks.sh"
    cp "$COMMON_TEMPLATE_ROOT/.gitlint" "$project_path/.gitlint"
    cp -r "$COMMON_TEMPLATE_ROOT/bin/." "$project_path/bin"
    cp "$SHARED_TEMPLATE_ROOT/bin/export_repo_content.sh" "$project_path/bin/export_repo_content.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/ship.sh" "$project_path/bin/ship.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/commit.sh" "$project_path/bin/commit.sh"
    chmod +x "$project_path/bin/export_repo_content.sh" "$project_path/bin/ship.sh" "$project_path/bin/commit.sh"
    mkdir -p "$project_path/dist"
    cp "$SHARED_TEMPLATE_ROOT/dist/.keep" "$project_path/dist/.keep"
    # VS Code: shared settings (python-common) + slim per-tier tasks (no db tasks).
    mkdir -p "$project_path/.vscode"
    cp "$COMMON_TEMPLATE_ROOT/.vscode/settings.json" "$project_path/.vscode/settings.json"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.vscode/tasks.json" "$project_path/.vscode/tasks.json"

    print_status "success" "Common templates applied"
}

copy_mkdocs_templates() {
    local project_path="$1"

    print_status "info" "Copying MkDocs templates..."

    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' \
        < "$BLUEPRINTX_ROOT/templates/lib-minimal/mkdocs.yml" \
        > "$project_path/mkdocs.yml"
    envsubst '${PROJECT_DISPLAY_NAME}' \
        < "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/index.md" \
        > "$project_path/docs/index.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/usage.md" \
        "$project_path/docs/usage.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/api.md" \
        "$project_path/docs/api.md"
    # Non-published docs/ authoring guide + the excluded backlog folder.
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/CLAUDE.md" \
        "$project_path/docs/CLAUDE.md"
    mkdir -p "$project_path/docs/backlog"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/backlog/.keep" \
        "$project_path/docs/backlog/.keep"

    print_status "success" "MkDocs templates copied"
}

apply_branch_protection() {
    local branch="main"
    local repo="${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}"

    if ! command -v gh >/dev/null 2>&1; then
        print_status "info" "gh CLI not found; skipping main branch protection."
        return
    fi

    if ! gh auth status >/dev/null 2>&1; then
        print_status "warn" "gh not authenticated; skipping main branch protection."
        return
    fi

    if ! gh repo view "$repo" >/dev/null 2>&1; then
        print_status "warn" "GitHub repo $repo not reachable; skipping branch protection."
        return
    fi

    read -r -p "Protect branch '$branch' on GitHub now? [y/N]: " protect_ans || true
    case "$protect_ans" in
        y|Y)
            # A solo maintainer cannot satisfy a required-approving-review
            # rule — GitHub forbids self-approval, so the first PR's merge
            # would be permanently blocked. Ask whether human reviewers will
            # gate merges, and build the protection payload accordingly.
            local reviews_json
            read -r -p "Will human reviewers gate merges to '$branch'? [y/N]: " reviews_ans || true
            case "$reviews_ans" in
                y|Y)
                    reviews_json='"required_pull_request_reviews": { "dismiss_stale_reviews": true, "require_code_owner_reviews": false, "required_approving_review_count": 1 },'
                    ;;
                *)
                    reviews_json='"required_pull_request_reviews": null,'
                    ;;
            esac
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
                print_status "warn" "Failed to protect branch '$branch'; adjust settings manually in GitHub."
            fi
            ;;
        *) print_status "info" "Skipped branch protection";;
    esac
}

# Always initialise a local git repo with a first commit, independent of any
# remote setup, so every scaffold is a git repo even in non-interactive (--dev)
# runs. Skips gracefully when git is unavailable or the repo already exists.
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
    local project_path="$1"

    print_status "info" "Optional: add a remote origin / create a GitHub repo (the local repo is already initialized)"
    read -r -p "Add remote origin and (optionally) create the GitHub repo now? [y/N]: " answer || true

    case "$answer" in
        y|Y)
            push_done=0
            (
                cd "$project_path"
                if git remote get-url origin >/dev/null 2>&1; then
                    print_status "warn" "Remote 'origin' already exists; skipped add"
                else
                    git remote add origin "git@github.com:${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}.git" || true
                fi
            )
            if command -v gh >/dev/null 2>&1; then
                read -r -p "Create GitHub repo ${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME} and push now? [y/N]: " create_ans || true
                case "$create_ans" in
                    y|Y)
                        local vis_choice vis_flag repo_slug
                        read -r -p "Visibility [1] Public (default)  [2] Private: " vis_choice || true
                        vis_flag="--public"
                        [ "$vis_choice" = "2" ] && vis_flag="--private"
                        repo_slug="${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}"
                        (
                            cd "$project_path"
                            if gh repo create "$repo_slug" --source . --remote origin --push "$vis_flag"; then
                                push_done=1
                                gh repo edit "$repo_slug" --default-branch main >/dev/null 2>&1 || true
                                print_status "success" "Repository created and pushed via gh."
                            else
                                print_status "warn" "gh repo create failed; check authentication or if the repo already exists."
                                print_status "info" "Manual fallback: create the repo on GitHub and run 'git push -u origin main'."
                            fi
                        )
                        ;;
                    *) print_status "info" "Skipped GitHub repo creation/push";;
                esac
            else
                print_status "info" "gh CLI not found; to publish run: git push -u origin main (ensure repo exists on GitHub)."
            fi
            if [ "$push_done" -eq 0 ]; then
                if git -C "$project_path" remote get-url origin >/dev/null 2>&1; then
                    if git -C "$project_path" push -u origin main >/dev/null 2>&1; then
                        print_status "success" "Pushed to origin/main."
                    else
                        print_status "warn" "Push to origin/main failed; create the repo on GitHub and retry 'git push -u origin main'."
                    fi
                else
                    print_status "warn" "Remote 'origin' missing; cannot push. Create repo and run 'git push -u origin main'."
                fi
            fi
            print_status "success" "Git repo initialized."
            ;;
        *)
            print_status "info" "Skipped remote setup"
            ;;
    esac

    apply_branch_protection "$project_path"
}

apply_offline_mode() {
    local project_path="$1"

    print_status "info" "No GitHub remote connected — switching to offline mode"
    # GitHub-only assets (Actions workflows, CODEOWNERS, PR template) are not useful
    # without a GitHub remote; remove them and ship the offline git-diff workflow instead.
    rm -rf "$project_path/.github"
    print_status "info" "Removed .github (GitHub-only assets)"
    mkdir -p "$project_path/bin/lib"
    cp "$SHARED_TEMPLATE_ROOT/bin/lib/common.sh" "$project_path/bin/lib/common.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_diff_export.sh" "$project_path/bin/git_diff_export.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_diff_apply.sh" "$project_path/bin/git_diff_apply.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_diff_check.sh" "$project_path/bin/git_diff_check.sh"
    # Local git workflow + branch guard — substitute for GitHub's branch/PR flow.
    cp "$SHARED_TEMPLATE_ROOT/bin/new_branch.sh" "$project_path/bin/new_branch.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_merge_to_main.sh" "$project_path/bin/git_merge_to_main.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/protect_branch.sh" "$project_path/bin/protect_branch.sh"
    chmod +x "$project_path/bin/git_diff_export.sh" \
        "$project_path/bin/git_diff_apply.sh" \
        "$project_path/bin/git_diff_check.sh" \
        "$project_path/bin/new_branch.sh" \
        "$project_path/bin/git_merge_to_main.sh" \
        "$project_path/bin/protect_branch.sh"
    mkdir -p "$project_path/make"
    cp "$SHARED_TEMPLATE_ROOT/make/offline.mk" "$project_path/make/offline.mk"
    mkdir -p "$project_path/git_diffs"
    touch "$project_path/git_diffs/.keep"
    # Swap the stock no-commit-to-branch hook for the friendly local protect-branch
    # guard that points at `make new_branch` (offline has no server-side protection).
    swap_protect_branch_hook "$project_path"
    commit_offline_artifacts "$project_path"
    print_status "success" "Offline workflow enabled (new_branch | git_merge_to_main | git_diff_* | protect-branch)"
}

# The scaffold's first commit runs before the online/offline branch, so the
# offline artifacts (local git workflow, swapped pre-commit hook, removed
# .github) would otherwise be left uncommitted. Commit them so a freshly
# scaffolded offline project starts with a clean working tree. --no-verify
# bypasses the just-installed protect-branch hook (HEAD is the default branch).
commit_offline_artifacts() {
    local project_path="$1"
    git -C "$project_path" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
    git -C "$project_path" add -A
    git -C "$project_path" commit -q --no-verify -m "chore: enable offline git workflow" || true
}

# Replace the stock pre-commit `no-commit-to-branch` hook with a local hook that
# runs bin/protect_branch.sh first (fail-fast, friendly message). Offline only.
swap_protect_branch_hook() {
    local project_path="$1"
    local pc="$project_path/.pre-commit-config.yaml"
    [ -f "$pc" ] || return 0
    python3 - "$pc" <<'PY'
import re
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    text = fh.read()

# Drop the stock no-commit-to-branch hook (its id line + the following --branch args).
text = re.sub(
    r"\n      - id: no-commit-to-branch\n(?:        args:\n          - --branch=\S+\n)?",
    "\n",
    text,
)

# Insert a local protect-branch hook as the FIRST entry of the `repos:` list so it
# fails fast before the slow test/coverage hooks.
local_hook = (
    "repos:\n"
    "  - repo: local\n"
    "    hooks:\n"
    "      - id: protect-branch\n"
    "        name: block direct commits to main/master\n"
    "        entry: bash bin/protect_branch.sh\n"
    "        language: system\n"
    "        always_run: true\n"
    "        pass_filenames: false\n"
)
text = text.replace("repos:\n", local_hook, 1)

with open(path, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
    print_status "success" "Swapped no-commit-to-branch → local protect-branch hook"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    PROJECT_PATH="$PROJECT_ROOT/$PROJECT_NAME"

    print_section "Python lib-minimal scaffold"
    print_status "config" "Target: $PROJECT_PATH"

    validate_inputs
    resolve_github_username
    PROJECT_DISPLAY_NAME="$(format_display_name "$PROJECT_NAME")"
    create_directory_structure "$PROJECT_PATH"
    create_python_files "$PROJECT_PATH"
    copy_typing_chassis "$PROJECT_PATH"
    copy_templates "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    copy_mkdocs_templates "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    # When the project is not connected to a GitHub remote (no upstream tracking
    # branch after setup), switch to offline mode: drop GitHub-only assets and
    # ship the git-diff sync workflow instead.
    if ! git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        apply_offline_mode "$PROJECT_PATH"
    fi

    print_status "success" "Lib-minimal scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
}

main
