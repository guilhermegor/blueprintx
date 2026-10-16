#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=bin/lib/scaffold_git_remote.sh
source "$SCRIPT_DIR/../lib/scaffold_git_remote.sh"
# shellcheck source=bin/lib/scaffold_package_json.sh
source "$SCRIPT_DIR/../lib/scaffold_package_json.sh"

PROJECT_ROOT="$1"
PROJECT_NAME="$2"
PROJECT_DESCRIPTION="${3:-}"
LICENSE_CHOICE="${LICENSE_CHOICE:-MIT}"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SKELETON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/react-spa-webpack"
COMMON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/ts-common"
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
    if [ -n "$input" ]; then
        GITHUB_USERNAME="$input"
    else
        GITHUB_USERNAME="$DEFAULT_GITHUB_USERNAME"
    fi
    print_status "config" "GitHub username (prompt): $GITHUB_USERNAME"
}

prompt_state_management() {
    echo ""
    print_status "info" "State management strategy:"
    echo "  1) React Context  (zero deps, default)"
    echo "  2) Zustand        (lightweight store)"
    echo "  3) Redux Toolkit  (enterprise, RTK Query)"
    prompt_read sm_choice "$(prompt_main "Choice [1]: ")"
    STATE_MGMT_CHOICE="${sm_choice:-1}"
    case "$STATE_MGMT_CHOICE" in
        1) print_status "config" "State management: React Context" ;;
        2) print_status "config" "State management: Zustand" ;;
        3) print_status "config" "State management: Redux Toolkit" ;;
        *) print_status "warning" "Invalid choice; defaulting to React Context"
           STATE_MGMT_CHOICE=1 ;;
    esac
}

prompt_deploy_target() {
    echo ""
    print_status "info" "Deploy target for the built SPA:"
    echo "  1) GitHub Pages  (no extra secrets; served under /<repo-name>/)"
    echo "  2) Vercel        (needs VERCEL_TOKEN / VERCEL_ORG_ID / VERCEL_PROJECT_ID)"
    echo "  3) None          (no deploy workflow)"
    prompt_read deploy_choice "$(prompt_main "Choice [1]: ")"
    DEPLOY_TARGET_CHOICE="${deploy_choice:-1}"
    case "$DEPLOY_TARGET_CHOICE" in
        1) print_status "config" "Deploy target: GitHub Pages" ;;
        2) print_status "config" "Deploy target: Vercel"
           print_status "warning" "Create the Vercel project first, then add the three repository secrets."
           print_status "info" "  gh secret set VERCEL_TOKEN; gh secret set VERCEL_ORG_ID; gh secret set VERCEL_PROJECT_ID" ;;
        3) print_status "config" "Deploy target: none" ;;
        *) print_status "warning" "Invalid choice; defaulting to GitHub Pages"
           DEPLOY_TARGET_CHOICE=1 ;;
    esac
}

prompt_module_federation() {
    echo ""
    prompt_yes_no USE_MODULE_FEDERATION "$(prompt_main "Enable Webpack Module Federation? [y/N]: ")"
    if [ "$USE_MODULE_FEDERATION" = "true" ]; then
        print_status "config" "Module Federation: enabled"
    else
        print_status "config" "Module Federation: disabled"
    fi
}

prompt_docker() {
    echo ""
    prompt_yes_no USE_DOCKER "$(prompt_main "Add a Docker setup (multi-stage build → nginx)? [y/N]: ")"
    if [ "$USE_DOCKER" = "true" ]; then
        print_status "config" "Docker: enabled (Dockerfile + nginx.conf + .dockerignore)"
    else
        print_status "config" "Docker: disabled"
    fi
}

prompt_js_copy_delivery() {
    echo ""
    prompt_yes_no USE_JS_COPY_DELIVERY "$(prompt_main "Ship a plain-JavaScript delivery copy script (js-copy)? [y/N]: ")"
    if [ "$USE_JS_COPY_DELIVERY" = "true" ]; then
        print_status "config" "JS-copy delivery: enabled (npm run js-copy:build / js-copy:verify)"
    else
        print_status "config" "JS-copy delivery: disabled"
    fi
}

prompt_otel() {
    echo ""
    prompt_yes_no INCLUDE_OTEL "$(prompt_main "Include OpenTelemetry OTLP log export (opt-in, sends to an OTel collector)? [y/N]: ")"
    if [ "$INCLUDE_OTEL" = "true" ]; then
        print_status "config" "OTLP log export: enabled"
    fi
}

create_directory_structure() {
    local project_path="$1"

    print_status "info" "Creating directory structure..."

    mkdir -p "$project_path"/src
    mkdir -p "$project_path"/public
    mkdir -p "$project_path"/docs
    mkdir -p "$project_path"/.github/workflows
    mkdir -p "$project_path"/.vscode

    print_status "success" "Directory structure created"
}

copy_skeleton_files() {
    local project_path="$1"

    print_status "info" "Copying React SPA skeleton files..."

    cp -r "$SKELETON_TEMPLATE_ROOT/src/." "$project_path/src"
    cp -r "$SKELETON_TEMPLATE_ROOT/public/." "$project_path/public"
    mkdir -p "$project_path/tests/e2e"
    cp -r "$SKELETON_TEMPLATE_ROOT/tests/." "$project_path/tests"
    cp "$SKELETON_TEMPLATE_ROOT/.babelrc" "$project_path/.babelrc"
    cp "$SKELETON_TEMPLATE_ROOT/eslint.config.js" "$project_path/eslint.config.js"
    cp "$SKELETON_TEMPLATE_ROOT/.prettierrc.js" "$project_path/.prettierrc.js"
    cp "$SKELETON_TEMPLATE_ROOT/tsconfig.json" "$project_path/tsconfig.json"
    cp "$SKELETON_TEMPLATE_ROOT/webpack.config.js" "$project_path/webpack.config.js"
    cp "$SKELETON_TEMPLATE_ROOT/lint-staged.config.js" "$project_path/lint-staged.config.js"

    cp "$SKELETON_TEMPLATE_ROOT/.env.example" "$project_path/.env"
    cp "$SKELETON_TEMPLATE_ROOT/.env.example" "$project_path/.env.example"
    cp "$SKELETON_TEMPLATE_ROOT/docs/configuration.md" "$project_path/docs/configuration.md"

    print_status "success" "Skeleton files copied"
}

apply_docker_files() {
    local project_path="$1"

    if [ "${USE_DOCKER:-false}" != "true" ]; then
        return
    fi

    print_status "info" "Adding Docker setup (multi-stage build → nginx)..."
    cp "$SKELETON_TEMPLATE_ROOT/Dockerfile" "$project_path/Dockerfile"
    cp "$SKELETON_TEMPLATE_ROOT/nginx.conf" "$project_path/nginx.conf"
    cp "$SKELETON_TEMPLATE_ROOT/.dockerignore" "$project_path/.dockerignore"
    print_status "success" "Docker files added — build with: docker build --secret id=env,src=.env -t ${PROJECT_NAME} ."
}

apply_js_copy_delivery() {
    local project_path="$1"
    local js_copy_root="$SKELETON_TEMPLATE_ROOT/optional/js-copy"

    if [ "${USE_JS_COPY_DELIVERY:-false}" != "true" ]; then
        return
    fi

    print_status "info" "Adding plain-JavaScript delivery copy scripts..."
    mkdir -p "$project_path/scripts"
    cp "$js_copy_root/emit-js-copy.mjs" "$project_path/scripts/emit-js-copy.mjs"
    cp "$js_copy_root/verify-js-copy.mjs" "$project_path/scripts/verify-js-copy.mjs"

    patch_package_json "$project_path/package.json" scripts \
        'js-copy:build=node scripts/emit-js-copy.mjs' \
        'js-copy:verify=node scripts/verify-js-copy.mjs' \
        'js-copy=npm run js-copy:build && npm run js-copy:verify'

    printf '\n# js-copy delivery script output (npm run js-copy:build)\n/js-copy/\n' \
        >> "$project_path/.gitignore"
    sed_inplace "s#'\*\*/dist/\*\*',#'**/dist/**',\n      '**/js-copy/**',#" \
        "$project_path/eslint.config.js"
    sed_inplace "s#  // 9. Prettier config#  // 9. scripts/ (js-copy delivery tooling) — Node CLI, not app code\n  {\n    files: ['scripts/**/*.mjs'],\n    languageOptions: { globals: { ...globals.node } },\n  },\n\n  // 10. Prettier config#" \
        "$project_path/eslint.config.js"

    print_status "success" "JS-copy delivery scripts added"
}

apply_file_variants() {
    local project_path="$1"
    local capabilities_path="$project_path/src/capabilities/example"
    local application_path="$capabilities_path/application"

    print_status "info" "Applying state management variant files..."

    case "$STATE_MGMT_CHOICE" in
        2)
            STATE_MANAGEMENT_VARIANT="Zustand"
            STATE_MANAGEMENT_DESC="use-cases.ts is a Zustand store (create<Store>()). State and async actions are co-located; the store is a singleton not tied to the React tree."
            STATE_MANAGEMENT_ANTIPATTERN="Don't create more than one Zustand store per capability — merge new actions into the existing store."
            mv "$application_path/use-cases.zustand.ts" "$application_path/use-cases.ts"
            mv "$capabilities_path/context.zustand.tsx" "$capabilities_path/context.tsx"
            mv "$capabilities_path/use-context.zustand.ts" "$capabilities_path/use-context.ts"
            rm -f "$application_path/use-cases.rtk.ts" \
                  "$capabilities_path/context.rtk.tsx" \
                  "$capabilities_path/use-context.rtk.ts"
            ;;
        3)
            STATE_MANAGEMENT_VARIANT="Redux Toolkit"
            STATE_MANAGEMENT_DESC="use-cases.ts is an RTK slice with createAsyncThunk actions. initialState, reducers, and thunks are co-located in one file."
            STATE_MANAGEMENT_ANTIPATTERN="Don't dispatch actions outside of thunks or hooks — keep all side effects inside the RTK layer."
            mv "$application_path/use-cases.rtk.ts" "$application_path/use-cases.ts"
            mv "$capabilities_path/context.rtk.tsx" "$capabilities_path/context.tsx"
            mv "$capabilities_path/use-context.rtk.ts" "$capabilities_path/use-context.ts"
            rm -f "$application_path/use-cases.zustand.ts" \
                  "$capabilities_path/context.zustand.tsx" \
                  "$capabilities_path/use-context.zustand.ts"
            ;;
        *)
            STATE_MANAGEMENT_VARIANT="React Context"
            STATE_MANAGEMENT_DESC="use-cases.ts exports one custom hook per use-case (useState + useCallback). Each hook owns its loading, error, and result state."
            STATE_MANAGEMENT_ANTIPATTERN="Don't lift hook state into a shared module — each hook is intentionally isolated."
            rm -f "$application_path/use-cases.zustand.ts" \
                  "$application_path/use-cases.rtk.ts" \
                  "$capabilities_path/context.zustand.tsx" \
                  "$capabilities_path/context.rtk.tsx" \
                  "$capabilities_path/use-context.zustand.ts" \
                  "$capabilities_path/use-context.rtk.ts"
            ;;
    esac

    if [ "$USE_MODULE_FEDERATION" = "true" ]; then
        print_status "info" "Applying Module Federation webpack config..."
        cp "$SKELETON_TEMPLATE_ROOT/webpack.mf.config.js" "$project_path/webpack.config.js"
        sed_inplace "s/__APP_NAME__/$PROJECT_NAME/g" "$project_path/webpack.config.js"
    fi

    print_status "success" "File variants applied"
}

apply_package_variants() {
    local project_path="$1"

    case "$STATE_MGMT_CHOICE" in
        2)
            print_status "info" "Adding Zustand dependency..."
            patch_package_json "$project_path/package.json" dependencies \
                'zustand=^5.0.0'
            ;;
        3)
            print_status "info" "Adding Redux Toolkit dependencies..."
            patch_package_json "$project_path/package.json" dependencies \
                '@reduxjs/toolkit=^2.0.0' 'react-redux=^9.0.0'
            ;;
        *) ;;
    esac

    print_status "success" "Package variants applied"
}

copy_deploy_target() {
    local project_path="$1"
    local deploy_root="$SKELETON_TEMPLATE_ROOT/optional/deploy"

    case "$DEPLOY_TARGET_CHOICE" in
        1) cp "$deploy_root/pages/deploy-spa.yml" "$project_path/.github/workflows/deploy-spa.yml"
           print_status "success" "GitHub Pages deploy workflow added" ;;
        2) cp "$deploy_root/vercel/deploy-vercel.yml" "$project_path/.github/workflows/deploy-vercel.yml"
           cp "$deploy_root/vercel/vercel.json" "$project_path/vercel.json"
           print_status "success" "Vercel deploy workflow + vercel.json added" ;;
        *) print_status "info" "No deploy workflow added" ;;
    esac
}

copy_shared_ts_source() {
    local project_path="$1"
    mkdir -p "$project_path/src/shared/utils"
    cp -r "$COMMON_TEMPLATE_ROOT/src/." "$project_path/src/shared"
}

wire_otel_composition_root() {
    local project_path="$1"
    local context_file="$project_path/src/capabilities/example/context.tsx"

    if [[ ! -f "$context_file" ]]; then
        print_status "warning" "OTEL: $context_file not found — composition root NOT wired"
        return
    fi
    if ! grep -q 'new ConsoleNotifier(CONSOLE_EMITTER)' "$context_file"; then
        print_status "warning" \
            "OTEL: composition root does not match the expected shape — NOT wired. Wrap it by hand: withOtelLogExport(CONSOLE_EMITTER)"
        return
    fi
    sed_inplace \
        -e "s#^import { CONSOLE_EMITTER } from '@/shared/utils/log-emitter';#&\\nimport { withOtelLogExport } from '@/shared/utils/otel-log-emitter';#" \
        -e 's#new ConsoleNotifier(CONSOLE_EMITTER)#new ConsoleNotifier(withOtelLogExport(CONSOLE_EMITTER))#' \
        "$context_file"
    print_status "success" "OTEL: composition root wired (withOtelLogExport(CONSOLE_EMITTER))"
}

conditional_copy_otel() {
    local project_path="$1"
    if [[ "$INCLUDE_OTEL" != "true" ]]; then return; fi
    mkdir -p "$project_path/src/shared/utils"
    cp "$COMMON_TEMPLATE_ROOT/optional/otel-log-emitter.ts" "$project_path/src/shared/utils/otel-log-emitter.ts"
    cp "$COMMON_TEMPLATE_ROOT/optional/otel-log-emitter.test.ts" "$project_path/src/shared/utils/otel-log-emitter.test.ts"
    cp "$COMMON_TEMPLATE_ROOT/docker-compose.otel-collector.yml" "$project_path/docker-compose.otel-collector.yml"
    cp "$COMMON_TEMPLATE_ROOT/otel-collector-config.yaml" "$project_path/otel-collector-config.yaml"
    patch_package_json "$project_path/package.json" dependencies \
        '@opentelemetry/api=1.9.1' \
        '@opentelemetry/api-logs=0.222.0' \
        '@opentelemetry/sdk-logs=0.222.0' \
        '@opentelemetry/exporter-logs-otlp-http=0.222.0' \
        '@opentelemetry/resources=2.11.0'
    cat "$COMMON_TEMPLATE_ROOT/optional/otel.env.fragment" >> "$project_path/.env"
    cat "$COMMON_TEMPLATE_ROOT/optional/otel.env.fragment" >> "$project_path/.env.example"
    cat "$COMMON_TEMPLATE_ROOT/optional/otel.config.md" >> "$project_path/docs/configuration.md"
    wire_otel_composition_root "$project_path"
    print_status "success" "OTLP log export (src/shared/utils/otel-log-emitter.ts) added"
    print_status "info" "Set OTEL_EXPORTER_OTLP_ENDPOINT (and optionally OTEL_SERVICE_NAME) in .env to enable export — leave OTEL_EXPORTER_OTLP_HEADERS blank (see the fragment's warning)"
}

copy_static_ts_common_files() {
    local project_path="$1"

    cp "$COMMON_TEMPLATE_ROOT/.gitignore" "$project_path/.gitignore"
    cp "$COMMON_TEMPLATE_ROOT/.nvmrc" "$project_path/.nvmrc"
    cp "$COMMON_TEMPLATE_ROOT/.stylelintrc.json" "$project_path/.stylelintrc.json"
    cp "$COMMON_TEMPLATE_ROOT/jest.config.cjs" "$project_path/jest.config.cjs"
    cp "$COMMON_TEMPLATE_ROOT/jest.setup.ts" "$project_path/jest.setup.ts"
    cp "$COMMON_TEMPLATE_ROOT/playwright.config.ts" "$project_path/playwright.config.ts"
    cp "$COMMON_TEMPLATE_ROOT/CONTRIBUTING.md" "$project_path/CONTRIBUTING.md"
    mkdir -p "$project_path/.husky"
    cp -r "$COMMON_TEMPLATE_ROOT/.husky/." "$project_path/.husky"
    chmod +x "$project_path/.husky/pre-commit" "$project_path/.husky/pre-push" 2>/dev/null || true
    cp -r "$COMMON_TEMPLATE_ROOT/.vscode/." "$project_path/.vscode"
    cp -r "$COMMON_TEMPLATE_ROOT/.github/." "$project_path/.github"
    cp "$SHARED_TEMPLATE_ROOT/.editorconfig" "$project_path/.editorconfig"
    cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "$project_path/.gitattributes"
    cp "$SHARED_TEMPLATE_ROOT/.coderabbit.yaml" "$project_path/.coderabbit.yaml"
    mkdir -p "$project_path/.greptile" && cp "$SHARED_TEMPLATE_ROOT/.greptile/config.json" "$BLUEPRINTX_ROOT/templates/react-spa-webpack/.greptile/"* "$project_path/.greptile/"
    cp "$SHARED_TEMPLATE_ROOT/.github/CLAUDE.md" "$project_path/.github/CLAUDE.md"
    GITHUB_USERNAME="$GITHUB_USERNAME" envsubst '${GITHUB_USERNAME}' < "$SHARED_TEMPLATE_ROOT/.github/CODEOWNERS" > "$project_path/.github/CODEOWNERS"
    cp "$SHARED_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
    mkdir -p "$project_path/.github/ISSUE_TEMPLATE" && cp "$SHARED_TEMPLATE_ROOT/.github/ISSUE_TEMPLATE/feature_or_fix.md" "$project_path/.github/ISSUE_TEMPLATE/feature_or_fix.md"
    copy_repo_policy_workflows "$project_path"
    cp -r "$SHARED_TEMPLATE_ROOT/.specs" "$project_path/.specs"
}

refresh_lockfile_for_variants() {
	local project_path="$1"
	if [[ "$STATE_MANAGEMENT" == "none" ]]; then
		return
	fi
	if ! command -v npm >/dev/null 2>&1; then
		rm -f "$project_path/package-lock.json"
		print_status "warning" \
			"npm not found: package-lock.json omitted for the '$STATE_MANAGEMENT' variant — run 'npm install' before the first push"
		return
	fi
	print_status "info" "Refreshing package-lock.json for the '$STATE_MANAGEMENT' variant..."
	if (cd "$project_path" && npm install --package-lock-only --silent >/dev/null 2>&1); then
		print_status "success" "package-lock.json matches the patched package.json"
	else
		rm -f "$project_path/package-lock.json"
		print_status "warning" \
			"lockfile refresh failed (offline?): package-lock.json omitted — run 'npm install' before the first push"
	fi
}

copy_common_templates() {
    local project_path="$1"

    print_status "info" "Applying common TypeScript templates..."

    PROJECT_LICENSE="${LICENSE_CHOICE}"
    export PROJECT_NAME PROJECT_DESCRIPTION PROJECT_LICENSE GITHUB_USERNAME \
           STATE_MANAGEMENT_VARIANT STATE_MANAGEMENT_DESC STATE_MANAGEMENT_ANTIPATTERN
    envsubst '${PROJECT_NAME} ${PROJECT_DESCRIPTION}' \
        < "$COMMON_TEMPLATE_ROOT/package.json" \
        > "$project_path/package.json"
    cp "$COMMON_TEMPLATE_ROOT/package-lock.json" "$project_path/package-lock.json"
    envsubst '${PROJECT_NAME} ${STATE_MANAGEMENT_VARIANT} ${STATE_MANAGEMENT_DESC} ${STATE_MANAGEMENT_ANTIPATTERN}' \
        < "$SKELETON_TEMPLATE_ROOT/AGENTS.md" \
        > "$project_path/AGENTS.md"
    cp "$SKELETON_TEMPLATE_ROOT/CLAUDE.md" "$project_path/CLAUDE.md"
    cp "$SHARED_TEMPLATE_ROOT/PRINCIPLES.md" "$project_path/PRINCIPLES.md"
    envsubst '${PROJECT_NAME} ${PROJECT_DESCRIPTION} ${PROJECT_LICENSE} ${GITHUB_USERNAME} ${STATE_MANAGEMENT_VARIANT}' \
        < "$SKELETON_TEMPLATE_ROOT/README.md" \
        > "$project_path/README.md"

    copy_static_ts_common_files "$project_path"
    if [ -d "$SKELETON_TEMPLATE_ROOT/.github" ]; then
        cp -r "$SKELETON_TEMPLATE_ROOT/.github/." "$project_path/.github"
    fi
    copy_deploy_target "$project_path"
    envsubst < "$LICENSES_TEMPLATE_ROOT/${LICENSE_CHOICE}" > "$project_path/LICENSE"

    mkdir -p "$project_path/bin/lib"
    cp "$SHARED_TEMPLATE_ROOT/bin/lib/common.sh" "$project_path/bin/lib/common.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/export_repo_content.sh" "$project_path/bin/export_repo_content.sh"
    chmod +x "$project_path/bin/export_repo_content.sh"

    cp "$SHARED_TEMPLATE_ROOT/bin/check_review_threads.py" "$project_path/bin/check_review_threads.py"
    copy_repo_rules_provisioner "$project_path" "$COMMON_TEMPLATE_ROOT/bin/required-checks.txt"

    copy_shared_ts_source "$project_path"

    print_status "success" "Common templates applied"
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

pages_prerequisites_met() {
    local repo="$1"

    command -v gh >/dev/null 2>&1 || return 1
    gh auth status >/dev/null 2>&1 || return 1
    gh repo view "$repo" >/dev/null 2>&1 || return 1
}

wait_for_gh_pages_branch() {
    local repo="$1" manual_cmd="$2"
    local attempts=0
    local max_attempts=12
    local wait_ans

    gh api "/repos/$repo/branches/gh-pages" >/dev/null 2>&1 && return 0

    print_status "info" "The 'gh-pages' branch doesn't exist yet — the first deploy creates it (~1-3 min)."
    prompt_yes_no wait_ans "$(prompt_main "Wait for the first deploy and enable Pages automatically? [Y/n]: ")" y
    if [ "$wait_ans" != "true" ]; then
        print_status "info" "After the first deploy finishes, enable Pages with:"
        print_status "info" "  $manual_cmd"
        return 1
    fi

    while [ "$attempts" -lt "$max_attempts" ]; do
        sleep 15
        gh api "/repos/$repo/branches/gh-pages" >/dev/null 2>&1 && return 0
        attempts=$((attempts + 1))
        print_status "info" "Still waiting for the first deploy... (${attempts}/${max_attempts})"
    done

    print_status "warning" "The 'gh-pages' branch still isn't there — the first deploy may still be running or it failed."
    print_status "info" "Check the run, then enable Pages with:"
    print_status "info" "  $manual_cmd"
    return 1
}

enable_gh_pages() {
    local repo="$1" owner="$2" manual_cmd="$3"

    if gh api --method POST "/repos/$repo/pages" \
        -f 'source[branch]=gh-pages' -f 'source[path]=/' >/dev/null 2>&1; then
        print_status "success" "GitHub Pages enabled — live at https://$owner.github.io/${PROJECT_NAME}/ in ~1 min."
    elif gh api "/repos/$repo/pages" >/dev/null 2>&1; then
        print_status "success" "GitHub Pages already enabled — https://$owner.github.io/${PROJECT_NAME}/"
    else
        print_status "warning" "Could not enable Pages automatically."
        print_status "info" "  $manual_cmd"
    fi
}

prompt_pages_setup() {
    local owner="${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}"
    local repo="$owner/${PROJECT_NAME}"
    local manual_cmd="gh api -X POST repos/$repo/pages -f 'source[branch]=gh-pages' -f 'source[path]=/'"
    local pages_ans

    pages_prerequisites_met "$repo" || return

    print_status "info" "GitHub Pages must be enabled once per repo (GitHub no longer auto-enables it on gh-pages pushes)."
    prompt_yes_no pages_ans "$(prompt_main "Enable GitHub Pages (deploy from gh-pages branch) now? [y/N]: ")"
    if [ "$pages_ans" != "true" ]; then
        print_status "info" "Skipped GitHub Pages setup"
        return
    fi

    wait_for_gh_pages_branch "$repo" "$manual_cmd" || return
    enable_gh_pages "$repo" "$owner" "$manual_cmd"
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
		[ "$DEPLOY_TARGET_CHOICE" = "1" ] && prompt_pages_setup
	fi
}

apply_offline_mode() {
    local project_path="$1"

    print_status "info" "No GitHub remote connected — switching to offline mode"
    rm -rf "$project_path/.github"
    remove_repo_policy_scripts "$project_path"
    print_status "info" "Removed .github (GitHub-only assets)"
    if [ -f "$project_path/vercel.json" ]; then
        rm -f "$project_path/vercel.json"
        print_status "info" "Removed vercel.json (its deploy workflow went with .github)"
    fi
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
    if git -C "$project_path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        scaffold_commit_artifacts "$project_path" "chore: enable offline git workflow"
    fi
}


main() {
    PROJECT_PATH="$PROJECT_ROOT/$PROJECT_NAME"

    print_section "React SPA (Webpack) scaffold"
    print_status "config" "Target: $PROJECT_PATH"

    validate_inputs
    resolve_github_username
    scaffold_prompt_review_bot_roster
    prompt_state_management
    prompt_deploy_target
    prompt_module_federation
    prompt_docker
    prompt_js_copy_delivery
    prompt_otel
    create_directory_structure "$PROJECT_PATH"
    copy_skeleton_files "$PROJECT_PATH"
    apply_docker_files "$PROJECT_PATH"
    apply_file_variants "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    conditional_copy_otel "$PROJECT_PATH"
    scaffold_prune_review_bot_roster "$PROJECT_PATH"
    apply_package_variants "$PROJECT_PATH"
    refresh_lockfile_for_variants "$PROJECT_PATH"
    apply_js_copy_delivery "$PROJECT_PATH"
    scaffold_purge_caches "$PROJECT_PATH"
    scaffold_comment_budget "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    if [ "$SCAFFOLD_REMOTE_VERIFIED" != "1" ] \
        || ! git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        apply_offline_mode "$PROJECT_PATH"
    fi

    print_status "success" "React SPA scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
    print_status "info" "Run 'npm install && npm start' to begin development"
}

main
