#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=bin/lib/scaffold_git_remote.sh
source "$SCRIPT_DIR/../lib/scaffold_git_remote.sh"
# shellcheck source=bin/lib/scaffold_provenance.sh
source "$SCRIPT_DIR/../lib/scaffold_provenance.sh"

PROJECT_ROOT="$1"
PROJECT_NAME="$2"
PROJECT_PKG_NAME="$(to_import_package_name "$PROJECT_NAME")"
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
INCLUDE_LOGS=false
INCLUDE_OTEL=false
PUBLISH_PYPI=true
PUBLISH_TEST_PYPI=true
CONSUME_PRIVATE=false


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

    mkdir -p "$project_path"/src/"$PROJECT_PKG_NAME"/_internal/utils/typing
    mkdir -p "$project_path"/src/"$PROJECT_PKG_NAME"/_internal/config/contracts
    mkdir -p "$project_path"/src/"$PROJECT_PKG_NAME"/_internal/config/ports
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

    PROJECT_NAME="$PROJECT_NAME" envsubst '${PROJECT_NAME}' \
        < "$BLUEPRINTX_ROOT/templates/lib-minimal/rendered/package__init__.py.tmpl" \
        > "$project_path/src/$PROJECT_PKG_NAME/__init__.py"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/main.py" "$project_path/src/$PROJECT_PKG_NAME/main.py"

    mkdir -p "$project_path/tests/unit"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_fixture_scope_gate.py" "$project_path/tests/unit/test_fixture_scope_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_one_assert_gate.py" "$project_path/tests/unit/test_one_assert_gate.py"

    PROJECT_PKG_NAME="$PROJECT_PKG_NAME" envsubst '${PROJECT_PKG_NAME}' \
        < "$BLUEPRINTX_ROOT/templates/lib-minimal/rendered/test_main.py.tmpl" \
        > "$project_path/tests/unit/test_main.py"

    PROJECT_PKG_NAME="$PROJECT_PKG_NAME" envsubst '${PROJECT_PKG_NAME}' \
        < "$BLUEPRINTX_ROOT/templates/lib-minimal/rendered/test_typing.py.tmpl" \
        > "$project_path/tests/unit/test_typing.py"

    print_status "success" "Python files created"
}

rewrite_internal_imports() {
    local internal_dir="$1"
    local pkg_prefix="${PROJECT_PKG_NAME}._internal"
    local file
    while IFS= read -r file; do
        sed_inplace -E \
            -e "s@^([[:space:]]*)(from|import) utils\.@\1\2 ${pkg_prefix}.utils.@" \
            -e "s@^([[:space:]]*)(from|import) config\.@\1\2 ${pkg_prefix}.config.@" \
            -e "s@^([[:space:]]*)(from|import) ports\.@\1\2 ${pkg_prefix}.config.ports.@" \
            -e "s@^([[:space:]]*)(from|import) chassis\.typing@\1\2 ${pkg_prefix}.utils.typing@" \
            "$file"
    done < <(grep -rlE "^[[:space:]]*(from|import) (utils|config|ports|chassis)\." "$internal_dir" 2>/dev/null)
}

copy_internal_otel() {
    local internal_dir="$1"
    local test_path="$2/tests/unit/test_otel_logging.py"
    if [[ "$INCLUDE_OTEL" != "true" ]]; then return; fi
    cp "$COMMON_TEMPLATE_ROOT/optional/otel_logging.py" "$internal_dir/utils/otel_logging.py"
    cp "$COMMON_TEMPLATE_ROOT/optional/test_otel_logging.py" "$test_path"
    sed_inplace -E "s@^( +)from (utils|chassis)\.otel_logging@\1from ${PROJECT_PKG_NAME}._internal.utils.otel_logging@" "$test_path"
}

copy_internal_utils() {
    local project_path="$1"
    local internal_dir="$project_path/src/$PROJECT_PKG_NAME/_internal"
    local utils_src="$COMMON_TEMPLATE_ROOT/src/utils"
    local -a modules=(
        __init__.py dtypes.py br_identifiers.py http_downloader.py
        tabular_reader.py xml_reader.py provenance.py sidecar_metadata.py text.py
        zip_extractor.py raw_workspace.py daily_cache.py
        regime_window.py regime_registry.py regime_adapter.py spec_gap_registry.py
    )
    local -a packages=(retry)
    if [[ "$INCLUDE_LOGS" == "true" ]]; then
        modules+=(logs.py logs_emitter.py)
    fi
    local module

    printf '"""Private internals of the %s package (not a public API)."""\n' "$PROJECT_PKG_NAME" \
        > "$internal_dir/__init__.py"
    for module in "${modules[@]}"; do
        cp "$utils_src/$module" "$internal_dir/utils/$module"
    done
    local package
    for package in "${packages[@]}"; do
        mkdir -p "$internal_dir/utils/$package"
        cp -r "$utils_src/$package/." "$internal_dir/utils/$package/"
    done
    cp -r "$COMMON_TEMPLATE_ROOT/optional/typing/." "$internal_dir/utils/typing"
    copy_internal_otel "$internal_dir" "$project_path"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/utils_CLAUDE.md" "$internal_dir/utils/CLAUDE.md"

    rewrite_internal_imports "$internal_dir"

    mkdir -p "$project_path/tests/unit"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_regime_adapters.py" \
        "$project_path/tests/unit/test_regime_adapters.py"
    rewrite_internal_imports "$project_path/tests/unit"

    print_status "success" "Private internal utils (_internal/utils) applied"
}

copy_internal_config() {
    local project_path="$1"
    local internal_dir="$project_path/src/$PROJECT_PKG_NAME/_internal"
    local config_src="$COMMON_TEMPLATE_ROOT/src/config"

    printf '"""Private configuration internals (data contracts) of %s."""\n' "$PROJECT_PKG_NAME" \
        > "$internal_dir/config/__init__.py"
    cp "$config_src/contracts/__init__.py" "$internal_dir/config/contracts/__init__.py"
    cp "$config_src/contracts/example_source.py" "$internal_dir/config/contracts/example_source.py"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/config_CLAUDE.md" "$internal_dir/config/CLAUDE.md"

    rewrite_internal_imports "$internal_dir"
    print_status "success" "Private internal config (_internal/config/contracts) applied"
}

copy_internal_ports() {
    local project_path="$1"
    local internal_dir="$project_path/src/$PROJECT_PKG_NAME/_internal"
    local ports_src="$COMMON_TEMPLATE_ROOT/optional/ports"

    cp "$ports_src/__init__.py" "$internal_dir/config/ports/__init__.py"
    cp "$ports_src/example_port.py" "$internal_dir/config/ports/example_port.py"

    rewrite_internal_imports "$internal_dir"
    print_status "success" "Private internal ports (_internal/config/ports) applied"
}

add_library_badges() {
    local project_path="$1"
    local readme="$project_path/README.md"
    [ -f "$readme" ] || return 0
    python3 - "$readme" <<'PY'
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    lines = fh.readlines()

if any("PyPI Version" in ln for ln in lines):
    sys.exit(0)  # already added — idempotent

badges = [
    "![PyPI Version](https://img.shields.io/pypi/v/${PYPI_NAME})\n",
    "[![Snyk Vulnerabilities](https://snyk.io/test/github/${GITHUB_USERNAME}/${PROJECT_SLUG}/badge.svg)]"
    "(https://snyk.io/test/github/${GITHUB_USERNAME}/${PROJECT_SLUG})\n",
    "[![Snyk License](https://snyk.io/advisor/python/${PYPI_NAME}/badge.svg)]"
    "(https://snyk.io/advisor/python/${PYPI_NAME})\n",
    "![PyPI Downloads](https://static.pepy.tech/badge/${PYPI_NAME})\n",
]

out: list[str] = []
inserted = False
for ln in lines:
    out.append(ln)
    if not inserted and "Python Version" in ln and "img.shields.io" in ln:
        out.extend(badges)
        inserted = True
if not inserted:  # no anchor found: prepend after the first badge line instead
    for i, ln in enumerate(out):
        if "img.shields.io" in ln or "repostatus.org" in ln:
            out[i + 1 : i + 1] = badges
            break

with open(path, "w", encoding="utf-8") as fh:
    fh.writelines(out)
PY
    print_status "success" "Library PyPI/Snyk badges added to README"
}

copy_templates() {
    local project_path="$1"

    print_status "info" "Copying templates..."

    cp "$COMMON_TEMPLATE_ROOT/.gitignore" "$project_path/.gitignore"
    cp "$COMMON_TEMPLATE_ROOT/.python-version" "$project_path/.python-version"
    cp "$SHARED_TEMPLATE_ROOT/.editorconfig" "$project_path/.editorconfig"
    cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "$project_path/.gitattributes"
    cp "$SHARED_TEMPLATE_ROOT/.coderabbit.yaml" "$project_path/.coderabbit.yaml"
    mkdir -p "$project_path/.greptile" && cp "$SHARED_TEMPLATE_ROOT/.greptile/config.json" "$BLUEPRINTX_ROOT/templates/lib-minimal/.greptile/"* "$project_path/.greptile/"
    PROJECT_DISPLAY_NAME="${PROJECT_DISPLAY_NAME:-$(format_display_name "$PROJECT_NAME")}"
    PROJECT_DISPLAY_NAME="$PROJECT_DISPLAY_NAME" envsubst '${PROJECT_DISPLAY_NAME}' < "$COMMON_TEMPLATE_ROOT/README.md" > "$project_path/README.md"
    cp "$COMMON_TEMPLATE_ROOT/coverage.svg" "$project_path/coverage.svg"
    add_library_badges "$project_path"
    cp "$COMMON_TEMPLATE_ROOT/assets/logo_lorem_ipsum.png" "$project_path/assets/logo_lorem_ipsum.png"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/CLAUDE.md" "$project_path/CLAUDE.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/AGENTS.md" "$project_path/AGENTS.md"
    mkdir -p "$project_path/.claude"
    cp "$SHARED_TEMPLATE_ROOT/CLAUDE.md" "$project_path/.claude/CLAUDE.md"
    cp "$SHARED_TEMPLATE_ROOT/PRINCIPLES.md" "$project_path/PRINCIPLES.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.coveragerc" "$project_path/.coveragerc"
    cp "$COMMON_TEMPLATE_ROOT/CHANGELOG.md" "$project_path/CHANGELOG.md"

    print_status "success" "Templates copied and configured"
}

lib_minimal_render_pyproject() {
    local project_path="$1"


    print_status "info" "Applying common Python templates..."

    HOMEPAGE="${HOMEPAGE:-https://example.com/${PROJECT_NAME}}"
    REPOSITORY="${REPOSITORY:-https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}}"
    BUG_REPORTS_URL="${BUG_REPORTS_URL:-${REPOSITORY}/issues}"
    SOURCE_URL="${SOURCE_URL:-${REPOSITORY}}"

    COPYRIGHT_YEAR="$(date +%Y)"
    AUTHOR_NAME="${GITHUB_USERNAME}"
    PROJECT_LICENSE="${LICENSE_CHOICE}"
    case "$PROJECT_LICENSE" in
        MIT) PROJECT_LICENSE_CLASSIFIER="License :: OSI Approved :: MIT License" ;;
        Apache-2.0) PROJECT_LICENSE_CLASSIFIER="License :: OSI Approved :: Apache Software License" ;;
        GPL-3.0) PROJECT_LICENSE_CLASSIFIER="License :: OSI Approved :: GNU General Public License v3 (GPLv3)" ;;
        *) PROJECT_LICENSE_CLASSIFIER="License :: OSI Approved" ;;
    esac

    export PROJECT_NAME PROJECT_PKG_NAME PROJECT_VERSION PROJECT_DESCRIPTION \
        PROJECT_DISPLAY_NAME HOMEPAGE REPOSITORY BUG_REPORTS_URL SOURCE_URL GITHUB_USERNAME \
        COPYRIGHT_YEAR AUTHOR_NAME PROJECT_LICENSE PROJECT_LICENSE_CLASSIFIER
    envsubst < "$BLUEPRINTX_ROOT/templates/lib-minimal/pyproject.toml" > "$project_path/pyproject.toml"
}

lib_minimal_copy_tooling_configs() {
    local project_path="$1"

    cp "$COMMON_TEMPLATE_ROOT/.pre-commit-config.yaml" "$project_path/.pre-commit-config.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.pydocstyle" "$project_path/.pydocstyle"
    cp "$COMMON_TEMPLATE_ROOT/requirements.txt" "$project_path/requirements.txt"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.layer-policy.yaml" "$project_path/.layer-policy.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.codespellrc" "$project_path/.codespellrc"
    if [[ "${INCLUDE_REVIEW_BOT_ROSTER:-true}" == "true" ]]; then
        cp "$COMMON_TEMPLATE_ROOT/.review-bots.yaml" "$project_path/.review-bots.yaml"
    fi
    cp "$COMMON_TEMPLATE_ROOT/mypy.ini" "$project_path/mypy.ini"
    cp "$COMMON_TEMPLATE_ROOT/.sqlfluff" "$project_path/.sqlfluff"
    cp "$COMMON_TEMPLATE_ROOT/.sqlfluffignore" "$project_path/.sqlfluffignore"
    cp "$COMMON_TEMPLATE_ROOT/.hadolint.yaml" "$project_path/.hadolint.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.yamllint" "$project_path/.yamllint"
    cp "$COMMON_TEMPLATE_ROOT/.shellcheckrc" "$project_path/.shellcheckrc"
    cp "$COMMON_TEMPLATE_ROOT/CONTRIBUTING.md" "$project_path/CONTRIBUTING.md"
    envsubst < "$LICENSES_TEMPLATE_ROOT/${LICENSE_CHOICE}" > "$project_path/LICENSE"
    cp "$COMMON_TEMPLATE_ROOT/poe_tasks.toml" "$project_path/poe_tasks.toml"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/poe_tasks.library.toml" \
        "$project_path/poe_tasks.library.toml"
    add_poe_include "$project_path" "poe_tasks.library.toml"
    cp "$COMMON_TEMPLATE_ROOT/pytest.ini" "$project_path/pytest.ini"
    cp "$COMMON_TEMPLATE_ROOT/ruff.toml" "$project_path/ruff.toml"
    cp "$COMMON_TEMPLATE_ROOT/poetry.toml" "$project_path/poetry.toml"
    cp "$COMMON_TEMPLATE_ROOT/.cz.toml" "$project_path/.cz.toml"
}

lib_minimal_copy_github_assets() {
    local project_path="$1"

    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/tests.yaml" "$project_path/.github/workflows/tests.yaml"
    if [ -n "${GITGUARDIAN_API_KEY:-}" ]; then
        cp "$COMMON_TEMPLATE_ROOT/.github/workflows/secret_scan.yaml" "$project_path/.github/workflows/secret_scan.yaml"
    fi
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/review_threads.yaml" "$project_path/.github/workflows/review_threads.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/coderabbit_trigger.yaml" "$project_path/.github/workflows/coderabbit_trigger.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/review_retry.yaml" "$project_path/.github/workflows/review_retry.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/pr-gate.yaml" "$project_path/.github/workflows/pr-gate.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/pr-reconcile.yaml" "$project_path/.github/workflows/pr-reconcile.yaml"
    if [[ "$PUBLISH_PYPI" == "true" ]]; then
        envsubst '${PROJECT_NAME} ${GITHUB_USERNAME}' \
            < "$BLUEPRINTX_ROOT/templates/lib-minimal/.github/workflows/release-pypi.yaml" \
            > "$project_path/.github/workflows/release-pypi.yaml"
    fi
    if [[ "$PUBLISH_TEST_PYPI" == "true" ]]; then
        envsubst '${PROJECT_NAME} ${GITHUB_USERNAME}' \
            < "$BLUEPRINTX_ROOT/templates/lib-minimal/.github/workflows/release-test-pypi.yaml" \
            > "$project_path/.github/workflows/release-test-pypi.yaml"
    fi
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.github/workflows/docs.yaml" \
        "$project_path/.github/workflows/docs.yaml"
    GITHUB_USERNAME="$GITHUB_USERNAME" envsubst '${GITHUB_USERNAME}' < "$SHARED_TEMPLATE_ROOT/.github/CODEOWNERS" > "$project_path/.github/CODEOWNERS"
    # dependabot.yml (ordinary VERSION bumps; SECURITY updates are a toggle set by
    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' \
        < "$SHARED_TEMPLATE_ROOT/SECURITY.md" > "$project_path/SECURITY.md"
    cp "$COMMON_TEMPLATE_ROOT/.github/dependabot.yml" "$project_path/.github/dependabot.yml"
    cp "$SHARED_TEMPLATE_ROOT/.github/CLAUDE.md" "$project_path/.github/CLAUDE.md"
    cp "$SHARED_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
    mkdir -p "$project_path/.github/ISSUE_TEMPLATE" && cp "$SHARED_TEMPLATE_ROOT/.github/ISSUE_TEMPLATE/feature_or_fix.md" "$project_path/.github/ISSUE_TEMPLATE/feature_or_fix.md"
    copy_repo_policy_workflows "$project_path"
}

lib_minimal_copy_gate_tests() {
    local project_path="$1"

    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_layer_imports_gate.py" \
        "$project_path/tests/unit/test_layer_imports_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_comment_language_gate.py" \
        "$project_path/tests/unit/test_comment_language_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_sql_guards_gate.py" \
        "$project_path/tests/unit/test_sql_guards_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_identifier_masking_gate.py" \
        "$project_path/tests/unit/test_identifier_masking_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_orm_model_guards_gate.py" \
        "$project_path/tests/unit/test_orm_model_guards_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_gate_integrity_gate.py" \
        "$project_path/tests/unit/test_gate_integrity_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_coverage_floor_gate.py" \
        "$project_path/tests/unit/test_coverage_floor_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_function_length_gate.py" \
        "$project_path/tests/unit/test_function_length_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_template_drift_gate.py" \
        "$project_path/tests/unit/test_template_drift_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_comment_budget_gate.py" \
        "$project_path/tests/unit/test_comment_budget_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_env_docs_sync_gate.py" \
        "$project_path/tests/unit/test_env_docs_sync_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_quality_rules_gate.py" \
        "$project_path/tests/unit/test_quality_rules_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_wheelhouse_select.py" \
        "$project_path/tests/unit/test_wheelhouse_select.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_review_threads_gate.py" \
        "$project_path/tests/unit/test_review_threads_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_review_retry.py" \
        "$project_path/tests/unit/test_review_retry.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_docs_code_refs_gate.py" \
        "$project_path/tests/unit/test_docs_code_refs_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_assertion_weakening_gate.py" \
        "$project_path/tests/unit/test_assertion_weakening_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_rmw_race_gate.py" \
        "$project_path/tests/unit/test_rmw_race_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_ruff_ret_rule.py" \
        "$project_path/tests/unit/test_ruff_ret_rule.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_migration_slug_gate.py" \
        "$project_path/tests/unit/test_migration_slug_gate.py"
}

lib_minimal_copy_project_scaffolding() {
    local project_path="$1"

    cp "$COMMON_TEMPLATE_ROOT/.gitlint" "$project_path/.gitlint"
    cp -r "$COMMON_TEMPLATE_ROOT/bin/." "$project_path/bin"
    mkdir -p "$project_path/tests/integration"
    cp "$COMMON_TEMPLATE_ROOT/tests/integration/test_bin_scripts.py" \
        "$project_path/tests/integration/test_bin_scripts.py"
    rm -f "$project_path/tests/integration/.keep"
    mkdir -p "$project_path/tests/unit"
    cp "$COMMON_TEMPLATE_ROOT/tests/CLAUDE.md" "$project_path/tests/CLAUDE.md"
    cp "$COMMON_TEMPLATE_ROOT/tests/conftest.py" "$project_path/tests/conftest.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_pr_gate.py" \
        "$project_path/tests/unit/test_pr_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_backlog_ledger.py" \
        "$project_path/tests/unit/test_backlog_ledger.py"
    lib_minimal_copy_gate_tests "$project_path"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_pip_requirements.py" \
        "$project_path/tests/unit/test_pip_requirements.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_family_convention_example.py" \
        "$project_path/tests/unit/test_family_convention_example.py"
    cp "$SHARED_TEMPLATE_ROOT/bin/export_repo_content.sh" "$project_path/bin/export_repo_content.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/ship.sh" "$project_path/bin/ship.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/commit.sh" "$project_path/bin/commit.sh"
    chmod +x "$project_path/bin/export_repo_content.sh" "$project_path/bin/ship.sh" "$project_path/bin/commit.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/check_review_threads.py" "$project_path/bin/check_review_threads.py"
    cp -r "$SHARED_TEMPLATE_ROOT/.specs" "$project_path/.specs"
    mkdir -p "$project_path/.specs/backlog"
    touch "$project_path/.specs/backlog/.gitkeep"
    cp "$BLUEPRINTX_ROOT"/bin/ci/{check_specs_structure.sh,check_docs_boundary.sh,check_required_checks_sync.py} "$project_path/bin/"
    chmod +x "$project_path"/bin/check_{specs_structure,docs_boundary}.sh
    mkdir -p "$project_path/dist"
    cp "$SHARED_TEMPLATE_ROOT/dist/.keep" "$project_path/dist/.keep"
    mkdir -p "$project_path/.vscode"
    cp "$COMMON_TEMPLATE_ROOT/.vscode/settings.json" "$project_path/.vscode/settings.json"
    cp "$COMMON_TEMPLATE_ROOT/.vscode/extensions.json" "$project_path/.vscode/extensions.json"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.vscode/tasks.json" "$project_path/.vscode/tasks.json"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.vscode/tasks.json" "$project_path/.vscode/tasks.json"
}

copy_common_templates() {
    local project_path="$1"

    print_status "info" "Applying common Python templates..."
    lib_minimal_render_pyproject "$project_path"
    lib_minimal_copy_tooling_configs "$project_path"
    lib_minimal_copy_github_assets "$project_path"
    lib_minimal_copy_project_scaffolding "$project_path"
    scaffold_stamp_provenance lib-minimal "$project_path"
    print_status "success" "Common templates applied"
}

copy_mkdocs_templates() {
    local project_path="$1"

    print_status "info" "Copying MkDocs templates..."

    export DOCS_LOCALE="${DOCS_LOCALE:-en}"
    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY} ${DOCS_LOCALE}' \
        < "$BLUEPRINTX_ROOT/templates/lib-minimal/mkdocs.yml" \
        > "$project_path/mkdocs.yml"
    envsubst '${PROJECT_DISPLAY_NAME}' \
        < "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/index.md" \
        > "$project_path/docs/index.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/usage.md" \
        "$project_path/docs/usage.md"
    mkdir -p "$project_path/docs/api"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/api/index.md" \
        "$project_path/docs/api/index.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/api/reference.md" \
        "$project_path/docs/api/reference.md"
    mkdir -p "$project_path/docs/assets"
    cp "$COMMON_TEMPLATE_ROOT/assets/logo_lorem_ipsum.png" \
        "$project_path/docs/assets/logo.png"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/examples.md" \
        "$project_path/docs/examples.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/faq.md" \
        "$project_path/docs/faq.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/contributing.md" \
        "$project_path/docs/contributing.md"
    cp "$COMMON_TEMPLATE_ROOT/docs/changelog.md" \
        "$project_path/docs/changelog.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/CLAUDE.md" \
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

    protect_ans=""
    prompt_read protect_ans "$(prompt_main "Protect branch '$branch' on GitHub now? [y/N]: ")"
    case "$protect_ans" in
        y|Y)
            local reviews_approvals
            reviews_ans=""
            prompt_read reviews_ans "$(prompt_sub "Will human reviewers gate merges to '$branch'? [y/N]: ")"
            case "$reviews_ans" in
                y|Y)
                    reviews_approvals=1
                    ;;
                *)
                    reviews_approvals=0
                    ;;
            esac
            (cd "$project_path" && RULESET_APPROVALS="$reviews_approvals" bash bin/enable_repo_rules.sh)
            ;;
        *) print_status "info" "Skipped branch protection";;
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
	SCAFFOLD_REPO_HOMEPAGE="https://${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}.github.io/${PROJECT_NAME}/"
	if scaffold_prompt_git_remote_setup "$1"; then
		apply_branch_protection "$1"
	fi
}

apply_offline_mode() {
    local project_path="$1"

    print_status "info" "No GitHub remote connected — switching to offline mode"
    rm -rf "$project_path/.github"
    remove_repo_policy_scripts "$project_path"
    print_status "info" "Removed .github (GitHub-only assets)"
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

commit_online_artifacts() {
    local project_path="$1"
    git -C "$project_path" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
    [ -n "$(git -C "$project_path" status --porcelain)" ] || return 0
    git -C "$project_path" add -A
    git -C "$project_path" commit -q --no-verify -m "chore: apply tag-driven versioning and docs URL" || true
    git -C "$project_path" push >/dev/null 2>&1 \
        || print_status "warning" "Could not push versioning changes; run 'git push' manually."
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

apply_online_tag_versioning() {
    local project_path="$1"
    local pyproject="$project_path/pyproject.toml"
    [ -f "$pyproject" ] || return 0
    python3 - "$pyproject" "$PROJECT_VERSION" <<'PY'
import sys

path, version = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as fh:
    text = fh.read()

# 1) Stub the version — the real one is derived from the git tag at build time.
text = text.replace(f'version = "{version}"', 'version = "0.0.0"', 1)

# 2) Insert the dynamic-versioning config just before [build-system].
dynamic_block = (
    "[tool.poetry-dynamic-versioning]\n"
    "# Published version is derived from the latest git tag matching `v$version` (e.g. v0.2.0). On\n"
    "# an exact tag the build is clean (0.2.0); off-tag builds get a PEP 440 dev version. The CI\n"
    "# release workflows pass POETRY_DYNAMIC_VERSIONING_BYPASS to build a specific version. Needs\n"
    "# `python -m build` (a PEP 517 frontend), not `poetry build` (which ignores the backend).\n"
    "enable = true\n"
    'vcs = "git"\n'
    'style = "pep440"\n'
    "\n"
    "[build-system]\n"
)
text = text.replace("[build-system]\n", dynamic_block, 1)

# 3) Swap to the poetry-dynamic-versioning build backend.
text = text.replace(
    'requires = ["poetry-core>=1.7.0"]',
    'requires = ["poetry-core>=1.7.0", "poetry-dynamic-versioning>=1.4.0,<2.0.0"]',
)
text = text.replace(
    'build-backend = "poetry.core.masonry.api"',
    'build-backend = "poetry_dynamic_versioning.backend"',
)

with open(path, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
    strip_bump_version "$project_path"
    print_status "success" "Online: tag-driven versioning (poetry-dynamic-versioning); make bump_version removed"
}

apply_online_docs_url() {
    local project_path="$1"
    local pyproject="$project_path/pyproject.toml"
    [ -f "$pyproject" ] || return 0
    local docs_url="https://${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}.github.io/${PROJECT_NAME}/"
    python3 - "$pyproject" "$docs_url" <<'PY'
import re
import sys

path, docs = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as fh:
    text = fh.read()

# homepage -> the docs site.
text = re.sub(r'^homepage = ".*"$', f'homepage = "{docs}"', text, count=1, flags=re.M)
# Add a documentation field right after homepage (if not already present).
if "documentation = " not in text:
    text = re.sub(
        r'(^homepage = ".*"\n)',
        rf'\1documentation = "{docs}"\n',
        text,
        count=1,
        flags=re.M,
    )
# Add a Documentation entry under [tool.poetry.urls] (after the existing "K" = "V" lines).
if '"Documentation"' not in text:
    text = re.sub(
        r'(\[tool\.poetry\.urls\]\n(?:"[^"]+" = "[^"]*"\n)*)',
        rf'\1"Documentation" = "{docs}"\n',
        text,
        count=1,
    )

with open(path, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
    print_status "success" "Online: docs website URL wired into pyproject ($docs_url)"
}

prompt_logs() {
    local answer
    prompt_read answer "$(prompt_main "Include the in-repo logging helper (utils/logs.py)? [y/N]: ")"
    case "$answer" in
        y|Y) INCLUDE_LOGS=true; print_status "config" "logs.py: included" ;;
        *)   INCLUDE_LOGS=false ;;
    esac
}

prompt_otel() {
    local answer
    prompt_read answer "$(prompt_main "Include OpenTelemetry OTLP log export (opt-in, sends to an OTel collector)? [y/N]: ")"
    case "$answer" in
        y|Y) INCLUDE_OTEL=true; print_status "config" "OTLP log export: enabled" ;;
        *)   INCLUDE_OTEL=false ;;
    esac
}

conditional_pyproject_otel() {
    local project_path="$1"
    if [[ "$INCLUDE_OTEL" != "true" ]]; then return; fi
    local pyproject="$project_path/pyproject.toml"
    sed_inplace '/^defusedxml = ">=0.7"/a\
# OpenTelemetry OTLP log export (opt-in, blueprintx#438) — pinned; the Logs signal is\
# "Development" status upstream (see _internal/utils/otel_logging.py). The consumer'"'"'s own\
# host process sets OTEL_EXPORTER_OTLP_ENDPOINT — this library ships no .env.\
opentelemetry-api = "==1.44.0"\
opentelemetry-sdk = "==1.44.0"\
opentelemetry-exporter-otlp-proto-http = "==1.44.0"' "$pyproject"
    print_status "success" "OTLP log export (_internal/utils/otel_logging.py) added — call configure_otel_logging(your_logger) to wire it"
}

prompt_publish_targets() {
    local answer
    print_status "section" "Publishing — where this library ships to"
    prompt_read answer "$(prompt_main "Publish to the official public registry (PyPI)? [Y/n]: ")"
    case "$answer" in n | N) PUBLISH_PYPI=false ;; *) PUBLISH_PYPI=true ;; esac
    print_status "config" "Publish target PyPI: $PUBLISH_PYPI"

    prompt_read answer "$(prompt_main "Add a staging/sandbox registry (Test PyPI) first? [Y/n]: ")"
    case "$answer" in n | N) PUBLISH_TEST_PYPI=false ;; *) PUBLISH_TEST_PYPI=true ;; esac
    print_status "config" "Staging registry Test PyPI: $PUBLISH_TEST_PYPI"

    print_status "section" "Consuming — where this library's own dependencies come from"
    prompt_read answer "$(prompt_main "Consume this library from a non-official source (private index / git)? [y/N]: ")"
    case "$answer" in y | Y) CONSUME_PRIVATE=true ;; *) CONSUME_PRIVATE=false ;; esac
    print_status "config" "Private consumer source: $CONSUME_PRIVATE"
}

apply_private_consumer_source() {
    local project_path="$1"
    [[ "$CONSUME_PRIVATE" == "true" ]] || return 0
    local pyproject="$project_path/pyproject.toml"
    [ -f "$pyproject" ] || return 0
    cat >> "$pyproject" <<'EOF'

# --- Private / non-official consumer source (uncomment and fill in) --------------------------
# Install this package from a source other than PyPI (a private PEP 503 index, or a git source).
# Use priority = "explicit" so poetry/pip NEVER falls back to it for other packages — the
# dependency-confusion guard. Authenticate with:
#   poetry config http-basic.private <user> <token>
# and, for pip, use --index-url (never --extra-index-url).
# [[tool.poetry.source]]
# name = "private"
# url = "https://your-private-index.example/simple/"
# priority = "explicit"
EOF
    print_status "success" "Q3: private consumer-source template appended to pyproject.toml"
}

prompt_docker_compose() {
    local answer db_ans
    prompt_read answer "$(prompt_main "Include Docker Compose for database infrastructure? [y/N]: ")"
    case "$answer" in
        y|Y)
            INCLUDE_DOCKER_COMPOSE=true
            prompt_read db_ans "$(prompt_sub "Which database backend? [postgresql/mariadb/mysql] (default: postgresql): ")"
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

conditional_copy_docker_compose() {
    local project_path="$1"
    if [[ "$INCLUDE_DOCKER_COMPOSE" != "true" ]]; then return; fi
    cp "$COMMON_TEMPLATE_ROOT/docker-compose.${DB_COMPOSE_BACKEND}.yml" "$project_path/docker-compose.yml"
    print_status "success" "docker-compose.yml (${DB_COMPOSE_BACKEND}) copied"
}


main() {
    PROJECT_PATH="$PROJECT_ROOT/$PROJECT_NAME"

    print_section "Python lib-minimal scaffold"
    print_status "config" "Target: $PROJECT_PATH"

    validate_inputs
    resolve_github_username
    prompt_logs
    prompt_otel
    prompt_docker_compose
    prompt_publish_targets
    scaffold_prompt_review_bot_roster
    PROJECT_DISPLAY_NAME="$(format_display_name "$PROJECT_NAME")"
    create_directory_structure "$PROJECT_PATH"
    create_python_files "$PROJECT_PATH"
    copy_internal_utils "$PROJECT_PATH"
    copy_internal_config "$PROJECT_PATH"
    copy_internal_ports "$PROJECT_PATH"
    copy_templates "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    conditional_pyproject_otel "$PROJECT_PATH"
    apply_private_consumer_source "$PROJECT_PATH"
    conditional_copy_docker_compose "$PROJECT_PATH"
    copy_mkdocs_templates "$PROJECT_PATH"
    scaffold_purge_caches "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    if [ "$SCAFFOLD_REMOTE_VERIFIED" != "1" ] \
        || ! git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        apply_offline_mode "$PROJECT_PATH"
    else
        apply_online_tag_versioning "$PROJECT_PATH"
        apply_online_docs_url "$PROJECT_PATH"
        if [[ -f "$PROJECT_PATH/.github/workflows/release.yaml" ]]; then
            rm -f "$PROJECT_PATH/.github/workflows/release.yaml"
            print_status "success" "Library: generic service release.yaml removed (uses release-pypi instead)"
        fi
        commit_online_artifacts "$PROJECT_PATH"
    fi

    print_status "success" "Lib-minimal scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
}

main
