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
    # The prompt validates too, but the scaffolds are also callable DIRECTLY
    # (bin/ci/scaffold_lint_test.sh does exactly that), so a guard living only in
    # prompt_project_name protects one of the two entry points. blueprintx#113.
    if ! is_valid_project_name "$PROJECT_NAME"; then
        exit_error "Invalid project name '$PROJECT_NAME'. Use a letter or underscore first, then letters, digits, '-' or '_'."
    fi
    print_status "success" "Input validation passed"
}

format_display_name() {
    # Identity: the docs/README title IS the distribution name (lowercase,
    # hyphenated), mirroring filings-cvm/filings-b3 — not a title-cased variant.
    # Set PROJECT_DISPLAY_NAME explicitly before scaffolding to override.
    echo "$1"
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
    read -r -p "$(prompt_main "GitHub username (default: $DEFAULT_GITHUB_USERNAME): ")" input || true
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
    # The BOOTSTRAP installer's pin: Poetry itself plus its plugins (export, shell). Not
    # application dependencies -- bin/lib/bootstrap.sh pip-installs this file into the
    # interpreter Poetry runs from, which is the only place a Poetry plugin can be loaded.
    # ⚠️ Four of the five Python scaffolds omitted this copy, so `poetry export` shipped
    # without its plugin in every service tier while lib-minimal alone had it (blueprintx#116
    # family: each scaffold hand-maintains its own cp list, so a shared file drifts silently).
    cp "$COMMON_TEMPLATE_ROOT/requirements.txt" "$project_path/requirements.txt"
    # Per-layer import policy read by bin/check_layer_imports.py (pre-commit + CI).
    # ⚠️ Per-tier, never shared: the layer NAMES differ, and lib-minimal nests them
    # inside the distributable package (hence its src_prefix_depth). Without this file
    # the gate used to self-skip in silence, so this tier shipped with no import
    # boundary while its CI stayed green; it now FAILS instead.
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/.layer-policy.yaml" "$project_path/.layer-policy.yaml"
    cp "$SHARED_TEMPLATE_ROOT/.editorconfig" "$project_path/.editorconfig"
    cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "$project_path/.gitattributes"
    PROJECT_DISPLAY_NAME="${PROJECT_DISPLAY_NAME:-$(format_display_name "$PROJECT_NAME")}"
    PROJECT_DISPLAY_NAME="$PROJECT_DISPLAY_NAME" GITHUB_USERNAME="$GITHUB_USERNAME" \
        envsubst '${PROJECT_DISPLAY_NAME} ${GITHUB_USERNAME}' \
        < "$COMMON_TEMPLATE_ROOT/README.md" > "$project_path/README.md"
    # Ship an initial coverage.svg so the README ![Test Coverage](./coverage.svg) badge
    # resolves on the first push instead of 404-ing; regenerated by the coverage-badge hook.
    cp "$COMMON_TEMPLATE_ROOT/coverage.svg" "$project_path/coverage.svg"
    cp "$COMMON_TEMPLATE_ROOT/assets/logo_lorem_ipsum.png" "$project_path/assets/logo_lorem_ipsum.png"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/.env.example" "$project_path/.env"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/.env.example" "$project_path/.env.example"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/CLAUDE.md" "$project_path/CLAUDE.md"

    print_status "success" "Templates copied and configured"
}

copy_common_templates() {
	# The 95-line body this replaced was byte-identical across the four service
	# scaffolds except for the tier name, twice. It lives in bin/lib/scaffold_python_templates.sh
	# now; this wrapper keeps the call sites and the per-tier name in one place.
	scaffold_copy_common_templates "ddd-service-native-db" "$1"
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
    # API reference is a directory (index + one page) from day one, never a single
    # api.md — splitting it later rots published deep links (see docs/api/index.md).
    mkdir -p "$project_path/docs/api"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/docs/api/index.md" \
        "$project_path/docs/api/index.md"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/docs/api/reference.md" \
        "$project_path/docs/api/reference.md"
    # Placeholder brand image (header logo/favicon + landing hero) + its tunable CSS.
    # Swap docs/assets/logo.png for a real asset; size/position/border are inline on the <img>.
    mkdir -p "$project_path/docs/assets"
    cp "$COMMON_TEMPLATE_ROOT/assets/logo_lorem_ipsum.png" \
        "$project_path/docs/assets/logo.png"
    # Standard doc sections shared across all service tiers — single-sourced from
    # python-common/docs so every tier stays in sync.
    local doc
    for doc in usage examples faq contributing changelog; do
        cp "$COMMON_TEMPLATE_ROOT/docs/${doc}.md" "$project_path/docs/${doc}.md"
    done
    # Adds architecture.md to the gate's required-pages set (blueprintx#130) — the
    # page ships in this tier but was previously enforced by nothing.
    cp "$COMMON_TEMPLATE_ROOT/docs/.docs-skeleton.yaml" "$project_path/docs/.docs-skeleton.yaml"
    # Non-published docs/ authoring guide + the excluded backlog folder.
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/docs/CLAUDE.md" \
        "$project_path/docs/CLAUDE.md"
    mkdir -p "$project_path/docs/backlog"
    cp "$BLUEPRINTX_ROOT/templates/ddd-service-native-db/docs/backlog/.keep" \
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
        print_status "warning" "gh not authenticated; skipping main branch protection."
        return
    fi

    if ! gh repo view "$repo" >/dev/null 2>&1; then
        print_status "warning" "GitHub repo $repo not reachable; skipping branch protection."
        return
    fi

    read -r -p "$(prompt_main "Protect branch '$branch' on GitHub now? [y/N]: ")" protect_ans || true
    case "$protect_ans" in
        y|Y)
            # A solo maintainer cannot satisfy a required-approving-review
            # rule — GitHub forbids self-approval, so the first PR's merge
            # would be permanently blocked. Ask whether human reviewers will
            # gate merges, and build the protection payload accordingly.
            local reviews_json
            read -r -p "$(prompt_sub "Will human reviewers gate merges to '$branch'? [y/N]: ")" reviews_ans || true
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
                print_status "warning" "Failed to protect branch '$branch'; adjust settings manually in GitHub."
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
	# Non-zero just means "no verified remote" (#212); main already routes that to
	# offline mode via the @{u} check, so it must not abort the scaffold under `set -e`.
	scaffold_prompt_git_remote_setup "$1" || true
	# Branch protection is applied later, in commit_and_push_github_assets, only for the
	# online path and only after the .github assets have been pushed — so the asset push
	# is never blocked by the rules we are about to set.
}

prompt_docker_compose() {
    local answer db_ans
    read -r -p "$(prompt_main "Include Docker Compose for database infrastructure? [y/N]: ")" answer || true
    case "$answer" in
        y|Y)
            INCLUDE_DOCKER_COMPOSE=true
            read -r -p "$(prompt_sub "Which database backend? [postgresql/mariadb/mysql] (default: postgresql): ")" db_ans || true
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
    read -r -p "$(prompt_main "Include schema-less file storage (JSON/CSV/joblib)? [y/N]: ")" answer || true
    case "$answer" in
        y|Y) INCLUDE_STORAGE=true; print_status "config" "Schema-less storage: enabled" ;;
        *) INCLUDE_STORAGE=false ;;
    esac
}

prompt_data_dir() {
    local answer base_ans dated_ans
    read -r -p "$(prompt_main "Customise the output directory (logs/artifacts root)? [y/N]: ")" answer || true
    case "$answer" in
        y|Y)
            INCLUDE_DATA_DIR=true
            read -r -p "$(prompt_sub "Output base directory [logs]: ")" base_ans || true
            DATA_DIR_BASE="${base_ans:-logs}"
            read -r -p "$(prompt_sub "Organise output into date-named subdirectories (<base>/YYYY-MM-DD)? [y/N]: ")" dated_ans || true
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
    read -r -p "$(prompt_main "Include outbound webhook notifications? [y/N]: ")" answer || true
    case "$answer" in
        y|Y)
            INCLUDE_WEBHOOK=true
            read -r -p "$(prompt_sub "Which platform? [teams/slack/custom] (default: teams): ")" platform_ans || true
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
    cp "$COMMON_TEMPLATE_ROOT/src/config/contract_oracles.yaml" "$project_path/src/config/contract_oracles.yaml"
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
    local -a utils=(
        br_identifiers dtypes decimals logs logs_emitter text paths signatures dates
        tabular_reader xml_reader provenance sidecar_metadata retry http_downloader zip_extractor frames
        ms_office email raw_workspace daily_cache queries
        regime_window regime_registry regime_adapter spec_gap_registry
    )
    for util in "${utils[@]}"; do
        # A util is either a single module or a PACKAGE — retry/ was split into one in
        # blueprintx#116, mirroring what all four proving grounds converged on. Handling both
        # here keeps the roster ONE flat list of names instead of a second list to forget.
        if [ -d "$COMMON_TEMPLATE_ROOT/src/utils/${util}" ]; then
            # `cp -r src dst` NESTS when dst already exists (dst/retry/retry/), so copy the
            # package's CONTENTS into a directory we create. Verified: the nesting form leaves
            # a rerun with a stale, unimportable tree instead of overwriting it.
            mkdir -p "$project_path/src/utils/${util}"
            cp -r "$COMMON_TEMPLATE_ROOT/src/utils/${util}/." "$project_path/src/utils/${util}/"
        else
            cp "$COMMON_TEMPLATE_ROOT/src/utils/${util}.py" "$project_path/src/utils/${util}.py"
        fi
        if [ -f "$COMMON_TEMPLATE_ROOT/tests/unit/test_${util}.py" ]; then
            cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_${util}.py" "$project_path/tests/unit/test_${util}.py"
        fi
    done
    # ms_office/ and email/ are PACKAGES with more than one test file, one per module inside —
    # a single "test_${util}.py" above cannot name them, so each rides an explicit cp instead
    # (blueprintx#117/#118/#121). check_test_copy_lists.py's static scan requires exactly this
    # form (`cp … tests/unit/test_X.py`) to recognise a shared test as reachable.
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
    # test_regime_adapters.py covers FOUR modules (regime_window/regime_registry/
    # regime_adapter/spec_gap_registry) in one file — the loop's `test_${util}.py` naming
    # cannot name it for any single util, so it rides an explicit cp like ms_office/email above.
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_regime_adapters.py" \
        "$project_path/tests/unit/test_regime_adapters.py"
    # A COUNT, never an enumeration: the old message listed 15 of the 17 names and had already
    # drifted (lesson `ci-python-gates` — the enumeration is what goes stale). The number still
    # proves the step ran, which silence would not.
    print_status "success" "Shared utils + their tests applied (${#utils[@]} modules)"
}

# Runtime type-checking engine — single source in python-common/optional/typing.
# DDD keeps the canonical chassis.typing import prefix, so it is copied as-is to
# src/chassis/typing (no rewrite; the MVC tiers vendor it under utils/typing).
copy_typing_chassis() {
    local project_path="$1"
    mkdir -p "$project_path/src/chassis/typing" "$project_path/tests/unit"
    cp -r "$COMMON_TEMPLATE_ROOT/optional/typing/." "$project_path/src/chassis/typing"
    # The engine's unit test resolves the layout through its own import shim, so the
    # same file serves the chassis (DDD) and utils (MVC) placements.
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_typing.py" "$project_path/tests/unit/test_typing.py"
    print_status "success" "Runtime type-checking engine (chassis/typing) + test applied"
}

# chassis/db is the DatabaseHandler ABC that db_schema (and db_wschema) extend.
# Native db_schema requires it, so it is always injected here.
copy_required_chassis_db() {
    local project_path="$1"
    cp -r "$COMMON_TEMPLATE_ROOT/optional/chassis/db" "$project_path/src/chassis/db"
    print_status "success" "chassis/db copied (required by db_schema)"
}

# blueprintx#274: prune each declined opt-in's dependency line from the just-rendered
# pyproject.toml — joblib is imported only by chassis/db_wschema (storage opt-in), pymsteams
# only by optional/webhook (webhook opt-in).
conditional_prune_optin_deps() {
    local project_path="$1"
    scaffold_prune_optin_dependency "$project_path" "$INCLUDE_STORAGE" \
        '/^# Used only by the schema-less-storage opt-in/,/^joblib = /d'
    scaffold_prune_optin_dependency "$project_path" "$INCLUDE_WEBHOOK" \
        '/^# Microsoft Teams incoming-webhook transport/,/^pymsteams = /d'
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
    # GitGuardian secret-scanning gate (blueprintx#153). GitHub-only, like tests.yaml.
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/secret_scan.yaml" "$project_path/.github/workflows/secret_scan.yaml"
    # Re-evaluates on pull_request_review / pull_request_review_comment, so a thread opened
    # after the last push is still checked — a push-only trigger goes stale exactly then.
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/review_threads.yaml" "$project_path/.github/workflows/review_threads.yaml"
    # Its other half: the gate above fails a PR nobody reviewed, and this asks for the review.
    # A new repo has 0 stars, so CodeRabbit declines to review it automatically BY CONSTRUCTION
    # — ship the gate without the trigger and every PR blocks; ship the trigger without the
    # gate and nothing notices when it stops working. GitHub-only, hence here.
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/coderabbit_trigger.yaml" "$project_path/.github/workflows/coderabbit_trigger.yaml"
    # Its THIRD half, and the reason the pair above is survivable: a rate-limited reviewer
    # declines the trigger, the gate then correctly blocks, and nothing re-asks. This retries on
    # a schedule (the only trigger that fires while a PR merely WAITS). It relaxes no verdict —
    # measured upstream, 19 rate-limited PRs and 18 reviewed in the end, so it is a delay to
    # automate rather than an unavailability to forgive. GitHub-only.
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/review_retry.yaml" "$project_path/.github/workflows/review_retry.yaml"
    # PR quality gate (classify by path, sticky comment, native auto-merge) + the reconciler
    # that closes linked issues of BOT-merged PRs (a bot merge suppresses both the issue close
    # and delete_branch_on_merge). GitHub-only, like tests.yaml.
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/pr-gate.yaml" "$project_path/.github/workflows/pr-gate.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/pr-reconcile.yaml" "$project_path/.github/workflows/pr-reconcile.yaml"
    # Weekly, non-gating contract-drift check (opens/updates an issue on schema drift). GitHub-only.
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/contract_drift.yaml" "$project_path/.github/workflows/contract_drift.yaml"
    # Tag + GitHub Release (no PyPI — a service is deployed, not published). GitHub-only.
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/release.yaml" "$project_path/.github/workflows/release.yaml"
    # Docs → GitHub Pages deploy (build + gh-deploy on push to the default branch). GitHub-only.
    cp "$SHARED_TEMPLATE_ROOT/docs_version/docs.yaml" "$project_path/.github/workflows/docs.yaml"
    envsubst '${GITHUB_USERNAME}' < "$SHARED_TEMPLATE_ROOT/.github/CODEOWNERS" > "$project_path/.github/CODEOWNERS"
    # SECURITY.md (root; GitHub auto-detects it and flips "Security policy" to Enabled) +
    # dependabot.yml (ordinary VERSION bumps; SECURITY updates are a toggle set by
    # bin/enable_security.sh). Both are GitHub-platform features, hence GitHub-only.
    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' \
        < "$SHARED_TEMPLATE_ROOT/SECURITY.md" > "$project_path/SECURITY.md"
    cp "$COMMON_TEMPLATE_ROOT/.github/dependabot.yml" "$project_path/.github/dependabot.yml"
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

# Webhook notify is the final lifecycle step, expressed as bootstrap.notify() rather than a
# loose post-teardown tail: add `notify` to the bootstrap import (only when chosen, so there
# is no unused import otherwise) and call it last with the production-gated notifier
# (CLS_WEBHOOK when ENV passes the gate, else None). main.py stays a thin
# bootstrap → wire → run → teardown → notify script.
conditional_patch_main_py() {
    local project_path="$1"
    local main_path="$project_path/src/main.py"
    if [[ "$INCLUDE_WEBHOOK" != "true" ]]; then return; fi
    awk '
        /^from app\.bootstrap import / {
            print "from app.bootstrap import cls_create_log, init, notify, teardown"
            next
        }
        { print }
    ' "$main_path" > "$main_path.tmp" && mv "$main_path.tmp" "$main_path"
    cat >> "$main_path" <<'PYBLOCK'

# ─── NOTIFY ───────────────────────────────────────────────────────────────────
from src.config.startup import (  # noqa: E402
	BOOL_WEBHOOK_ENABLED,
	CLS_WEBHOOK,
	MSG_WEBHOOK,
)


notify(CLS_WEBHOOK if BOOL_WEBHOOK_ENABLED else None, MSG_WEBHOOK)
PYBLOCK
    print_status "success" "Webhook notify wired as the final lifecycle step (main.py)"
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
    read -r -p "$(prompt_main "Include an outbound e-mail handler (Outlook/SMTP)? [y/N]: ")" answer || true
    case "$answer" in
        y | Y)
            INCLUDE_EMAIL=true
            read -r -p "$(prompt_sub "Which backend? [outlook/smtp] (default: outlook): ")" backend_ans || true
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
# where it needs to notify (the Outlook backend injects utils.ms_office.outlook_gateway by default).
conditional_copy_email() {
    local project_path="$1"
    if [[ "$INCLUDE_EMAIL" != "true" ]]; then return; fi
    cp -r "$COMMON_TEMPLATE_ROOT/optional/email" "$project_path/src/chassis/email"
    # The seam ships its unit test co-located; relocate it to the project's tests/unit (the
    # canonical chassis.email imports already match the DDD layout, so no rewrite is needed).
    mv "$project_path/src/chassis/email/tests/unit/test_email_handlers.py" \
        "$project_path/tests/unit/test_email_handlers.py"
    rm -rf "$project_path/src/chassis/email/tests"
    local email_env
    email_env=$'\n# E-mail handler (opt-in). EMAIL_BACKEND: outlook (Windows desktop) or smtp.\n# SENDER_EMAIL is the From address; SMTP_* are used only when EMAIL_BACKEND=smtp.\nSENDER_EMAIL=\nEMAIL_BACKEND='"$EMAIL_BACKEND"$'\nSMTP_HOST=\nSMTP_PORT=587\nSMTP_USER=\nSMTP_PASSWORD=\nSMTP_USE_TLS=true\n# Dispatch defaults (fallback for every emails.yaml block; override per block with\n# EMAIL_SEND__<BLOCK> / EMAIL_AUTO_SEND__<BLOCK>, block key upper-cased). Send on, auto-send off.\nEMAIL_SEND__DEFAULTS=true\nEMAIL_AUTO_SEND__DEFAULTS=false\n'
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
    # Offline-only tasks. add_poe_include wires the fragment in only when it is copied:
    # poe warns on every invocation for a missing include, unlike make's silent -include.
    cp "$SHARED_TEMPLATE_ROOT/poe_tasks.offline.toml" "$project_path/poe_tasks.offline.toml"
    add_poe_include "$project_path" "poe_tasks.offline.toml"
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
    conditional_prune_optin_deps "$PROJECT_PATH"
    conditional_copy_docker_compose "$PROJECT_PATH"
    conditional_copy_storage "$PROJECT_PATH"
    conditional_patch_inputs_yaml "$PROJECT_PATH"
    apply_env_wise_config "$PROJECT_PATH"
    conditional_copy_webhooks_yaml "$PROJECT_PATH"
    conditional_copy_email "$PROJECT_PATH"
    conditional_patch_startup "$PROJECT_PATH"
    conditional_patch_main_py "$PROJECT_PATH"
    copy_mkdocs_templates "$PROJECT_PATH"
    # Every `cp -r` above copies whatever sits in templates/, caches included (#205).
    scaffold_purge_caches "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    # GitHub-only assets exist iff a GitHub remote was established. With an upstream
    # tracking branch → copy .github; otherwise switch to the offline git-diff workflow.
    # ⚠️ `@{u}` alone answers "is there an upstream?", never "is it OUR upstream?" — it is TRUE
    # for a pre-existing clone whose origin points elsewhere, and this branch pushes to it.
    # SCAFFOLD_REMOTE_VERIFIED is the missing half (#212, raised by review on #215).
    if [ "$SCAFFOLD_REMOTE_VERIFIED" = "1" ] \
        && git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        copy_github_assets "$PROJECT_PATH"
        # Online: releases are cut by tagging via release.yaml, not a hand-bump. Offline keeps
        # make bump_version (cz bump). Strip BEFORE the assets commit so its Makefile/tasks.sh
        # edits are swept into the same commit+push (no leftover uncommitted files).
        strip_bump_version "$PROJECT_PATH"
        commit_and_push_github_assets "$PROJECT_PATH"
    else
        apply_offline_mode "$PROJECT_PATH"
    fi

    print_status "success" "Hex-service scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
}

main
