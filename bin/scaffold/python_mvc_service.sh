#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=bin/lib/scaffold_python_templates.sh
source "$SCRIPT_DIR/../lib/scaffold_python_templates.sh"
# shellcheck source=bin/lib/scaffold_git_remote.sh
source "$SCRIPT_DIR/../lib/scaffold_git_remote.sh"

PROJECT_ROOT="$1"
PROJECT_NAME="$2"
PROJECT_DESCRIPTION="${3:-}"
PROJECT_VERSION="${4:-0.0.1}"
LICENSE_CHOICE="${LICENSE_CHOICE:-MIT}"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMMON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/python-common"
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
INCLUDE_OTEL=false
INCLUDE_EMAIL=false
EMAIL_BACKEND="outlook"
INCLUDE_MULTI_PIPELINE=false


validate_inputs() {
    if [ -z "$PROJECT_ROOT" ] || [ -z "$PROJECT_NAME" ]; then
        exit_error "Usage: $0 <project_root_dir> <project_name>"
    fi
    if ! is_valid_project_name "$PROJECT_NAME"; then
        exit_error "Invalid project name '$PROJECT_NAME'. Use a letter or underscore first, then letters, digits, '-' or '_'."
    fi
    print_status "success" "Input validation passed"
}

format_display_name() {
    echo "$1"
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
    rm -f "$project_path/tests/unit/.keep"

    print_status "success" "Sample tests copied"
}

copy_templates() {
    local project_path="$1"

    print_status "info" "Copying templates..."

    cp "$COMMON_TEMPLATE_ROOT/.gitignore" "$project_path/.gitignore"
    cp "$COMMON_TEMPLATE_ROOT/.python-version" "$project_path/.python-version"
    cp "$COMMON_TEMPLATE_ROOT/requirements.txt" "$project_path/requirements.txt"
    cp "$SHARED_TEMPLATE_ROOT/.editorconfig" "$project_path/.editorconfig"
    cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "$project_path/.gitattributes"
    cp "$SHARED_TEMPLATE_ROOT/.coderabbit.yaml" "$project_path/.coderabbit.yaml"
    mkdir -p "$project_path/.greptile" && cp "$SHARED_TEMPLATE_ROOT/.greptile/config.json" "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/.greptile/"* "$project_path/.greptile/"
    PROJECT_DISPLAY_NAME="${PROJECT_DISPLAY_NAME:-$(format_display_name "$PROJECT_NAME")}"
    PROJECT_DISPLAY_NAME="$PROJECT_DISPLAY_NAME" envsubst '${PROJECT_DISPLAY_NAME}' < "$COMMON_TEMPLATE_ROOT/README.md" > "$project_path/README.md"
    cp "$COMMON_TEMPLATE_ROOT/coverage.svg" "$project_path/coverage.svg"
    cp "$COMMON_TEMPLATE_ROOT/assets/logo_lorem_ipsum.png" "$project_path/assets/logo_lorem_ipsum.png"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/.env.example" "$project_path/.env"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/.env.example" "$project_path/.env.example"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/docs/configuration.md" "$project_path/docs/configuration.md"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/CLAUDE.md" "$project_path/CLAUDE.md"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/.layer-policy.yaml" "$project_path/.layer-policy.yaml"

    print_status "success" "Templates copied and configured"
}

copy_common_templates() {
	scaffold_copy_common_templates "mvc-service-native-db" "$1"
}

copy_mkdocs_templates() {
    local project_path="$1"

    print_status "info" "Copying MkDocs templates..."

    export DOCS_LOCALE="${DOCS_LOCALE:-en}"
    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY} ${DOCS_LOCALE}' \
        < "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/mkdocs.yml" \
        > "$project_path/mkdocs.yml"
    envsubst '${PROJECT_DISPLAY_NAME}' \
        < "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/docs/index.md" \
        > "$project_path/docs/index.md"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/docs/architecture.md" \
        "$project_path/docs/architecture.md"
    mkdir -p "$project_path/docs/api"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/docs/api/index.md" \
        "$project_path/docs/api/index.md"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/docs/api/reference.md" \
        "$project_path/docs/api/reference.md"
    mkdir -p "$project_path/docs/assets"
    cp "$COMMON_TEMPLATE_ROOT/assets/logo_lorem_ipsum.png" \
        "$project_path/docs/assets/logo.png"
    local doc
    for doc in usage examples faq contributing changelog; do
        cp "$COMMON_TEMPLATE_ROOT/docs/${doc}.md" "$project_path/docs/${doc}.md"
    done
    cp "$COMMON_TEMPLATE_ROOT/docs/.docs-skeleton.yaml" "$project_path/docs/.docs-skeleton.yaml"
    cp "$BLUEPRINTX_ROOT/templates/mvc-service-native-db/docs/CLAUDE.md" \
        "$project_path/docs/CLAUDE.md"


    print_status "success" "MkDocs templates copied"
}

apply_branch_protection() {
    local project_path="$1"
    local branch="main"
    local repo="${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}"

    if ! command -v gh >/dev/null 2>&1; then
        print_status "info" "gh CLI not found; skipping main branch protection."
        return
    fi

    if ! gh auth status >/dev/null 2>&1; then
        print_status "warning" "gh not authenticated; skipping main branch protection."
        return
    fi

    if ! gh repo view "$repo" >/dev/null 2>&1; then
        print_status "warning" "GitHub repo $repo not reachable; skipping branch protection."
        return
    fi

    local do_protect reviews_ans reviews_approvals
    prompt_yes_no do_protect "$(prompt_main "Protect branch '$branch' on GitHub now? [y/N]: ")"
    if [ "$do_protect" != "true" ]; then
        print_status "info" "Skipped branch protection"
        return
    fi

    prompt_yes_no reviews_ans "$(prompt_sub "Will human reviewers gate merges to '$branch'? [y/N]: ")"
    if [ "$reviews_ans" = "true" ]; then
        reviews_approvals=1
    else
        reviews_approvals=0
    fi
    (cd "$project_path" && RULESET_APPROVALS="$reviews_approvals" bash bin/enable_repo_rules.sh)
}

prompt_docker_compose() {
    local db_ans
    prompt_yes_no INCLUDE_DOCKER_COMPOSE "$(prompt_main "Include Docker Compose for database infrastructure? [y/N] ")"
    if [ "$INCLUDE_DOCKER_COMPOSE" = "true" ]; then
        prompt_read db_ans "$(prompt_sub "Which database backend? [postgresql/mariadb/mysql] (default: postgresql): ")"
        case "$db_ans" in
            mariadb|mysql) DB_COMPOSE_BACKEND="$db_ans" ;;
            *) DB_COMPOSE_BACKEND="postgresql" ;;
        esac
        print_status "config" "Docker Compose backend: $DB_COMPOSE_BACKEND"
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
    local base_ans
    prompt_yes_no INCLUDE_DATA_DIR "$(prompt_main "Customise the output directory (logs/artifacts root)? [y/N]: ")"
    if [ "$INCLUDE_DATA_DIR" = "true" ]; then
        prompt_read base_ans "$(prompt_sub "Output base directory [logs]: ")"
        DATA_DIR_BASE="${base_ans:-logs}"
        prompt_yes_no DATA_DIR_DATED "$(prompt_sub "Organise output into date-named subdirectories (<base>/YYYY-MM-DD)? [y/N]: ")"
        print_status "config" "Output dir: $DATA_DIR_BASE (date-organised: $DATA_DIR_DATED)"
    fi
}

prompt_webhook() {
    local platform_ans
    prompt_yes_no INCLUDE_WEBHOOK "$(prompt_main "Include outbound webhook notifications? [y/N]: ")"
    if [ "$INCLUDE_WEBHOOK" = "true" ]; then
        prompt_read platform_ans "$(prompt_sub "Which platform? [teams/slack] (default: teams): ")"
        case "${platform_ans:-teams}" in
            slack) WEBHOOK_PLATFORM="slack" ;;
            *) WEBHOOK_PLATFORM="teams" ;;
        esac
        print_status "config" "Webhook platform: $WEBHOOK_PLATFORM"
    fi
}

prompt_otel() {
    prompt_yes_no INCLUDE_OTEL "$(prompt_main "Include OpenTelemetry OTLP log export (opt-in, sends to an OTel collector)? [y/N]: ")"
    if [ "$INCLUDE_OTEL" = "true" ]; then
        print_status "config" "OTLP log export: enabled"
    fi
}

prompt_email() {
    local backend_ans
    prompt_yes_no INCLUDE_EMAIL "$(prompt_main "Include an outbound e-mail handler (Outlook/SMTP)? [y/N]: ")"
    if [ "$INCLUDE_EMAIL" = "true" ]; then
        prompt_read backend_ans "$(prompt_sub "Which backend? [outlook/smtp] (default: outlook): ")"
        case "${backend_ans:-outlook}" in
            smtp) EMAIL_BACKEND="smtp" ;;
            *) EMAIL_BACKEND="outlook" ;;
        esac
        print_status "config" "E-mail backend: $EMAIL_BACKEND"
    fi
}

prompt_pipeline_intent() {
    if [[ "${MULTI_PIPELINE_OPTIN:-}" == "true" ]]; then
        INCLUDE_MULTI_PIPELINE=true
        print_status "config" "Pipeline mode: multi-intent (PIPELINE_INTENT dispatch) [env override]"
        return
    fi
    prompt_yes_no INCLUDE_MULTI_PIPELINE "$(prompt_main "Does this process have multiple run intents (e.g. send/reconcile/notify)? [y/N]: ")"
    if [ "$INCLUDE_MULTI_PIPELINE" = "true" ]; then
        print_status "config" "Pipeline mode: multi-intent (PIPELINE_INTENT dispatch)"
    fi
}

conditional_copy_email() {
    local project_path="$1"
    if [[ "$INCLUDE_EMAIL" != "true" ]]; then return; fi
    mkdir -p "$project_path/src/utils/email"
    cp -r "$COMMON_TEMPLATE_ROOT/optional/email/." "$project_path/src/utils/email/"
    mv "$project_path/src/utils/email/tests/unit/test_email_handlers.py" \
        "$project_path/tests/unit/test_email_handlers.py"
    rm -rf "$project_path/src/utils/email/tests"
    while IFS= read -r str_file; do
        sed_inplace "s|chassis\.email|utils.email|g" "$str_file"
    done < <(grep -rl "chassis.email" "$project_path/src/utils/email" \
        "$project_path/tests/unit/test_email_handlers.py")
    local main_path="$project_path/src/controller/main.py"
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
    cp "$mp_root/test_pipeline.py" "$project_path/tests/unit/test_pipeline.py"
    rm -f "$project_path/tests/unit/test_pipeline_enrichment.py"
    rm -f "$project_path/tests/unit/test_pipeline_phases.py"
    rm -f "$controller_dir/_pipeline.py"
    sed_inplace 's|<!-- pipeline-mode: single -->|<!-- pipeline-mode: multi -->|' "$controller_dir/CLAUDE.md"
    local intent_env
    intent_env=$'\nPIPELINE_INTENT=send\n'
    printf '%s' "$intent_env" >> "$project_path/.env"
    printf '%s' "$intent_env" >> "$project_path/.env.example"
    cat "$COMMON_TEMPLATE_ROOT/optional/pipeline-intent.config.md" >> "$project_path/docs/configuration.md"
    print_status "success" "Multi-intent pipeline dispatch wired (send/reconcile; PIPELINE_INTENT)"
}

conditional_prune_optin_deps() {
    local project_path="$1"
    scaffold_prune_optin_dependency "$project_path" "$INCLUDE_WEBHOOK" \
        '/^# Microsoft Teams incoming-webhook transport/,/^pymsteams = /d'
}

copy_global_config() {
    local project_path="$1"
    cp "$COMMON_TEMPLATE_ROOT/src/config/startup.py" "$project_path/src/config/startup.py"
    cp "$COMMON_TEMPLATE_ROOT/src/config/inputs.yaml" "$project_path/src/config/inputs.yaml"
    cp "$COMMON_TEMPLATE_ROOT/src/config/outputs.yaml" "$project_path/src/config/outputs.yaml"
    cp "$COMMON_TEMPLATE_ROOT/src/config/contract_oracles.yaml" "$project_path/src/config/contract_oracles.yaml"
    cp "$COMMON_TEMPLATE_ROOT/src/config/env_config.py" "$project_path/src/config/env_config.py"
    cp "$COMMON_TEMPLATE_ROOT/src/config/CLAUDE.md" "$project_path/src/config/CLAUDE.md"
    mkdir -p "$project_path/src/config/contracts"
    cp "$COMMON_TEMPLATE_ROOT/src/config/contracts/__init__.py" "$project_path/src/config/contracts/__init__.py"
    cp "$COMMON_TEMPLATE_ROOT/src/config/contracts/example_source.py" "$project_path/src/config/contracts/example_source.py"
    if [ -f "$COMMON_TEMPLATE_ROOT/tests/unit/test_env_config.py" ]; then
        cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_env_config.py" "$project_path/tests/unit/test_env_config.py"
    fi
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_fixture_scope_gate.py" "$project_path/tests/unit/test_fixture_scope_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_quality_rules_gate.py" "$project_path/tests/unit/test_quality_rules_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_one_assert_gate.py" "$project_path/tests/unit/test_one_assert_gate.py"
    print_status "success" "Global config (startup/env_config/inputs/outputs/CLAUDE.md) applied"
}

copy_shared_utils() {
    local project_path="$1"
    local util
    mkdir -p "$project_path/src/utils" "$project_path/tests/unit"
    local -a utils=(
        br_identifiers dtypes decimals logs logs_emitter text paths signatures dates
        tabular_reader xml_reader provenance sidecar_metadata retry http_downloader zip_extractor frames
        ms_office email raw_workspace daily_cache queries
        regime_window regime_registry regime_adapter spec_gap_registry
    )
    for util in "${utils[@]}"; do
        if [ -d "$COMMON_TEMPLATE_ROOT/src/utils/${util}" ]; then
            mkdir -p "$project_path/src/utils/${util}"
            cp -r "$COMMON_TEMPLATE_ROOT/src/utils/${util}/." "$project_path/src/utils/${util}/"
        else
            cp "$COMMON_TEMPLATE_ROOT/src/utils/${util}.py" "$project_path/src/utils/${util}.py"
        fi
        if [ -f "$COMMON_TEMPLATE_ROOT/tests/unit/test_${util}.py" ]; then
            cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_${util}.py" "$project_path/tests/unit/test_${util}.py"
        fi
    done
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_ms_office_outlook_gateway.py" \
        "$project_path/tests/unit/test_ms_office_outlook_gateway.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_ms_office_excel_sheet_names.py" \
        "$project_path/tests/unit/test_ms_office_excel_sheet_names.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_email_dispatch.py" \
        "$project_path/tests/unit/test_email_dispatch.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_email_sender.py" \
        "$project_path/tests/unit/test_email_sender.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_email_html_body.py" \
        "$project_path/tests/unit/test_email_html_body.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_regime_adapters.py" \
        "$project_path/tests/unit/test_regime_adapters.py"
    print_status "success" "Shared utils + their tests applied (${#utils[@]} modules)"
}

copy_typing_chassis() {
    local project_path="$1"
    mkdir -p "$project_path/src/utils/typing" "$project_path/tests/unit"
    cp -r "$COMMON_TEMPLATE_ROOT/optional/typing/." "$project_path/src/utils/typing"
    while IFS= read -r str_file; do
        sed_inplace "s|chassis\.typing|utils.typing|g" "$str_file"
    done < <(grep -rl "chassis.typing" "$project_path/src/utils/typing")
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_typing.py" "$project_path/tests/unit/test_typing.py"
    print_status "success" "Runtime type-checking engine (utils/typing) + test applied"
}

conditional_patch_inputs_yaml() {
    local project_path="$1"
    if [[ "$INCLUDE_DATA_DIR" != "true" ]]; then return; fi
    local f="$project_path/src/config/inputs.yaml"
    sed_inplace "s|^daily_infos_base_path:.*|daily_infos_base_path: \"${DATA_DIR_BASE}\"|" "$f"
    sed_inplace "s|^daily_infos_dated:.*|daily_infos_dated: ${DATA_DIR_DATED}|" "$f"
    print_status "success" "Output directory configured in inputs.yaml"
}

conditional_copy_webhooks_yaml() {
    local project_path="$1"
    if [[ "$INCLUDE_WEBHOOK" != "true" ]]; then return; fi
    cp "$COMMON_TEMPLATE_ROOT/optional/webhooks.yaml" "$project_path/src/config/webhooks.yaml"
    cp -r "$COMMON_TEMPLATE_ROOT/optional/webhook" "$project_path/src/utils/webhook"
    while IFS= read -r str_file; do
        sed_inplace "s|chassis\.webhook|utils.webhook|g" "$str_file"
    done < <(grep -rl "chassis.webhook" "$project_path/src/utils/webhook")
    local webhook_env
    webhook_env=$'\n# Webhook — platform auto-detected from the URL; fires only when ENV is a\n# production value (prod/production/...). Leave WEBHOOK_URL empty to opt out.\nWEBHOOK_URL=\n'
    printf '%s' "$webhook_env" >> "$project_path/.env"
    printf '%s' "$webhook_env" >> "$project_path/.env.example"
    print_status "success" "Webhook provider (utils/webhook) + webhooks.yaml added"
}

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

conditional_copy_otel() {
    local project_path="$1"
    if [[ "$INCLUDE_OTEL" != "true" ]]; then return; fi
    cp "$COMMON_TEMPLATE_ROOT/optional/otel_logging.py" "$project_path/src/utils/otel_logging.py"
    cp "$COMMON_TEMPLATE_ROOT/optional/test_otel_logging.py" "$project_path/tests/unit/test_otel_logging.py"
    cat "$COMMON_TEMPLATE_ROOT/optional/otel.env.fragment" >> "$project_path/.env"
    cat "$COMMON_TEMPLATE_ROOT/optional/otel.env.fragment" >> "$project_path/.env.example"
    cat "$COMMON_TEMPLATE_ROOT/optional/otel.config.md" >> "$project_path/docs/configuration.md"
    cp "$COMMON_TEMPLATE_ROOT/docker-compose.otel-collector.yml" "$project_path/docker-compose.otel-collector.yml"
    cp "$COMMON_TEMPLATE_ROOT/otel-collector-config.yaml" "$project_path/otel-collector-config.yaml"
    sed_inplace '/^python-dotenv = ">=1.0.0"/a\
# OpenTelemetry OTLP log export (opt-in, blueprintx#438) — pinned; the Logs signal is\
# "Development" status upstream (see utils/otel_logging.py for the measured source).\
opentelemetry-api = "==1.44.0"\
opentelemetry-sdk = "==1.44.0"\
opentelemetry-exporter-otlp-proto-http = "==1.44.0"' "$project_path/pyproject.toml"
    cat >> "$project_path/src/config/startup.py" <<'PYBLOCK'

# OTLP log export (opt-in) — ADDS a handler to LOGGER; never replaces the FileHandler
# above. A no-op when OTEL_EXPORTER_OTLP_ENDPOINT is unset (see utils/otel_logging.py).
from utils.otel_logging import configure_otel_logging  # noqa: E402


configure_otel_logging(LOGGER)
PYBLOCK
    print_status "success" "OTLP log export (utils/otel_logging.py) wired into startup.py + collector compose added"
}

copy_github_assets() {
    local project_path="$1"
    mkdir -p "$project_path/.github/workflows"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/tests.yaml" "$project_path/.github/workflows/tests.yaml"
    if [ -n "${GITGUARDIAN_API_KEY:-}" ]; then
        cp "$COMMON_TEMPLATE_ROOT/.github/workflows/secret_scan.yaml" "$project_path/.github/workflows/secret_scan.yaml"
    fi
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/review_threads.yaml" "$project_path/.github/workflows/review_threads.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/coderabbit_trigger.yaml" "$project_path/.github/workflows/coderabbit_trigger.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/review_retry.yaml" "$project_path/.github/workflows/review_retry.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/pr-gate.yaml" "$project_path/.github/workflows/pr-gate.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/pr-reconcile.yaml" "$project_path/.github/workflows/pr-reconcile.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/contract_drift.yaml" "$project_path/.github/workflows/contract_drift.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/release.yaml" "$project_path/.github/workflows/release.yaml"
    cp "$SHARED_TEMPLATE_ROOT/docs_version/docs.yaml" "$project_path/.github/workflows/docs.yaml"
    envsubst '${GITHUB_USERNAME}' < "$SHARED_TEMPLATE_ROOT/.github/CODEOWNERS" > "$project_path/.github/CODEOWNERS"
    # dependabot.yml (ordinary VERSION bumps; SECURITY updates are a toggle set by
    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' \
        < "$SHARED_TEMPLATE_ROOT/SECURITY.md" > "$project_path/SECURITY.md"
    cp "$COMMON_TEMPLATE_ROOT/.github/dependabot.yml" "$project_path/.github/dependabot.yml"
    cp "$SHARED_TEMPLATE_ROOT/.github/CLAUDE.md" "$project_path/.github/CLAUDE.md"
    cp "$SHARED_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
    mkdir -p "$project_path/.github/ISSUE_TEMPLATE" && cp "$SHARED_TEMPLATE_ROOT/.github/ISSUE_TEMPLATE/feature_or_fix.md" "$project_path/.github/ISSUE_TEMPLATE/feature_or_fix.md"
    copy_repo_policy_workflows "$project_path"
    print_status "success" "GitHub assets copied (.github)"
}

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
	scaffold_prompt_git_remote_setup "$1" || true
}

apply_offline_mode() {
    local project_path="$1"

    print_status "info" "No GitHub remote connected — switching to offline mode"
    mkdir -p "$project_path/bin/lib"
    cp "$SHARED_TEMPLATE_ROOT/bin/lib/common.sh" "$project_path/bin/lib/common.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_diff_export.sh" "$project_path/bin/git_diff_export.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_diff_apply.sh" "$project_path/bin/git_diff_apply.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_diff_check.sh" "$project_path/bin/git_diff_check.sh"
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
    cp "$SHARED_TEMPLATE_ROOT/poe_tasks.offline.toml" "$project_path/poe_tasks.offline.toml"
    add_poe_include "$project_path" "poe_tasks.offline.toml"
    mkdir -p "$project_path/git_diffs"
    touch "$project_path/git_diffs/.keep"
    swap_protect_branch_hook "$project_path"
    commit_offline_artifacts "$project_path"
    print_status "success" "Offline workflow enabled (new_branch | git_merge_to_main | git_diff_* | protect-branch)"
}

commit_offline_artifacts() {
    local project_path="$1"
    git -C "$project_path" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
    git -C "$project_path" add -A
    git -C "$project_path" commit -q --no-verify -m "chore: enable offline git workflow" || true
}

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


finalize_github_or_offline() {
    local project_path="$1"

    if [ "$SCAFFOLD_REMOTE_VERIFIED" = "1" ] \
        && git -C "$project_path" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        copy_github_assets "$project_path"
        strip_bump_version "$project_path"
        commit_and_push_github_assets "$project_path"
    else
        apply_offline_mode "$project_path"
    fi
}


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
    prompt_otel
    prompt_email
    prompt_pipeline_intent
    prompt_env_wise_config
    scaffold_prompt_review_bot_roster
    create_directory_structure "$PROJECT_PATH"
    create_python_files "$PROJECT_PATH"
    copy_global_config "$PROJECT_PATH"
    copy_shared_utils "$PROJECT_PATH"
    copy_typing_chassis "$PROJECT_PATH"
    copy_tests "$PROJECT_PATH"
    copy_templates "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    conditional_prune_optin_deps "$PROJECT_PATH"
    conditional_copy_docker_compose "$PROJECT_PATH"
    conditional_patch_inputs_yaml "$PROJECT_PATH"
    apply_env_wise_config "$PROJECT_PATH"
    conditional_copy_webhooks_yaml "$PROJECT_PATH"
    conditional_patch_startup "$PROJECT_PATH"
    conditional_patch_main_py "$PROJECT_PATH"
    conditional_copy_otel "$PROJECT_PATH"
    conditional_copy_email "$PROJECT_PATH"
    conditional_apply_multi_pipeline "$PROJECT_PATH"
    copy_mkdocs_templates "$PROJECT_PATH"
    scaffold_purge_caches "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"
    finalize_github_or_offline "$PROJECT_PATH"

    print_status "success" "MVC service scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
}

main
