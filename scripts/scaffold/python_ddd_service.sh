#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/logging.sh"

PROJECT_ROOT="$1"
PROJECT_NAME="$2"
PROJECT_DESCRIPTION="${3:-}"
PROJECT_VERSION="${4:-0.0.1}"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMMON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/python-common"
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
    
    mkdir -p "$project_path"/src/core/domain
    mkdir -p "$project_path"/src/core/infrastructure
    mkdir -p "$project_path"/src/core/application
    mkdir -p "$project_path"/src/modules
    mkdir -p "$project_path"/src/utils
    mkdir -p "$project_path"/src/config
    mkdir -p "$project_path"/tests/integration
    mkdir -p "$project_path"/tests/performance
    mkdir -p "$project_path"/tests/unit
    mkdir -p "$project_path"/container
    mkdir -p "$project_path"/scripts
    mkdir -p "$project_path"/data
    mkdir -p "$project_path"/public
    mkdir -p "$project_path"/docs
    mkdir -p "$project_path"/.github/workflows
    mkdir -p "$project_path"/.vscode

    # Ensure empty dirs are tracked by git
    touch "$project_path"/tests/integration/.keep
    touch "$project_path"/tests/performance/.keep
    touch "$project_path"/tests/unit/.keep
    touch "$project_path"/container/.keep
    touch "$project_path"/scripts/.keep
    touch "$project_path"/data/.keep
    touch "$project_path"/docs/.keep
    
    print_status "success" "Directory structure created"
}

create_python_files() {
    local project_path="$1"
    
    print_status "info" "Creating Python files..."
    
    touch "$project_path"/src/__init__.py
    touch "$project_path"/src/core/__init__.py
    touch "$project_path"/src/modules/__init__.py
    touch "$project_path"/src/utils/__init__.py
    touch "$project_path"/src/config/__init__.py
    mkdir -p "$project_path"/src/core/infrastructure/database
    cp -r "$BLUEPRINTX_ROOT/templates/ddd-service/src/." "$project_path/src"
    
    print_status "success" "Python files created"
}

copy_templates() {
    local project_path="$1"
    
    print_status "info" "Copying templates..."
    
    cp "$COMMON_TEMPLATE_ROOT/.gitignore" "$project_path/.gitignore"
    cp "$COMMON_TEMPLATE_ROOT/.python-version" "$project_path/.python-version"
    PROJECT_DISPLAY_NAME="${PROJECT_DISPLAY_NAME:-$(format_display_name "$PROJECT_NAME")}" 
    PROJECT_DISPLAY_NAME="$PROJECT_DISPLAY_NAME" envsubst '${PROJECT_DISPLAY_NAME}' < "$COMMON_TEMPLATE_ROOT/README.md" > "$project_path/README.md"
    cp "$COMMON_TEMPLATE_ROOT/public/logo_lorem_ipsum.png" "$project_path/public/logo_lorem_ipsum.png"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service/.env.example" "$project_path/.env"
    
    print_status "success" "Templates copied and configured"
}

copy_common_templates() {
    local project_path="$1"

    print_status "info" "Applying common Python templates..."

    HOMEPAGE="${HOMEPAGE:-https://example.com/${PROJECT_NAME}}"
    REPOSITORY="${REPOSITORY:-https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}}"
    BUG_REPORTS_URL="${BUG_REPORTS_URL:-${REPOSITORY}/issues}"
    SOURCE_URL="${SOURCE_URL:-${REPOSITORY}}"

    export PROJECT_NAME PROJECT_VERSION PROJECT_DESCRIPTION \
        PROJECT_DISPLAY_NAME HOMEPAGE REPOSITORY BUG_REPORTS_URL SOURCE_URL GITHUB_USERNAME
    envsubst < "$COMMON_TEMPLATE_ROOT/pyproject.toml" > "$project_path/pyproject.toml"
    
    cp "$COMMON_TEMPLATE_ROOT/.pre-commit-config.yaml" "$project_path/.pre-commit-config.yaml"
    cp "$COMMON_TEMPLATE_ROOT/requirements.txt" "$project_path/requirements.txt"
    cp "$COMMON_TEMPLATE_ROOT/.vscode/settings.json" "$project_path/.vscode/settings.json"
    cp "$COMMON_TEMPLATE_ROOT/.vscode/extensions.txt" "$project_path/.vscode/extensions.txt"
    cp "$COMMON_TEMPLATE_ROOT/.codespellrc" "$project_path/.codespellrc"
    cp "$COMMON_TEMPLATE_ROOT/CONTRIBUTING.md" "$project_path/CONTRIBUTING.md"
    cp "$COMMON_TEMPLATE_ROOT/LICENSE" "$project_path/LICENSE"
    cp "$COMMON_TEMPLATE_ROOT/Makefile" "$project_path/Makefile"
    cp "$COMMON_TEMPLATE_ROOT/pytest.ini" "$project_path/pytest.ini"
    cp "$COMMON_TEMPLATE_ROOT/ruff.toml" "$project_path/ruff.toml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/tests.yaml" "$project_path/.github/workflows/tests.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/CODEOWNERS" "$project_path/.github/CODEOWNERS"
    cp "$COMMON_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
    cp -r "$COMMON_TEMPLATE_ROOT/prompts" "$project_path/prompts"
    cp -r "$COMMON_TEMPLATE_ROOT/scripts/." "$project_path/scripts/"
    cp "$COMMON_TEMPLATE_ROOT/run.sh" "$project_path/run.sh"
    
    print_status "success" "Common templates applied"
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
            if gh api --method PUT \
                -H "Accept: application/vnd.github+json" \
                "/repos/$repo/branches/$branch/protection" \
                --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": []
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1
  },
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

prompt_git_remote_setup() {
    local project_path="$1"

    print_status "info" "Optional: initialize git and add remote"
    read -r -p "Initialize git repo and add remote origin? [y/N]: " answer || true

    case "$answer" in
        y|Y)
            push_done=0
            (
                cd "$project_path"
                git init -q || true
                git checkout -b main 2>/dev/null || git branch -M main || true
                git add . || true
                git commit -m "feat: first commit" >/dev/null 2>&1 || true
                if git remote get-url origin >/dev/null 2>&1; then
                    print_status "warn" "Remote 'origin' already exists; skipped add"
                else
                    git remote add origin "git@github.com:${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}.git" || true
                fi
            )
            # Offer to create GitHub repo via gh and push if available
            if command -v gh >/dev/null 2>&1; then
                read -r -p "Create GitHub repo ${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME} and push now? [y/N]: " create_ans || true
                case "$create_ans" in
                    y|Y)
                        (
                            cd "$project_path"
                            if gh repo create "${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}" --source . --remote origin --public --push; then
                                push_done=1
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
            print_status "info" "Skipped git initialization"
            ;;
    esac

    apply_branch_protection "$project_path"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    PROJECT_PATH="$PROJECT_ROOT/$PROJECT_NAME"
    
    print_section "Python ddd-service scaffold"
    print_status "config" "Target: $PROJECT_PATH"
    
    validate_inputs
    resolve_github_username
    PROJECT_DISPLAY_NAME="$(format_display_name "$PROJECT_NAME")"
    create_directory_structure "$PROJECT_PATH"
    create_python_files "$PROJECT_PATH"
    copy_templates "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"
    
    print_status "success" "Hex-service scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
}

main
