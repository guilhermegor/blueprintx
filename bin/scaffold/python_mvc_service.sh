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
INCLUDE_DOCKER_COMPOSE=false
DB_COMPOSE_BACKEND="postgresql"
INCLUDE_DATA_DIR=false
DATA_DIR_BASE="logs"
DATA_DIR_DATED=false
INCLUDE_WEBHOOK=false
WEBHOOK_PLATFORM="teams"
INCLUDE_EMAIL=false
EMAIL_BACKEND="outlook"
INCLUDE_MULTI_PIPELINE=false

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

    mkdir -p "$project_path"/src/controller
    mkdir -p "$project_path"/src/model
    mkdir -p "$project_path"/src/view
    mkdir -p "$project_path"/src/utils
    mkdir -p "$project_path"/src/config
    mkdir -p "$project_path"/tests/integration
    mkdir -p "$project_path"/tests/performance
    mkdir -p "$project_path"/tests/unit
    mkdir -p "$project_path"/bin
    mkdir -p "$project_path"/data
    mkdir -p "$project_path"/assets
    mkdir -p "$project_path"/docs
    mkdir -p "$project_path"/.vscode

    # Ensure empty dirs are tracked by git
    touch "$project_path"/tests/integration/.keep
    touch "$project_path"/tests/performance/.keep
    touch "$project_path"/tests/unit/.keep
    touch "$project_path"/data/.keep

    print_status "success" "Directory structure created"
}

create_python_files() {
    local project_path="$1"

    print_status "info" "Creating Python files..."

    touch "$project_path"/src/__init__.py
    touch "$project_path"/src/controller/__init__.py
    touch "$project_path"/src/model/__init__.py
    touch "$project_path"/src/view/__init__.py
    touch "$project_path"/src/utils/__init__.py
    touch "$project_path"/src/config/__init__.py
    cp -r "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/src/." "$project_path/src"

    print_status "success" "Python files created"
}

copy_tests() {
    local project_path="$1"

    print_status "info" "Copying sample tests..."

    cp -r "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/tests/." "$project_path/tests"
    # unit/ now ships a real sample test, so drop its placeholder
    rm -f "$project_path/tests/unit/.keep"

    print_status "success" "Sample tests copied"
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
    # Ship an initial coverage.svg so the README ![Test Coverage](./coverage.svg) badge
    # resolves on the first push instead of 404-ing; regenerated by the coverage-badge hook.
    cp "$COMMON_TEMPLATE_ROOT/coverage.svg" "$project_path/coverage.svg"
    cp "$COMMON_TEMPLATE_ROOT/assets/logo_lorem_ipsum.png" "$project_path/assets/logo_lorem_ipsum.png"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/.env.example" "$project_path/.env"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/.env.example" "$project_path/.env.example"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/CLAUDE.md" "$project_path/CLAUDE.md"

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
    envsubst < "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/pyproject.toml" > "$project_path/pyproject.toml"

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
    # Seed CHANGELOG.md so the docs Changelog page (--8<-- include) builds before the first
    # release; cz changelog regenerates it from tags at release/docs-build time.
    cp "$COMMON_TEMPLATE_ROOT/CHANGELOG.md" "$project_path/CHANGELOG.md"
    cp "$COMMON_TEMPLATE_ROOT/poetry.toml" "$project_path/poetry.toml"
    cp "$COMMON_TEMPLATE_ROOT/tasks.sh" "$project_path/tasks.sh"
    cp "$COMMON_TEMPLATE_ROOT/.gitlint" "$project_path/.gitlint"
    cp -r "$COMMON_TEMPLATE_ROOT/bin/." "$project_path/bin"
    # Reference integration test for the shared bin/ shell seams (poetry_exec.sh,
    # precommit.sh). Ships from python-common — the per-tier `cp -r tests/.` does not
    # reach python-common/tests/. See bin/CLAUDE.md "Testing shell scripts".
    mkdir -p "$project_path/tests/integration"
    cp "$COMMON_TEMPLATE_ROOT/tests/integration/test_bin_scripts.py" \
        "$project_path/tests/integration/test_bin_scripts.py"
    rm -f "$project_path/tests/integration/.keep"
    # Network-block guard + introspective-convention example — ship from
    # python-common to every tier (the per-tier `cp -r tests/.` does not reach
    # python-common/tests/). The conftest makes a real network call impossible in
    # any test; the example demonstrates enforcing a family convention via __all__.
    mkdir -p "$project_path/tests/unit"
    cp "$COMMON_TEMPLATE_ROOT/tests/conftest.py" "$project_path/tests/conftest.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_family_convention_example.py" \
        "$project_path/tests/unit/test_family_convention_example.py"
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
    cp "$COMMON_TEMPLATE_ROOT/.vscode/extensions.json" "$project_path/.vscode/extensions.json"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/.vscode/tasks.json" "$project_path/.vscode/tasks.json"

    print_status "success" "Common templates applied"
}

copy_mkdocs_templates() {
    local project_path="$1"

    print_status "info" "Copying MkDocs templates..."

    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' \
        < "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/mkdocs.yml" \
        > "$project_path/mkdocs.yml"
    envsubst '${PROJECT_DISPLAY_NAME}' \
        < "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/docs/index.md" \
        > "$project_path/docs/index.md"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/docs/architecture.md" \
        "$project_path/docs/architecture.md"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/docs/api.md" \
        "$project_path/docs/api.md"
    # Standard doc sections shared across all service tiers — single-sourced from
    # python-common/docs so every tier stays in sync.
    local doc
    for doc in usage examples faq contributing changelog; do
        cp "$COMMON_TEMPLATE_ROOT/docs/${doc}.md" "$project_path/docs/${doc}.md"
    done
    # Non-published docs/ authoring guide + the excluded backlog folder.
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/docs/CLAUDE.md" \
        "$project_path/docs/CLAUDE.md"
    mkdir -p "$project_path/docs/backlog"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/docs/backlog/.keep" \
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

prompt_docker_compose() {
    local ans
    read -r -p "Include Docker Compose for database infrastructure? [y/N] " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        INCLUDE_DOCKER_COMPOSE=true
        local db_ans
        read -r -p "Which database backend? [postgresql/mariadb/mysql] (default: postgresql): " db_ans
        case "$db_ans" in
            mariadb|mysql) DB_COMPOSE_BACKEND="$db_ans" ;;
            *) DB_COMPOSE_BACKEND="postgresql" ;;
        esac
        print_status "config" "Docker Compose backend: $DB_COMPOSE_BACKEND"
    else
        INCLUDE_DOCKER_COMPOSE=false
    fi
}

conditional_copy_docker_compose() {
    local project_path="$1"
    if [[ "$INCLUDE_DOCKER_COMPOSE" != "true" ]]; then return; fi
    local src="$COMMON_TEMPLATE_ROOT/docker-compose.${DB_COMPOSE_BACKEND}.yml"
    cp "$src" "$project_path/docker-compose.yml"
    print_status "success" "docker-compose.yml (${DB_COMPOSE_BACKEND}) copied"
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
            read -r -p "Which platform? [teams/slack] (default: teams): " platform_ans || true
            case "${platform_ans:-teams}" in
                slack) WEBHOOK_PLATFORM="slack" ;;
                *) WEBHOOK_PLATFORM="teams" ;;
            esac
            print_status "config" "Webhook platform: $WEBHOOK_PLATFORM"
            ;;
        *)
            INCLUDE_WEBHOOK=false
            ;;
    esac
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

# Multi-intent pipeline (opt-in, default No per YAGNI). Yes generates the dispatch trio
# (pipeline_<intent> + pipeline_dispatch + pipeline_common) + a dispatching main + the
# PIPELINE_INTENT env key, replacing the single _pipeline.py. Env override MULTI_PIPELINE_OPTIN=true
# forces Yes non-interactively (used by the multi-mode CI job).
prompt_pipeline_intent() {
    local answer
    if [[ "${MULTI_PIPELINE_OPTIN:-}" == "true" ]]; then
        INCLUDE_MULTI_PIPELINE=true
        print_status "config" "Pipeline mode: multi-intent (PIPELINE_INTENT dispatch) [env override]"
        return
    fi
    read -r -p "Does this process have multiple run intents (e.g. send/reconcile/notify)? [y/N]: " answer || true
    case "$answer" in
        y | Y)
            INCLUDE_MULTI_PIPELINE=true
            print_status "config" "Pipeline mode: multi-intent (PIPELINE_INTENT dispatch)"
            ;;
        *)
            INCLUDE_MULTI_PIPELINE=false
            ;;
    esac
}

# E-mail handler seam (opt-in, mirrors the webhook seam): copy optional/email into
# src/utils/email (rewrite the canonical chassis.email prefix to utils.email), wire the
# chosen backend into the controller by replacing the CLS_EMAIL_HANDLER sentinel, and add
# the EMAIL_BACKEND/SMTP_* keys to .env/.env.example.
conditional_copy_email() {
    local project_path="$1"
    if [[ "$INCLUDE_EMAIL" != "true" ]]; then return; fi
    cp -r "$COMMON_TEMPLATE_ROOT/optional/email" "$project_path/src/utils/email"
    # The seam ships its unit test co-located; relocate it to the project's tests/unit and drop
    # the now-empty package tests dir so the test is discovered and the package stays clean.
    mv "$project_path/src/utils/email/tests/unit/test_email_handlers.py" \
        "$project_path/tests/unit/test_email_handlers.py"
    rm -rf "$project_path/src/utils/email/tests"
    grep -rl "chassis.email" "$project_path/src/utils/email" \
        "$project_path/tests/unit/test_email_handlers.py" \
        | xargs -r sed -i "s|chassis\.email|utils.email|g"
    local main_path="$project_path/src/controller/main.py"
    # Inject the two first-party imports into the controller import block (keeps isort happy:
    # controller < utils.email < utils.paths), and replace the CLS_EMAIL_HANDLER sentinel with
    # the build call.
    awk -v backend="$EMAIL_BACKEND" '
        /^from controller\._pipeline import PipelineOrchestrator/ {
            print
            print "from utils.email.factory import build_email_handler  # noqa: E402"
            print "from utils.paths import resolve_path  # noqa: E402"
            next
        }
        /^CLS_EMAIL_HANDLER = None$/ {
            print "CLS_EMAIL_HANDLER = build_email_handler("
            print "\tstr_backend=\"" backend "\","
            print "\tstr_sender=os.getenv(\"SENDER_EMAIL\", \"\"),"
            print "\tpath_signatures_dir=resolve_path(\"src/config/signatures\"),"
            print "\tlogger=LOGGER,"
            print ")"
            next
        }
        { print }
    ' "$main_path" > "$main_path.tmp" && mv "$main_path.tmp" "$main_path"
    local email_env
    email_env=$'\n# E-mail handler (opt-in). EMAIL_BACKEND: outlook (Windows desktop) or smtp.\n# SENDER_EMAIL is the From address; SMTP_* are used only when EMAIL_BACKEND=smtp.\nSENDER_EMAIL=\nEMAIL_BACKEND='"$EMAIL_BACKEND"$'\nSMTP_HOST=\nSMTP_PORT=587\nSMTP_USER=\nSMTP_PASSWORD=\nSMTP_USE_TLS=true\n# Dispatch defaults (fallback for every emails.yaml block; override per block with\n# EMAIL_SEND__<BLOCK> / EMAIL_AUTO_SEND__<BLOCK>, block key upper-cased). Send on, auto-send off.\nEMAIL_SEND__DEFAULTS=true\nEMAIL_AUTO_SEND__DEFAULTS=false\n'
    printf '%s' "$email_env" >> "$project_path/.env"
    printf '%s' "$email_env" >> "$project_path/.env.example"
    print_status "success" "E-mail handler (utils/email, backend=$EMAIL_BACKEND) added"
}

# Multi-intent pipeline (opt-in). Runs LAST among the controller patches so it overwrites
# main.py with the clean dispatching entry-point; any e-mail/webhook auto-wiring of the single
# main.py is intentionally discarded (their .env keys + packages remain — wire them into the
# intent pipelines manually per controller/CLAUDE.md). Copies the dispatch trio, drops the
# single _pipeline.py, seeds PIPELINE_INTENT, and flips the controller/CLAUDE.md mode marker.
conditional_apply_multi_pipeline() {
    local project_path="$1"
    if [[ "$INCLUDE_MULTI_PIPELINE" != "true" ]]; then return; fi
    local mp_root="$BLUEPRINTX_ROOT/templates/mvc-service-native-db/optional/multi_pipeline"
    local controller_dir="$project_path/src/controller"
    cp "$mp_root/pipeline_common.py" "$controller_dir/pipeline_common.py"
    cp "$mp_root/pipeline_send.py" "$controller_dir/pipeline_send.py"
    cp "$mp_root/pipeline_reconcile.py" "$controller_dir/pipeline_reconcile.py"
    cp "$mp_root/pipeline_dispatch.py" "$controller_dir/pipeline_dispatch.py"
    cp "$mp_root/main.py" "$controller_dir/main.py"
    rm -f "$controller_dir/_pipeline.py"
    sed -i 's|<!-- pipeline-mode: single -->|<!-- pipeline-mode: multi -->|' "$controller_dir/CLAUDE.md"
    local intent_env
    intent_env=$'\n# Pipeline intent (multi-intent mode): which purpose to run.\n# Accepts send | reconcile (case/accent/spacing-insensitive); fails loud on a typo.\nPIPELINE_INTENT=send\n'
    printf '%s' "$intent_env" >> "$project_path/.env"
    printf '%s' "$intent_env" >> "$project_path/.env.example"
    print_status "success" "Multi-intent pipeline dispatch wired (send/reconcile; PIPELINE_INTENT)"
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
    for util in br_identifiers dtypes decimals logs logs_emitter text paths signatures dates \
        tabular_reader retry http_downloader zip_extractor frames \
        outlook_gateway; do
        cp "$COMMON_TEMPLATE_ROOT/src/utils/${util}.py" "$project_path/src/utils/${util}.py"
        if [ -f "$COMMON_TEMPLATE_ROOT/tests/unit/test_${util}.py" ]; then
            cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_${util}.py" "$project_path/tests/unit/test_${util}.py"
        fi
    done
    print_status "success" "Shared utils (br_identifiers/dtypes/decimals/logs/text/paths/signatures/dates/tabular_reader/retry/http_downloader/zip_extractor/frames) + tests applied"
}

# Runtime type-checking engine — single source in python-common/optional/typing.
# DDD receives it as chassis/typing (prefix already chassis.typing); MVC vendors
# it as utils/typing and rewrites the import prefix (mirrors the webhook seam).
copy_typing_chassis() {
    local project_path="$1"
    mkdir -p "$project_path/src/utils/typing" "$project_path/tests/unit"
    cp -r "$COMMON_TEMPLATE_ROOT/optional/typing/." "$project_path/src/utils/typing"
    grep -rl "chassis.typing" "$project_path/src/utils/typing" \
        | xargs -r sed -i "s|chassis\.typing|utils.typing|g"
    # The engine's unit test resolves the layout through its own import shim, so the
    # same file serves the utils (MVC) and chassis (DDD) placements.
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_typing.py" "$project_path/tests/unit/test_typing.py"
    print_status "success" "Runtime type-checking engine (utils/typing) + test applied"
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

# Webhook provider lands under src/utils/ for MVC; rewrite the package's internal
# absolute imports from the canonical chassis.webhook prefix to utils.webhook.
# The platform is auto-detected from WEBHOOK_URL, and the production gate is
# derived from ENV — so neither WEBHOOK_PLATFORM nor WEBHOOK_ENV_GATE is emitted.
conditional_copy_webhooks_yaml() {
    local project_path="$1"
    if [[ "$INCLUDE_WEBHOOK" != "true" ]]; then return; fi
    cp "$COMMON_TEMPLATE_ROOT/optional/webhooks.yaml" "$project_path/src/config/webhooks.yaml"
    cp -r "$COMMON_TEMPLATE_ROOT/optional/webhook" "$project_path/src/utils/webhook"
    grep -rl "chassis.webhook" "$project_path/src/utils/webhook" \
        | xargs -r sed -i "s|chassis\.webhook|utils.webhook|g"
    local webhook_env
    webhook_env=$'\n# Webhook — platform auto-detected from the URL; fires only when ENV is a\n# production value (prod/production/...). Leave WEBHOOK_URL empty to opt out.\nWEBHOOK_URL=\n'
    printf '%s' "$webhook_env" >> "$project_path/.env"
    printf '%s' "$webhook_env" >> "$project_path/.env.example"
    print_status "success" "Webhook provider (utils/webhook) + webhooks.yaml added"
}

# Webhook wiring depends only on the WebhookNotifier port (utils/webhook).
conditional_patch_startup() {
    local project_path="$1"
    local startup_path="$project_path/src/config/startup.py"
    if [[ "$INCLUDE_WEBHOOK" != "true" ]]; then return; fi
    cat >> "$startup_path" <<'PYBLOCK'

# Webhook notifications (opt-in) — depends only on the WebhookNotifier port. The
# platform is auto-detected from the URL; a blank URL yields a no-op NullNotifier.
from utils.text import normalize_text  # noqa: E402
from utils.webhook.factory import build_webhook  # noqa: E402


# Production allow-list: fire only when ENV normalises to a production value.
# Accent/case-insensitive, so "Prod"/"PRODUÇÃO"/"production" all match — and a
# mistyped ENV on a dev box stays silent (unlike a "!= development" deny-list).
_SET_ENV_PRODUCTION = frozenset({"prod", "production", "producao"})
YAML_WEBHOOKS: dict = yaml.safe_load((_CONFIG_DIR / "webhooks.yaml").read_text(encoding="utf-8"))
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

# Webhook notify is the orchestrator's final phase, not a post-run tail: inject the
# production-gated notifier (CLS_WEBHOOK when ENV passes the gate, else None) plus its
# message into the PipelineOrchestrator construction. The send fires inside run() via the
# WebhookNotifier port — main.py stays a thin wiring script.
conditional_patch_main_py() {
    local project_path="$1"
    local main_path="$project_path/src/controller/main.py"
    if [[ "$INCLUDE_WEBHOOK" != "true" ]]; then return; fi
    awk '
        /^PipelineOrchestrator\($/ {
            print "from config.startup import BOOL_WEBHOOK_ENABLED, CLS_WEBHOOK, MSG_WEBHOOK  # noqa: E402"
            print ""
            print ""
            print
            next
        }
        /^\)\.run\(\)$/ {
            print "\tcls_webhook=CLS_WEBHOOK if BOOL_WEBHOOK_ENABLED else None,"
            print "\tstr_webhook_message=MSG_WEBHOOK,"
            print
            next
        }
        { print }
    ' "$main_path" > "$main_path.tmp" && mv "$main_path.tmp" "$main_path"
    print_status "success" "Webhook notifier wired into PipelineOrchestrator.run() (controller/main.py)"
}

# GitHub-only assets are copied only when a GitHub remote is established (see main()).
copy_github_assets() {
    local project_path="$1"
    mkdir -p "$project_path/.github/workflows"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/tests.yaml" "$project_path/.github/workflows/tests.yaml"
    # Tag + GitHub Release (no PyPI — a service is deployed, not published). GitHub-only.
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/release.yaml" "$project_path/.github/workflows/release.yaml"
    # Docs → GitHub Pages deploy (build + gh-deploy on push to the default branch). GitHub-only.
    cp "$SHARED_TEMPLATE_ROOT/docs_version/docs.yaml" "$project_path/.github/workflows/docs.yaml"
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
                            if gh repo create "$repo_slug" --source . --remote origin --push --description "$PROJECT_DESCRIPTION" "$vis_flag"; then
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

    print_section "Python mvc-service-native-db scaffold"
    print_status "config" "Target: $PROJECT_PATH"

    validate_inputs
    resolve_github_username
    PROJECT_DISPLAY_NAME="$(format_display_name "$PROJECT_NAME")"
    prompt_docker_compose
    prompt_data_dir
    prompt_webhook
    prompt_email
    prompt_pipeline_intent
    prompt_env_wise_config
    create_directory_structure "$PROJECT_PATH"
    create_python_files "$PROJECT_PATH"
    copy_global_config "$PROJECT_PATH"
    copy_shared_utils "$PROJECT_PATH"
    copy_typing_chassis "$PROJECT_PATH"
    copy_tests "$PROJECT_PATH"
    copy_templates "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    conditional_copy_docker_compose "$PROJECT_PATH"
    conditional_patch_inputs_yaml "$PROJECT_PATH"
    apply_env_wise_config "$PROJECT_PATH"
    conditional_copy_webhooks_yaml "$PROJECT_PATH"
    conditional_patch_startup "$PROJECT_PATH"
    conditional_patch_main_py "$PROJECT_PATH"
    conditional_copy_email "$PROJECT_PATH"
    conditional_apply_multi_pipeline "$PROJECT_PATH"
    copy_mkdocs_templates "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    # GitHub-only assets exist iff a GitHub remote was established. With an upstream
    # tracking branch → copy .github; otherwise switch to the offline git-diff workflow.
    if git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        copy_github_assets "$PROJECT_PATH"
        # Online: releases are cut by tagging via release.yaml, not a hand-bump. Offline keeps
        # make bump_version (cz bump). Strip BEFORE the assets commit so its Makefile/tasks.sh
        # edits are swept into the same commit+push (no leftover uncommitted files).
        strip_bump_version "$PROJECT_PATH"
        commit_and_push_github_assets "$PROJECT_PATH"
    else
        apply_offline_mode "$PROJECT_PATH"
    fi

    print_status "success" "MVC service scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
}

main
