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

# Feature flags set by interactive prompts
INCLUDE_DOCKER_COMPOSE=false
DB_COMPOSE_BACKEND="postgresql"
INCLUDE_STORAGE=false
INCLUDE_DATA_DIR=false
DATA_DIR_BASE="logs"
DATA_DIR_DATED=false
INCLUDE_WEBHOOK=false
WEBHOOK_PLATFORM="teams"
INCLUDE_EMAIL=false
EMAIL_BACKEND="outlook"
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

    mkdir -p "$project_path"/src/chassis/db_schema/domain
    mkdir -p "$project_path"/src/chassis/db_schema/infrastructure
    mkdir -p "$project_path"/src/chassis/db_schema/application
    mkdir -p "$project_path"/src/capabilities
    mkdir -p "$project_path"/src/utils
    mkdir -p "$project_path"/src/config
    mkdir -p "$project_path"/tests/integration
    mkdir -p "$project_path"/tests/performance
    mkdir -p "$project_path"/tests/unit
    mkdir -p "$project_path"/container
    mkdir -p "$project_path"/bin
    mkdir -p "$project_path"/data
    mkdir -p "$project_path"/assets
    mkdir -p "$project_path"/docs
    mkdir -p "$project_path"/.vscode

    # Ensure empty dirs are tracked by git
    touch "$project_path"/tests/integration/.keep
    touch "$project_path"/tests/performance/.keep
    touch "$project_path"/tests/unit/.keep
    touch "$project_path"/container/.keep
    touch "$project_path"/data/.keep

    print_status "success" "Directory structure created"
}

create_python_files() {
    local project_path="$1"

    print_status "info" "Creating Python files..."

    touch "$project_path"/src/__init__.py
    touch "$project_path"/src/chassis/__init__.py
    touch "$project_path"/src/chassis/db_schema/__init__.py
    touch "$project_path"/src/capabilities/__init__.py
    touch "$project_path"/src/utils/__init__.py
    touch "$project_path"/src/config/__init__.py
    cp -r "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/src/." "$project_path/src"

    print_status "success" "Python files created"
}

copy_templates() {
    local project_path="$1"

    print_status "info" "Copying templates..."

    cp "$COMMON_TEMPLATE_ROOT/.gitignore" "$project_path/.gitignore"
    cp "$COMMON_TEMPLATE_ROOT/.python-version" "$project_path/.python-version"
    cp "$SHARED_TEMPLATE_ROOT/.editorconfig" "$project_path/.editorconfig"
    cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "$project_path/.gitattributes"
    PROJECT_DISPLAY_NAME="${PROJECT_DISPLAY_NAME:-$(format_display_name "$PROJECT_NAME")}"
    PROJECT_DISPLAY_NAME="$PROJECT_DISPLAY_NAME" GITHUB_USERNAME="$GITHUB_USERNAME" \
        envsubst '${PROJECT_DISPLAY_NAME} ${GITHUB_USERNAME}' \
        < "$COMMON_TEMPLATE_ROOT/README.md" > "$project_path/README.md"
    cp "$COMMON_TEMPLATE_ROOT/assets/logo_lorem_ipsum.png" "$project_path/assets/logo_lorem_ipsum.png"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/.env.example" "$project_path/.env"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/.env.example" "$project_path/.env.example"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/CLAUDE.md" "$project_path/CLAUDE.md"

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
    envsubst < "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/pyproject.toml" > "$project_path/pyproject.toml"

    cp "$COMMON_TEMPLATE_ROOT/.pre-commit-config.yaml" "$project_path/.pre-commit-config.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.pydocstyle" "$project_path/.pydocstyle"
    cp "$COMMON_TEMPLATE_ROOT/requirements.txt" "$project_path/requirements.txt"
    cp "$COMMON_TEMPLATE_ROOT/.codespellrc" "$project_path/.codespellrc"
    cp "$COMMON_TEMPLATE_ROOT/mypy.ini" "$project_path/mypy.ini"
    cp "$COMMON_TEMPLATE_ROOT/.sqlfluff" "$project_path/.sqlfluff"
    cp "$COMMON_TEMPLATE_ROOT/.sqlfluffignore" "$project_path/.sqlfluffignore"
    cp "$COMMON_TEMPLATE_ROOT/.hadolint.yaml" "$project_path/.hadolint.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.yamllint" "$project_path/.yamllint"
    cp "$COMMON_TEMPLATE_ROOT/.shellcheckrc" "$project_path/.shellcheckrc"
    cp "$COMMON_TEMPLATE_ROOT/CONTRIBUTING.md" "$project_path/CONTRIBUTING.md"
    envsubst < "$LICENSES_TEMPLATE_ROOT/${LICENSE_CHOICE}" > "$project_path/LICENSE"
    cp "$COMMON_TEMPLATE_ROOT/Makefile" "$project_path/Makefile"
    cp "$COMMON_TEMPLATE_ROOT/pytest.ini" "$project_path/pytest.ini"
    cp "$COMMON_TEMPLATE_ROOT/ruff.toml" "$project_path/ruff.toml"
    cp "$COMMON_TEMPLATE_ROOT/poetry.toml" "$project_path/poetry.toml"
    cp "$COMMON_TEMPLATE_ROOT/tasks.sh" "$project_path/tasks.sh"
    cp "$COMMON_TEMPLATE_ROOT/.gitlint" "$project_path/.gitlint"
    cp -r "$COMMON_TEMPLATE_ROOT/bin/." "$project_path/bin"
    cp "$SHARED_TEMPLATE_ROOT/bin/export_repo_content.sh" "$project_path/bin/export_repo_content.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/ship.sh" "$project_path/bin/ship.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/commit.sh" "$project_path/bin/commit.sh"
    chmod +x "$project_path/bin/export_repo_content.sh" "$project_path/bin/ship.sh" "$project_path/bin/commit.sh"
    mkdir -p "$project_path/dist"
    cp "$SHARED_TEMPLATE_ROOT/dist/.keep" "$project_path/dist/.keep"
    cp "$COMMON_TEMPLATE_ROOT/.coveragerc" "$project_path/.coveragerc"
    # VS Code: shared settings (python-common) + per-tier tasks (commands differ).
    mkdir -p "$project_path/.vscode"
    cp "$COMMON_TEMPLATE_ROOT/.vscode/settings.json" "$project_path/.vscode/settings.json"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/.vscode/tasks.json" "$project_path/.vscode/tasks.json"

    print_status "success" "Common templates applied"
}

copy_mkdocs_templates() {
    local project_path="$1"

    print_status "info" "Copying MkDocs templates..."

    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' \
        < "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/mkdocs.yml" \
        > "$project_path/mkdocs.yml"
    envsubst '${PROJECT_DISPLAY_NAME}' \
        < "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/docs/index.md" \
        > "$project_path/docs/index.md"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/docs/architecture.md" \
        "$project_path/docs/architecture.md"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/docs/api.md" \
        "$project_path/docs/api.md"
    # Non-published docs/ authoring guide + the excluded backlog folder.
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/docs/CLAUDE.md" \
        "$project_path/docs/CLAUDE.md"
    mkdir -p "$project_path/docs/backlog"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/docs/backlog/.keep" \
        "$project_path/docs/backlog/.keep"

    # Docs version label: hook (reads pyproject version) + theme override + header JS.
    mkdir -p "$project_path/overrides" "$project_path/docs/javascripts"
    cp "$SHARED_TEMPLATE_ROOT/docs_version/mkdocs_hooks.py" "$project_path/mkdocs_hooks.py"
    cp "$SHARED_TEMPLATE_ROOT/docs_version/main.html" "$project_path/overrides/main.html"
    cp "$SHARED_TEMPLATE_ROOT/docs_version/header-version.js" \
        "$project_path/docs/javascripts/header-version.js"

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
            # Offer to create GitHub repo via gh and push if available
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
    # Branch protection is applied later, in commit_and_push_github_assets, only
    # for the online path and only after the .github assets have been pushed —
    # so the asset push is never blocked by the rules we are about to set.
}

prompt_docker_compose() {
    local answer db_ans
    read -r -p "Include Docker Compose for database infrastructure? [y/N]: " answer || true
    case "$answer" in
        y|Y)
            INCLUDE_DOCKER_COMPOSE=true
            read -r -p "Which database backend? [postgresql/mariadb/mysql] (default: postgresql): " db_ans || true
            case "${db_ans:-postgresql}" in
                mariadb|mysql) DB_COMPOSE_BACKEND="$db_ans" ;;
                *) DB_COMPOSE_BACKEND="postgresql" ;;
            esac
            print_status "config" "Docker Compose: $DB_COMPOSE_BACKEND"
            ;;
        *)
            INCLUDE_DOCKER_COMPOSE=false
            ;;
    esac
}

prompt_storage() {
    local answer
    read -r -p "Include schema-less file storage (JSON/CSV/joblib)? [y/N]: " answer || true
    case "$answer" in
        y|Y) INCLUDE_STORAGE=true; print_status "config" "Schema-less storage: enabled" ;;
        *) INCLUDE_STORAGE=false ;;
    esac
}

prompt_data_dir() {
    local answer base_ans dated_ans
    read -r -p "Customise the output directory (logs/artifacts root)? [y/N]: " answer || true
    case "$answer" in
        y|Y)
            INCLUDE_DATA_DIR=true
            read -r -p "Output base directory [logs]: " base_ans || true
            DATA_DIR_BASE="${base_ans:-logs}"
            read -r -p "Organise output into date-named subdirectories (<base>/YYYY-MM-DD)? [y/N]: " dated_ans || true
            case "$dated_ans" in
                y|Y) DATA_DIR_DATED=true ;;
                *) DATA_DIR_DATED=false ;;
            esac
            print_status "config" "Output dir: $DATA_DIR_BASE (date-organised: $DATA_DIR_DATED)"
            ;;
        *)
            INCLUDE_DATA_DIR=false
            ;;
    esac
}

prompt_webhook() {
    local answer platform_ans
    read -r -p "Include outbound webhook notifications? [y/N]: " answer || true
    case "$answer" in
        y|Y)
            INCLUDE_WEBHOOK=true
            read -r -p "Which platform? [teams/slack/custom] (default: teams): " platform_ans || true
            case "${platform_ans:-teams}" in
                slack|custom) WEBHOOK_PLATFORM="$platform_ans" ;;
                *) WEBHOOK_PLATFORM="teams" ;;
            esac
            print_status "config" "Webhook platform: $WEBHOOK_PLATFORM"
            ;;
        *)
            INCLUDE_WEBHOOK=false
            ;;
    esac
}

copy_global_config() {
    local project_path="$1"
    cp "$COMMON_TEMPLATE_ROOT/src/config/startup.py" "$project_path/src/config/startup.py"
    cp "$COMMON_TEMPLATE_ROOT/src/config/inputs.yaml" "$project_path/src/config/inputs.yaml"
    cp "$COMMON_TEMPLATE_ROOT/src/config/outputs.yaml" "$project_path/src/config/outputs.yaml"
    cp "$COMMON_TEMPLATE_ROOT/src/config/env_config.py" "$project_path/src/config/env_config.py"
    cp "$COMMON_TEMPLATE_ROOT/src/config/CLAUDE.md" "$project_path/src/config/CLAUDE.md"
    mkdir -p "$project_path/src/config/contracts"
    cp "$COMMON_TEMPLATE_ROOT/src/config/contracts/__init__.py" "$project_path/src/config/contracts/__init__.py"
    cp "$COMMON_TEMPLATE_ROOT/src/config/contracts/example_source.py" "$project_path/src/config/contracts/example_source.py"
    if [ -f "$COMMON_TEMPLATE_ROOT/tests/unit/test_env_config.py" ]; then
        cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_env_config.py" "$project_path/tests/unit/test_env_config.py"
    fi
    print_status "success" "Global config (startup/env_config/inputs/outputs/CLAUDE.md) applied"
}

# Shared, project-agnostic utils + their unit tests, from the single source in
# python-common — so every skeleton ships the same helpers.
copy_shared_utils() {
    local project_path="$1"
    local util
    mkdir -p "$project_path/src/utils" "$project_path/tests/unit"
    for util in br_identifiers dtypes decimals loggers text paths signatures dates \
        tabular_reader retry http_downloader yaml_reader zip_extractor frames \
        outlook_gateway; do
        cp "$COMMON_TEMPLATE_ROOT/src/utils/${util}.py" "$project_path/src/utils/${util}.py"
        if [ -f "$COMMON_TEMPLATE_ROOT/tests/unit/test_${util}.py" ]; then
            cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_${util}.py" "$project_path/tests/unit/test_${util}.py"
        fi
    done
    print_status "success" "Shared utils (br_identifiers/dtypes/decimals/loggers/text/paths/signatures/dates/tabular_reader/retry/http_downloader/yaml_reader/zip_extractor/frames) + tests applied"
}

# Runtime type-checking engine — single source in python-common/optional/typing.
# DDD keeps the canonical chassis.typing import prefix, so it is copied as-is to
# src/chassis/typing (no rewrite; the MVC tiers vendor it under utils/typing).
copy_typing_chassis() {
    local project_path="$1"
    mkdir -p "$project_path/src/chassis/typing"
    cp -r "$COMMON_TEMPLATE_ROOT/optional/typing/." "$project_path/src/chassis/typing"
    print_status "success" "Runtime type-checking engine (chassis/typing) applied"
}

# chassis/db is the DatabaseHandler ABC that db_schema (and db_wschema) extend.
# Native db_schema requires it, so it is always injected here.
copy_required_chassis_db() {
    local project_path="$1"
    cp -r "$COMMON_TEMPLATE_ROOT/optional/chassis/db" "$project_path/src/chassis/db"
    print_status "success" "chassis/db copied (required by db_schema)"
}

conditional_copy_storage() {
    local project_path="$1"
    if [[ "$INCLUDE_STORAGE" != "true" ]]; then return; fi
    cp -r "$COMMON_TEMPLATE_ROOT/optional/chassis/db_wschema" "$project_path/src/chassis/db_wschema"
    cat "$COMMON_TEMPLATE_ROOT/optional/storage.env.fragment" >> "$project_path/.env"
    cat "$COMMON_TEMPLATE_ROOT/optional/storage.env.fragment" >> "$project_path/.env.example"
    print_status "success" "Schema-less storage (chassis/db_wschema) added"
}

# GitHub-only assets (Actions workflow, CODEOWNERS, PR template) are copied only
# when a GitHub remote is established — see main().
copy_github_assets() {
    local project_path="$1"
    mkdir -p "$project_path/.github/workflows"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/tests.yaml" "$project_path/.github/workflows/tests.yaml"
    envsubst '${GITHUB_USERNAME}' < "$SHARED_TEMPLATE_ROOT/.github/CODEOWNERS" > "$project_path/.github/CODEOWNERS"
    cp "$SHARED_TEMPLATE_ROOT/.github/CLAUDE.md" "$project_path/.github/CLAUDE.md"
    cp "$SHARED_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
    print_status "success" "GitHub assets copied (.github)"
}

# copy_github_assets adds .github AFTER the first commit/push, so commit and push
# those assets here — giving the online project a clean working tree and a remote
# that carries them. Done BEFORE branch protection so this direct push to the
# default branch is not blocked by the rules we then apply.
commit_and_push_github_assets() {
    local project_path="$1"
    git -C "$project_path" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
    if [ -n "$(git -C "$project_path" status --porcelain)" ]; then
        git -C "$project_path" add -A
        git -C "$project_path" commit -q --no-verify -m "chore: add GitHub project assets" || true
        git -C "$project_path" push >/dev/null 2>&1 \
            || print_status "warning" "Could not push GitHub assets; run 'git push' manually."
    fi
    apply_branch_protection "$project_path"
}

conditional_copy_docker_compose() {
    local project_path="$1"
    if [[ "$INCLUDE_DOCKER_COMPOSE" != "true" ]]; then return; fi
    local src="$COMMON_TEMPLATE_ROOT/docker-compose.${DB_COMPOSE_BACKEND}.yml"
    cp "$src" "$project_path/docker-compose.yml"
    print_status "success" "docker-compose.yml (${DB_COMPOSE_BACKEND}) copied"
}

# Output directory is data-driven from inputs.yaml (no startup.py patching).
conditional_patch_inputs_yaml() {
    local project_path="$1"
    if [[ "$INCLUDE_DATA_DIR" != "true" ]]; then return; fi
    local f="$project_path/src/config/inputs.yaml"
    sed -i "s|^daily_infos_base_path:.*|daily_infos_base_path: \"${DATA_DIR_BASE}\"|" "$f"
    sed -i "s|^daily_infos_dated:.*|daily_infos_dated: ${DATA_DIR_DATED}|" "$f"
    print_status "success" "Output directory configured in inputs.yaml"
}

# Webhook wiring depends only on the WebhookNotifier port (chassis/webhook),
# so swapping platform never edits this block.
conditional_patch_startup() {
    local project_path="$1"
    local startup_path="$project_path/src/config/startup.py"
    if [[ "$INCLUDE_WEBHOOK" != "true" ]]; then return; fi
    cat >> "$startup_path" <<'PYBLOCK'

# Webhook notifications (opt-in) — depends only on the WebhookNotifier port. The
# platform is auto-detected from the URL; a blank URL yields a no-op NullNotifier.
from chassis.webhook.factory import build_webhook  # noqa: E402
from utils.text import normalize_text  # noqa: E402


# Production allow-list: fire only when ENV normalises to a production value.
# Accent/case-insensitive, so "Prod"/"PRODUÇÃO"/"production" all match — and a
# mistyped ENV on a dev box stays silent (unlike a "!= development" deny-list).
_SET_ENV_PRODUCTION = frozenset({"prod", "production", "producao"})
YAML_WEBHOOKS: dict = reading_yaml(str(_CONFIG_DIR / "webhooks.yaml"))
BOOL_WEBHOOK_ENABLED: bool = normalize_text(ENVIRONMENT) in _SET_ENV_PRODUCTION
CLS_WEBHOOK = build_webhook(os.getenv("WEBHOOK_URL", ""))
MSG_WEBHOOK: str = YAML_WEBHOOKS["message"].format(
	app_name=APP_NAME,
	environment=ENVIRONMENT,
	hostname=HOSTNAME,
	user=USER,
	log_path=str(PATH_LOG),
)
PYBLOCK
    print_status "success" "Webhook wiring appended to startup.py"
}

# Conditional webhook send in main.py, gated by the deployment environment.
conditional_patch_main_py() {
    local project_path="$1"
    local main_path="$project_path/src/main.py"
    if [[ "$INCLUDE_WEBHOOK" != "true" ]]; then return; fi
    cat >> "$main_path" <<'PYBLOCK'

# ─── NOTIFY ───────────────────────────────────────────────────────────────────
from src.config.startup import (  # noqa: E402
	BOOL_WEBHOOK_ENABLED,
	CLS_WEBHOOK,
	MSG_WEBHOOK,
)


if BOOL_WEBHOOK_ENABLED:
	CLS_WEBHOOK.send(MSG_WEBHOOK)
PYBLOCK
    print_status "success" "Webhook send appended to main.py"
}

# The platform is auto-detected from WEBHOOK_URL, and the production gate is
# derived from ENV — so neither WEBHOOK_PLATFORM nor WEBHOOK_ENV_GATE is emitted.
conditional_copy_webhooks_yaml() {
    local project_path="$1"
    if [[ "$INCLUDE_WEBHOOK" != "true" ]]; then return; fi
    cp "$COMMON_TEMPLATE_ROOT/optional/webhooks.yaml" "$project_path/src/config/webhooks.yaml"
    cp -r "$COMMON_TEMPLATE_ROOT/optional/webhook" "$project_path/src/chassis/webhook"
    local webhook_env
    webhook_env=$'\n# Webhook — platform auto-detected from the URL; fires only when ENV is a\n# production value (prod/production/...). Leave WEBHOOK_URL empty to opt out.\nWEBHOOK_URL=\n'
    printf '%s' "$webhook_env" >> "$project_path/.env"
    printf '%s' "$webhook_env" >> "$project_path/.env.example"
    print_status "success" "Webhook provider (chassis/webhook) + webhooks.yaml added"
}

prompt_email() {
    local answer backend_ans
    read -r -p "Include an outbound e-mail handler (Outlook/SMTP)? [y/N]: " answer || true
    case "$answer" in
        y | Y)
            INCLUDE_EMAIL=true
            read -r -p "Which backend? [outlook/smtp] (default: outlook): " backend_ans || true
            case "${backend_ans:-outlook}" in
                smtp) EMAIL_BACKEND="smtp" ;;
                *) EMAIL_BACKEND="outlook" ;;
            esac
            print_status "config" "E-mail backend: $EMAIL_BACKEND"
            ;;
        *)
            INCLUDE_EMAIL=false
            ;;
    esac
}

# E-mail handler seam (opt-in): copy optional/email into src/chassis/email (canonical
# chassis.email prefix — no rewrite, like the webhook seam) and add the EMAIL_BACKEND/SMTP_*
# keys. DDD has no shared orchestrator, so a capability wires `build_email_handler(...)`
# where it needs to notify (the Outlook backend injects utils.outlook_gateway by default).
conditional_copy_email() {
    local project_path="$1"
    if [[ "$INCLUDE_EMAIL" != "true" ]]; then return; fi
    cp -r "$COMMON_TEMPLATE_ROOT/optional/email" "$project_path/src/chassis/email"
    local email_env
    email_env=$'\n# E-mail handler (opt-in). EMAIL_BACKEND: outlook (Windows desktop) or smtp.\n# SENDER_EMAIL is the From address; SMTP_* are used only when EMAIL_BACKEND=smtp.\nSENDER_EMAIL=\nEMAIL_BACKEND='"$EMAIL_BACKEND"$'\nSMTP_HOST=\nSMTP_PORT=587\nSMTP_USER=\nSMTP_PASSWORD=\nSMTP_USE_TLS=true\n'
    printf '%s' "$email_env" >> "$project_path/.env"
    printf '%s' "$email_env" >> "$project_path/.env.example"
    print_status "success" "E-mail handler (chassis/email, backend=$EMAIL_BACKEND) added"
}

apply_offline_mode() {
    local project_path="$1"

    print_status "info" "No GitHub remote connected — switching to offline mode"
    # GitHub-only assets are never created offline (see copy_github_assets in main);
    # ship the offline git-diff workflow + the local git-flow helpers instead.
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

    print_section "Python ddd-service-native-db scaffold"
    print_status "config" "Target: $PROJECT_PATH"

    validate_inputs
    resolve_github_username
    PROJECT_DISPLAY_NAME="$(format_display_name "$PROJECT_NAME")"
    prompt_docker_compose
    prompt_storage
    prompt_data_dir
    prompt_webhook
    prompt_email
    prompt_env_wise_config
    create_directory_structure "$PROJECT_PATH"
    create_python_files "$PROJECT_PATH"
    copy_global_config "$PROJECT_PATH"
    copy_shared_utils "$PROJECT_PATH"
    copy_typing_chassis "$PROJECT_PATH"
    copy_required_chassis_db "$PROJECT_PATH"
    copy_templates "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    conditional_copy_docker_compose "$PROJECT_PATH"
    conditional_copy_storage "$PROJECT_PATH"
    conditional_patch_inputs_yaml "$PROJECT_PATH"
    apply_env_wise_config "$PROJECT_PATH"
    conditional_copy_webhooks_yaml "$PROJECT_PATH"
    conditional_copy_email "$PROJECT_PATH"
    conditional_patch_startup "$PROJECT_PATH"
    conditional_patch_main_py "$PROJECT_PATH"
    copy_mkdocs_templates "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    # GitHub-only assets exist iff a GitHub remote was established. With an upstream
    # tracking branch → copy .github; otherwise switch to the offline git-diff workflow.
    if git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        copy_github_assets "$PROJECT_PATH"
        commit_and_push_github_assets "$PROJECT_PATH"
    else
        apply_offline_mode "$PROJECT_PATH"
    fi

    print_status "success" "Hex-service scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
}

main
