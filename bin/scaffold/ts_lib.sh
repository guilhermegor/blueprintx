#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=bin/lib/scaffold_git_remote.sh
source "$SCRIPT_DIR/../lib/scaffold_git_remote.sh"
# shellcheck source=bin/lib/scaffold_package_json.sh
source "$SCRIPT_DIR/../lib/scaffold_package_json.sh"

PROJECT_ROOT="${1:-}"
PROJECT_NAME="${2:-}"
PROJECT_DESCRIPTION="${3:-}"
LICENSE_CHOICE="${LICENSE_CHOICE:-MIT}"
GITHUB_USERNAME="${GITHUB_USERNAME:-}"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SKELETON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/ts-lib"
COMMON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/ts-common"
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
    prompt_read input "$(prompt_main "GitHub username (default: $DEFAULT_GITHUB_USERNAME): ")"
    if [ -n "$input" ]; then
        GITHUB_USERNAME="$input"
    else
        GITHUB_USERNAME="$DEFAULT_GITHUB_USERNAME"
    fi
    print_status "config" "GitHub username (prompt): $GITHUB_USERNAME"
}

prompt_otel() {
    local answer
    prompt_read answer "$(prompt_main "Include OpenTelemetry OTLP log export (opt-in, sends to an OTel collector)? [y/N]: ")"
    case "$answer" in
        y|Y) INCLUDE_OTEL=true; print_status "config" "OTLP log export: enabled" ;;
        *) INCLUDE_OTEL=false ;;
    esac
}

create_directory_structure() {
    local project_path="$1"

    print_status "info" "Creating directory structure..."

    mkdir -p "$project_path"/src
    mkdir -p "$project_path"/bin
    mkdir -p "$project_path"/.github/workflows
    mkdir -p "$project_path"/.vscode
    mkdir -p "$project_path"/docs

    print_status "success" "Directory structure created"
}

copy_skeleton_files() {
    local project_path="$1"

    print_status "info" "Copying ts-lib skeleton files..."

    cp -r "$SKELETON_TEMPLATE_ROOT/src/." "$project_path/src"
    cp "$SKELETON_TEMPLATE_ROOT/tsconfig.json" "$project_path/tsconfig.json"
    cp "$SKELETON_TEMPLATE_ROOT/tsconfig.esm.json" "$project_path/tsconfig.esm.json"
    cp "$SKELETON_TEMPLATE_ROOT/tsconfig.cjs.json" "$project_path/tsconfig.cjs.json"
    cp "$SKELETON_TEMPLATE_ROOT/tsconfig.types.json" "$project_path/tsconfig.types.json"
    cp "$SKELETON_TEMPLATE_ROOT/babel.config.test.cjs" "$project_path/babel.config.test.cjs"
    cp "$SKELETON_TEMPLATE_ROOT/jest.config.cjs" "$project_path/jest.config.cjs"
    cp "$SKELETON_TEMPLATE_ROOT/eslint.config.mjs" "$project_path/eslint.config.mjs"
    cp "$SKELETON_TEMPLATE_ROOT/.prettierrc.mjs" "$project_path/.prettierrc.mjs"
    cp "$SKELETON_TEMPLATE_ROOT/lint-staged.config.mjs" "$project_path/lint-staged.config.mjs"
    cp "$SKELETON_TEMPLATE_ROOT/bin/write_esm_package_json.sh" "$project_path/bin/write_esm_package_json.sh"
    cp "$SKELETON_TEMPLATE_ROOT/bin/smoke_pack.sh" "$project_path/bin/smoke_pack.sh"
    chmod +x "$project_path/bin/write_esm_package_json.sh" "$project_path/bin/smoke_pack.sh"
    cp "$SKELETON_TEMPLATE_ROOT/sidebars.js" "$project_path/sidebars.js"
    cp "$SKELETON_TEMPLATE_ROOT/.github/workflows/docs.yml" "$project_path/.github/workflows/docs.yml"
    cp "$SKELETON_TEMPLATE_ROOT/.github/workflows/docs-deploy.yml" "$project_path/.github/workflows/docs-deploy.yml"
    cp "$SKELETON_TEMPLATE_ROOT/.github/workflows/pack-smoke.yml" "$project_path/.github/workflows/pack-smoke.yml"

    print_status "success" "Skeleton files copied"
}

render_docusaurus_config() {
    local project_path="$1"
    python3 - "$SKELETON_TEMPLATE_ROOT/docusaurus.config.js" "$project_path/docusaurus.config.js" \
        "$PROJECT_NAME" "$PROJECT_DESCRIPTION" "$GITHUB_USERNAME" <<'PYEOF'
import json
import re
import sys

path_src, path_dst, str_name, str_desc, str_user = sys.argv[1:6]
with open(path_src, encoding="utf-8") as f:
    str_text = f.read()
# json.dumps returns a QUOTED literal; the template already supplies the quotes around
# ${PROJECT_DESCRIPTION}, so strip the outer pair and keep the escaping. GITHUB_USERNAME
# gets the same treatment for consistency, even though GitHub restricts usernames to
# alphanumerics/hyphens and can never actually carry a quote or backslash.
str_desc_js = json.dumps(str_desc)[1:-1].replace("'", "\\'")
str_name_js = json.dumps(str_name)[1:-1].replace("'", "\\'")
str_user_js = json.dumps(str_user)[1:-1].replace("'", "\\'")
str_replacements = {
    "${PROJECT_DESCRIPTION}": str_desc_js,
    "${PROJECT_NAME}": str_name_js,
    "${GITHUB_USERNAME}": str_user_js,
}
# Single-pass substitution: sequential .replace() calls would let a literal
# "${PROJECT_NAME}" or "${GITHUB_USERNAME}" inside the description get replaced again
# by a later iteration, once it's already sitting in the output text.
str_text = re.sub(
    r"\$\{PROJECT_DESCRIPTION\}|\$\{PROJECT_NAME\}|\$\{GITHUB_USERNAME\}",
    lambda match: str_replacements[match.group(0)],
    str_text,
)
with open(path_dst, "w", encoding="utf-8") as f:
    f.write(str_text)
PYEOF
}

render_package_json() {
    local project_path="$1"
    python3 - "$SKELETON_TEMPLATE_ROOT/package.json" "$project_path/package.json" \
        "$PROJECT_NAME" "$PROJECT_DESCRIPTION" "$PROJECT_LICENSE" "$GITHUB_USERNAME" <<'PY'
import json
import sys

path_template, path_out, str_name, str_description, str_license, str_github_username = (
    sys.argv[1:7]
)


def json_escape(value):
    """Escape a raw string for safe interpolation inside a JSON string literal."""
    return json.dumps(value)[1:-1]


with open(path_template, encoding="utf-8") as fh:
    text = fh.read()

text = text.replace("${PROJECT_NAME}", json_escape(str_name))
text = text.replace("${PROJECT_DESCRIPTION}", json_escape(str_description))
text = text.replace("${PROJECT_LICENSE}", json_escape(str_license))
# repository.url must match the GitHub repo exactly, or npm's OIDC trusted-publishing
# check fails at publish time (#135).
text = text.replace("${GITHUB_USERNAME}", json_escape(str_github_username))

json.loads(text)  # fail loudly on any render that produced invalid JSON

with open(path_out, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
}

copy_shared_ts_source() {
    local project_path="$1"
    mkdir -p "$project_path/src/utils"
    cp -r "$COMMON_TEMPLATE_ROOT/src/." "$project_path/src"
}

refresh_lockfile_for_otel() {
    local project_path="$1"
    local -a list_bound=()
    command -v timeout >/dev/null 2>&1 && list_bound=(timeout 120)
    print_status "info" "Refreshing package-lock.json for the OTLP dependencies (up to 120s)..."
    if (cd "$project_path" && ${list_bound[@]+"${list_bound[@]}"} npm install --package-lock-only --silent >/dev/null 2>&1); then
        return
    fi
    rm -f "$project_path/package-lock.json"
    print_status "warning" "lockfile refresh failed (npm missing, offline or timed out): package-lock.json omitted — run 'npm install' before the first push"
}

conditional_copy_otel() {
    local project_path="$1"
    if [[ "$INCLUDE_OTEL" != "true" ]]; then return; fi
    mkdir -p "$project_path/src/utils"
    cp "$COMMON_TEMPLATE_ROOT/optional/otel-log-emitter.ts" "$project_path/src/utils/otel-log-emitter.ts"
    cp "$COMMON_TEMPLATE_ROOT/optional/otel-log-emitter.test.ts" "$project_path/src/utils/otel-log-emitter.test.ts"
    cp "$COMMON_TEMPLATE_ROOT/docker-compose.otel-collector.yml" "$project_path/docker-compose.otel-collector.yml"
    cp "$COMMON_TEMPLATE_ROOT/otel-collector-config.yaml" "$project_path/otel-collector-config.yaml"
    patch_package_json "$project_path/package.json" dependencies \
        '@opentelemetry/api=1.9.1' \
        '@opentelemetry/api-logs=0.222.0' \
        '@opentelemetry/sdk-logs=0.222.0' \
        '@opentelemetry/exporter-logs-otlp-http=0.222.0' \
        '@opentelemetry/resources=2.11.0'
    refresh_lockfile_for_otel "$project_path"
    cat >> "$project_path/src/index.ts" <<'TSBLOCK'

// OTLP log export (opt-in, blueprintx#438) — an additional LogEmitter implementation a
// consumer wraps its own base emitter with: withOtelLogExport(NULL_EMITTER). A no-op until
// OTEL_EXPORTER_OTLP_ENDPOINT is set (see utils/otel-log-emitter.ts).
export { withOtelLogExport } from './utils/otel-log-emitter.js';
TSBLOCK
    print_status "success" "OTLP log export (src/utils/otel-log-emitter.ts) added — re-exported from src/index.ts"
    print_status "info" "Set OTEL_EXPORTER_OTLP_ENDPOINT (and optionally OTEL_SERVICE_NAME / OTEL_EXPORTER_OTLP_HEADERS) in your host's real environment to enable export"
}

copy_shared_github_overlay() {
    local project_path="$1"

    cp "$SHARED_TEMPLATE_ROOT/.editorconfig" "$project_path/.editorconfig"
    cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "$project_path/.gitattributes"
    cp "$SHARED_TEMPLATE_ROOT/.coderabbit.yaml" "$project_path/.coderabbit.yaml"
    mkdir -p "$project_path/.greptile" && cp "$SHARED_TEMPLATE_ROOT/.greptile/config.json" "$SHARED_TEMPLATE_ROOT/.greptile/graphite.md" "$BLUEPRINTX_ROOT/templates/ts-lib/.greptile/"* "$project_path/.greptile/"
    cp "$SHARED_TEMPLATE_ROOT/.github/CLAUDE.md" "$project_path/.github/CLAUDE.md"
    GITHUB_USERNAME="$GITHUB_USERNAME" envsubst '${GITHUB_USERNAME}' < "$SHARED_TEMPLATE_ROOT/.github/CODEOWNERS" > "$project_path/.github/CODEOWNERS"
    cp "$SHARED_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
    mkdir -p "$project_path/.github/ISSUE_TEMPLATE" && cp "$SHARED_TEMPLATE_ROOT/.github/ISSUE_TEMPLATE/feature_or_fix.md" "$project_path/.github/ISSUE_TEMPLATE/feature_or_fix.md"
    copy_repo_policy_workflows "$project_path"
}

copy_common_templates() {
    local project_path="$1"

    print_status "info" "Applying common TypeScript templates..."

    PROJECT_LICENSE="${LICENSE_CHOICE}"
    export PROJECT_NAME PROJECT_DESCRIPTION PROJECT_LICENSE GITHUB_USERNAME
    render_package_json "$project_path"
    envsubst '${PROJECT_NAME}' \
        < "$SKELETON_TEMPLATE_ROOT/AGENTS.md" \
        > "$project_path/AGENTS.md"
    cp "$SKELETON_TEMPLATE_ROOT/CLAUDE.md" "$project_path/CLAUDE.md"
    cp "$SHARED_TEMPLATE_ROOT/PRINCIPLES.md" "$project_path/PRINCIPLES.md"
    envsubst '${PROJECT_NAME} ${PROJECT_DESCRIPTION} ${PROJECT_LICENSE} ${GITHUB_USERNAME}' \
        < "$SKELETON_TEMPLATE_ROOT/README.md" \
        > "$project_path/README.md"

    for doc_file in index usage examples faq contributing; do
        envsubst '${PROJECT_NAME} ${PROJECT_DESCRIPTION}' \
            < "$SKELETON_TEMPLATE_ROOT/docs/$doc_file.md" \
            > "$project_path/docs/$doc_file.md"
    done
    render_docusaurus_config "$project_path"
    envsubst '${PROJECT_NAME}' \
        < "$SKELETON_TEMPLATE_ROOT/.github/workflows/release-npm.yml" \
        > "$project_path/.github/workflows/release-npm.yml"

    copy_static_ts_lib_files "$project_path"
    copy_repo_rules_provisioner "$project_path" "$COMMON_TEMPLATE_ROOT/bin/required-checks.txt"
    copy_shared_ts_source "$project_path"

    print_status "success" "Common templates applied"
}

copy_static_ts_lib_files() {
    local project_path="$1"

    cp "$COMMON_TEMPLATE_ROOT/.gitignore" "$project_path/.gitignore"
    cp "$COMMON_TEMPLATE_ROOT/.nvmrc" "$project_path/.nvmrc"
    cp "$SKELETON_TEMPLATE_ROOT/package-lock.json" "$project_path/package-lock.json"
    cp "$COMMON_TEMPLATE_ROOT/CONTRIBUTING.md" "$project_path/CONTRIBUTING.md"
    mkdir -p "$project_path/.husky"
    cp -r "$COMMON_TEMPLATE_ROOT/.husky/." "$project_path/.husky"
    chmod +x "$project_path/.husky/pre-commit" "$project_path/.husky/pre-push" 2>/dev/null || true
    cp -r "$COMMON_TEMPLATE_ROOT/.vscode/." "$project_path/.vscode"
    cp -r "$COMMON_TEMPLATE_ROOT/.github/." "$project_path/.github"
    copy_shared_github_overlay "$project_path"
    envsubst < "$LICENSES_TEMPLATE_ROOT/${LICENSE_CHOICE}" > "$project_path/LICENSE"
    cp -r "$SHARED_TEMPLATE_ROOT/.specs" "$project_path/.specs"

    mkdir -p "$project_path/bin/lib"
    cp "$SHARED_TEMPLATE_ROOT/bin/lib/common.sh" "$project_path/bin/lib/common.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/export_repo_content.sh" "$project_path/bin/export_repo_content.sh"
    chmod +x "$project_path/bin/export_repo_content.sh"

    cp "$SHARED_TEMPLATE_ROOT/bin/check_review_threads.py" "$project_path/bin/check_review_threads.py"
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

    scaffold_initial_commit "$project_path"
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
    print_status "info" "Removed .github (GitHub-only assets)"
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
    patch_package_json "$project_path/package.json" scripts \
        'git:diff:export=bash bin/git_diff_export.sh' \
        'git:diff:check=bash bin/git_diff_check.sh' \
        'git:diff:apply=bash bin/git_diff_apply.sh'
    print_status "success" "git-diff workflow enabled (npm run git:diff:export | git:diff:check | git:diff:apply)"
    commit_offline_artifacts "$project_path"
}

commit_offline_artifacts() {
    local project_path="$1"
    git -C "$project_path" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
    scaffold_commit_artifacts "$project_path" "chore: enable offline git workflow"
}


main() {
    PROJECT_PATH="$PROJECT_ROOT/$PROJECT_NAME"

    print_section "TypeScript library (ts-lib) scaffold"
    print_status "config" "Target: $PROJECT_PATH"

    validate_inputs
    resolve_github_username
    scaffold_prompt_review_bot_roster
    prompt_otel
    create_directory_structure "$PROJECT_PATH"
    copy_skeleton_files "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    conditional_copy_otel "$PROJECT_PATH"
    scaffold_prune_review_bot_roster "$PROJECT_PATH"
    scaffold_purge_caches "$PROJECT_PATH"
    scaffold_comment_budget "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    if [ "$SCAFFOLD_REMOTE_VERIFIED" != "1" ] \
        || ! git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        apply_offline_mode "$PROJECT_PATH"
    fi

    print_status "success" "ts-lib scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
    print_status "info" "Run 'npm install && npm run build && npm test' to get started"
}

main
