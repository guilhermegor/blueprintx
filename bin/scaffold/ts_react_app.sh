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
# Language-agnostic assets shared by every skeleton (CODEOWNERS, PR template)
SHARED_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/common"
LICENSES_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/licenses"
DEFAULT_GITHUB_USERNAME="${GITHUB_USERNAME:-your-github-username}"


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
    # No terminal on stdin: skip the read entirely rather than let a stray pipe line
    # answer as a username — falls straight to DEFAULT_GITHUB_USERNAME below (#539).
    if [ -t 0 ]; then
        read -r -p "$(prompt_main "GitHub username (default: $DEFAULT_GITHUB_USERNAME): ")" input || true
    fi
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
    # No terminal on stdin: skip the read so a stray pipe line can't pick a variant nobody
    # chose — falls straight to the "1" default below (#539).
    if [ -t 0 ]; then
        read -r -p "$(prompt_main "Choice [1]: ")" sm_choice || true
    fi
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
    # ⚠️ ONE target, never both. Each workflow triggers on `push: branches: [main]`, so
    # shipping both deploys twice on every merge, to two URLs, with nothing saying which is
    # canonical. The choice is made here so only one workflow ever reaches the project.
    echo ""
    print_status "info" "Deploy target for the built SPA:"
    echo "  1) GitHub Pages  (no extra secrets; served under /<repo-name>/)"
    echo "  2) Vercel        (needs VERCEL_TOKEN / VERCEL_ORG_ID / VERCEL_PROJECT_ID)"
    echo "  3) None          (no deploy workflow)"
    # No terminal on stdin: skip the read so a stray pipe line can't pick a deploy target
    # nobody chose — falls straight to the "1" default below (#539).
    if [ -t 0 ]; then
        read -r -p "$(prompt_main "Choice [1]: ")" deploy_choice || true
    fi
    DEPLOY_TARGET_CHOICE="${deploy_choice:-1}"
    case "$DEPLOY_TARGET_CHOICE" in
        1) print_status "config" "Deploy target: GitHub Pages" ;;
        2) print_status "config" "Deploy target: Vercel"
           # Stated at scaffold time, not in a doc read after the first red push: the
           # Vercel project must already EXIST for those IDs to exist at all.
           print_status "warning" "Create the Vercel project first, then add the three repository secrets."
           print_status "info" "  gh secret set VERCEL_TOKEN; gh secret set VERCEL_ORG_ID; gh secret set VERCEL_PROJECT_ID" ;;
        3) print_status "config" "Deploy target: none" ;;
        *) print_status "warning" "Invalid choice; defaulting to GitHub Pages"
           DEPLOY_TARGET_CHOICE=1 ;;
    esac
}

prompt_module_federation() {
    echo ""
    # default "n": Module Federation reshapes webpack.config.js (see apply_file_variants) —
    # an unattended run must not silently pick a different build topology (#539).
    prompt_yes_no USE_MODULE_FEDERATION "$(prompt_main "Enable Webpack Module Federation? [y/N]: ")"
    if [ "$USE_MODULE_FEDERATION" = "true" ]; then
        print_status "config" "Module Federation: enabled"
    else
        print_status "config" "Module Federation: disabled"
    fi
}

prompt_docker() {
    echo ""
    # default "n": adds a Dockerfile/nginx.conf nobody asked for (#539).
    prompt_yes_no USE_DOCKER "$(prompt_main "Add a Docker setup (multi-stage build → nginx)? [y/N]: ")"
    if [ "$USE_DOCKER" = "true" ]; then
        print_status "config" "Docker: enabled (Dockerfile + nginx.conf + .dockerignore)"
    else
        print_status "config" "Docker: disabled"
    fi
}

prompt_js_copy_delivery() {
    echo ""
    # default "n": ships an extra delivery script + package.json entries (#539).
    prompt_yes_no USE_JS_COPY_DELIVERY "$(prompt_main "Ship a plain-JavaScript delivery copy script (js-copy)? [y/N]: ")"
    if [ "$USE_JS_COPY_DELIVERY" = "true" ]; then
        print_status "config" "JS-copy delivery: enabled (npm run js-copy:build / js-copy:verify)"
    else
        print_status "config" "JS-copy delivery: disabled"
    fi
}

prompt_otel() {
    echo ""
    # default "n": an opt-in that installs @opentelemetry/* deps, writes .env vars and
    # rewrites the composition root must never be answered by leftover pipe input (#539,
    # originally fixed inline in #519 — now folded into the shared helper).
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

    # Ship both a working .env (git-ignored) and the committed .env.example
    # template, so the project runs out of the box yet documents its vars.
    cp "$SKELETON_TEMPLATE_ROOT/.env.example" "$project_path/.env"
    cp "$SKELETON_TEMPLATE_ROOT/.env.example" "$project_path/.env.example"

    print_status "success" "Skeleton files copied"
}

# Optional Docker setup (multi-stage build → nginx). Copied only when the user
# opts in via prompt_docker; static-hosting users (GitHub Pages) skip it.
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

# patch_package_json is defined in bin/lib/scaffold_package_json.sh (#397) — shared with
# ts_lib.sh, which needs the exact same argv-not-source-interpolated write.

# Optional plain-JavaScript delivery copy (course submission, client handoff,
# a consumer with no TS toolchain). Copied only when prompt_js_copy_delivery
# was accepted. Depends on package.json, .gitignore and eslint.config.js
# already existing in the project (copy_skeleton_files + copy_common_templates
# must have run first).
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

    # The generated js-copy/ tree is a build artifact — never committed —
    # and must be excluded from lint, or every finding is reported twice
    # (once on src/, once on a copy nobody can edit).
    printf '\n# js-copy delivery script output (npm run js-copy:build)\n/js-copy/\n' \
        >> "$project_path/.gitignore"
    sed_inplace "s#'\*\*/dist/\*\*',#'**/dist/**',\n      '**/js-copy/**',#" \
        "$project_path/eslint.config.js"
    # scripts/*.mjs are Node CLI tooling, not app code — they fall outside every
    # `files:` block that grants browser/node globals, so process/console read
    # as undefined without this.
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

# Ships exactly ONE deploy workflow, per prompt_deploy_target. The workflows live under
# optional/deploy/ rather than .github/workflows/ precisely so the `.github` overlay above
# cannot copy both unconditionally.
copy_deploy_target() {
    local project_path="$1"
    local deploy_root="$SKELETON_TEMPLATE_ROOT/optional/deploy"

    case "$DEPLOY_TARGET_CHOICE" in
        1) cp "$deploy_root/pages/deploy-spa.yml" "$project_path/.github/workflows/deploy-spa.yml"
           print_status "success" "GitHub Pages deploy workflow added" ;;
        2) cp "$deploy_root/vercel/deploy-vercel.yml" "$project_path/.github/workflows/deploy-vercel.yml"
           # vercel.json is what `vercel build` reads for the SPA rewrites, so it belongs at
           # the project root, not in .github/.
           cp "$deploy_root/vercel/vercel.json" "$project_path/vercel.json"
           print_status "success" "Vercel deploy workflow + vercel.json added" ;;
        *) print_status "info" "No deploy workflow added" ;;
    esac
}

# Shared TS source (blueprintx#436) — mirrors templates/python-common/src/utils/.
# Lands under src/shared/, this skeleton's existing home for cross-capability code
# (the eslint-plugin-boundaries "shared" element type already covers shared/**).
copy_shared_ts_source() {
    local project_path="$1"
    mkdir -p "$project_path/src/shared/utils"
    cp -r "$COMMON_TEMPLATE_ROOT/src/." "$project_path/src/shared"
}

# OTLP log export (opt-in, blueprintx#504 — react-spa-webpack side of blueprintx#438, ts-lib
# wired by PR #505): the emitter (imports @opentelemetry/* — the ONLY place it is imported),
# its unit test, the pinned package.json dependencies (declared only here, so an opt-out never
# installs them), and a local-dev collector compose fragment — one function, mirroring
# ts_lib.sh's conditional_copy_otel. Unlike ts-lib, this skeleton ships a real .env (git-ignored)
# alongside the committed .env.example (copy_skeleton_files), so the OTel vars are appended to
# BOTH rather than only printed. Lands in src/shared/utils/ — copy_shared_ts_source's existing
# home for log-emitter.ts, which this file wraps (see its own module docstring).
# Wires the OTLP wrapper into the generated composition root. Printing "now go edit
# context.tsx yourself" left the enabled scaffold exporting NOTHING until a human changed
# application code by hand -- dependencies installed, env vars set, module present, and no
# logs leaving the browser. An opt-in that ships inert is worse than one that is absent,
# because everything visible says it is on (blueprintx#504 review).
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
    # EXACT pins, deliberately against this repo's house style of ranges (^X.0.0) — see
    # otel-log-emitter.ts's module docstring: the Logs signal is still "not yet stable"
    # upstream, so a minor bump may change behaviour. Re-check that status before bumping.
    patch_package_json "$project_path/package.json" dependencies \
        '@opentelemetry/api=1.9.1' \
        '@opentelemetry/api-logs=0.222.0' \
        '@opentelemetry/sdk-logs=0.222.0' \
        '@opentelemetry/exporter-logs-otlp-http=0.222.0' \
        '@opentelemetry/resources=2.11.0'
    # webpack.config.js's DefinePlugin inlines every .env key automatically (readEnvFile), so
    # no webpack.config.js change is needed — the fragment appended here is enough for the vars
    # to reach process.env.<KEY> in the bundle.
    cat "$COMMON_TEMPLATE_ROOT/optional/otel.env.fragment" >> "$project_path/.env"
    cat "$COMMON_TEMPLATE_ROOT/optional/otel.env.fragment" >> "$project_path/.env.example"
    wire_otel_composition_root "$project_path"
    print_status "success" "OTLP log export (src/shared/utils/otel-log-emitter.ts) added"
    print_status "info" "Set OTEL_EXPORTER_OTLP_ENDPOINT (and optionally OTEL_SERVICE_NAME) in .env to enable export — leave OTEL_EXPORTER_OTLP_HEADERS blank (see the fragment's warning)"
}

# Static ts-common assets that need no envsubst rendering. Split out of
# copy_common_templates() (#464) to keep that function under the 60-line
# function-length gate once it grew a package-lock.json copy line.
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
    cp "$SHARED_TEMPLATE_ROOT/.github/CLAUDE.md" "$project_path/.github/CLAUDE.md"
    cp "$SHARED_TEMPLATE_ROOT/.github/CODEOWNERS" "$project_path/.github/CODEOWNERS"
    cp "$SHARED_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
}

# Refresh the lockfile after apply_package_variants (blueprintx#468 review).
# copy_common_templates ships the BASE lockfile, and apply_package_variants then adds the
# variant's dependencies to package.json — so a zustand/redux project would carry a lockfile
# that no longer matches its manifest. The generated project runs `npm ci` in five workflows,
# and `npm ci` fails hard on exactly that mismatch: the pinning #464 introduced would have
# turned into a red first push for two of the three supported variants.
refresh_lockfile_for_variants() {
	local project_path="$1"
	# The base variant never diverges from the shipped lockfile.
	if [[ "$STATE_MANAGEMENT" == "none" ]]; then
		return
	fi
	if ! command -v npm >/dev/null 2>&1; then
		# Ship no lockfile rather than a wrong one: `npm install` regenerates a correct one,
		# while a stale file fails in CI, far from here, naming neither the variant nor this step.
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
        < "$SKELETON_TEMPLATE_ROOT/CLAUDE.md" \
        > "$project_path/CLAUDE.md"
    # SRP/actor-cohesion + Clean Code function principles (blueprintx#540) — one shared
    # file, language-agnostic, so it lives in templates/common not ts-common.
    cp "$SHARED_TEMPLATE_ROOT/PRINCIPLES.md" "$project_path/PRINCIPLES.md"
    envsubst '${PROJECT_NAME} ${PROJECT_DESCRIPTION} ${PROJECT_LICENSE} ${GITHUB_USERNAME} ${STATE_MANAGEMENT_VARIANT}' \
        < "$SKELETON_TEMPLATE_ROOT/README.md" \
        > "$project_path/README.md"

    copy_static_ts_common_files "$project_path"
    # Overlay react-spa-webpack-specific .github contents (e.g. deploy-spa.yml)
    # on top of the universal ts-common .github. Skeleton overlays win on
    # name collision; ts-common files survive when the skeleton is silent.
    if [ -d "$SKELETON_TEMPLATE_ROOT/.github" ]; then
        cp -r "$SKELETON_TEMPLATE_ROOT/.github/." "$project_path/.github"
    fi
    copy_deploy_target "$project_path"
    envsubst < "$LICENSES_TEMPLATE_ROOT/${LICENSE_CHOICE}" > "$project_path/LICENSE"

    # Ship the repo→LLM context exporter (and its print_status helper) unconditionally,
    # so `npm run context:export` works whether or not a GitHub remote is connected.
    mkdir -p "$project_path/bin/lib"
    cp "$SHARED_TEMPLATE_ROOT/bin/lib/common.sh" "$project_path/bin/lib/common.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/export_repo_content.sh" "$project_path/bin/export_repo_content.sh"
    chmod +x "$project_path/bin/export_repo_content.sh"

    # The review-threads.yml gate's only dependency: the ONE shared implementation of the
    # answered-review-thread predicate (blueprintx#175), same file the Python tiers ship, so
    # the CI job above never fetches or vendors a copy of its own.
    cp "$SHARED_TEMPLATE_ROOT/bin/check_review_threads.py" "$project_path/bin/check_review_threads.py"

    copy_shared_ts_source "$project_path"

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
        print_status "warning" "gh not authenticated; skipping main branch protection."
        return
    fi

    if ! gh repo view "$repo" >/dev/null 2>&1; then
        print_status "warning" "GitHub repo $repo not reachable; skipping branch protection."
        return
    fi

    local do_protect reviews_ans reviews_json
    # default "n": protecting the branch is a GitHub API mutation (enforce_admins, required
    # checks) — an unattended run must not silently lock down a repo nobody confirmed (#539).
    prompt_yes_no do_protect "$(prompt_main "Protect branch '$branch' on GitHub now? [y/N]: ")"
    if [ "$do_protect" != "true" ]; then
        print_status "info" "Skipped branch protection"
        return
    fi

    # A solo maintainer cannot satisfy a required-approving-review
    # rule — GitHub forbids self-approval, so the first PR's merge
    # would be permanently blocked. Ask whether human reviewers will
    # gate merges, and build the protection payload accordingly.
    # default "n": matches the pre-existing fallback (solo maintainer, no required reviews).
    prompt_yes_no reviews_ans "$(prompt_sub "Will human reviewers gate merges to '$branch'? [y/N]: ")"
    if [ "$reviews_ans" = "true" ]; then
        reviews_json='"required_pull_request_reviews": { "dismiss_stale_reviews": true, "require_code_owner_reviews": false, "required_approving_review_count": 1 },'
    else
        # Solo: keep status checks + linear history, drop required reviews.
        reviews_json='"required_pull_request_reviews": null,'
    fi
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
}

pages_prerequisites_met() {
    # Everything that must be true before it is even worth asking. Each is a silent return
    # rather than a warning: a user without gh has not done anything wrong.
    local repo="$1"

    command -v gh >/dev/null 2>&1 || return 1
    gh auth status >/dev/null 2>&1 || return 1
    gh repo view "$repo" >/dev/null 2>&1 || return 1
}

wait_for_gh_pages_branch() {
    # Pages can only be pointed at the gh-pages branch once that branch EXISTS — and it is
    # created by the deploy-spa workflow on the FIRST push to main, which takes ~1-3 min.
    # Enabling before then fails with a 404 and leaves the user staring at "Site not found".
    local repo="$1" manual_cmd="$2"
    local attempts=0
    local max_attempts=12 # ~3 min at 15s intervals
    local wait_ans

    gh api "/repos/$repo/branches/gh-pages" >/dev/null 2>&1 && return 0

    print_status "info" "The 'gh-pages' branch doesn't exist yet — the first deploy creates it (~1-3 min)."
    # default "y": the only prerequisite already met to reach this point is a confirmed
    # GitHub Pages setup (prompt_pages_setup); waiting is a passive poll, not a mutation, so
    # it is the safe unattended answer -- unlike every other prompt in this file (#539).
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
    # GitHub stopped auto-enabling Pages on gh-pages pushes (~2022). The deploy-spa workflow
    # pushes the build to gh-pages, but the Pages service stays off — and a fresh deploy
    # 404s — until it is enabled once. The default GITHUB_TOKEN lacks the permission to do it
    # from the workflow, so it is offered here using the local gh token.
    local owner="${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}"
    local repo="$owner/${PROJECT_NAME}"
    local manual_cmd="gh api -X POST repos/$repo/pages -f 'source[branch]=gh-pages' -f 'source[path]=/'"
    local pages_ans

    pages_prerequisites_met "$repo" || return

    print_status "info" "GitHub Pages must be enabled once per repo (GitHub no longer auto-enables it on gh-pages pushes)."
    # default "n": enabling Pages is a GitHub API mutation — an unattended run must not
    # silently publish a site nobody confirmed (#539).
    prompt_yes_no pages_ans "$(prompt_main "Enable GitHub Pages (deploy from gh-pages branch) now? [y/N]: ")"
    if [ "$pages_ans" != "true" ]; then
        print_status "info" "Skipped GitHub Pages setup"
        return
    fi

    wait_for_gh_pages_branch "$repo" "$manual_cmd" || return
    enable_gh_pages "$repo" "$owner" "$manual_cmd"
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
	# Branch protection and Pages both write to the remote, so they run only once that
	# remote is verified to be the repository this scaffold names — not merely because
	# the prompt returned (#212).
	if scaffold_prompt_git_remote_setup "$1"; then
		apply_branch_protection "$1"
		# Only the Pages target needs the one-off Pages enablement; offering it on the
		# Vercel or none path would wait on a gh-pages branch nothing ever pushes.
		[ "$DEPLOY_TARGET_CHOICE" = "1" ] && prompt_pages_setup
	fi
}

apply_offline_mode() {
    local project_path="$1"

    print_status "info" "No GitHub remote connected — switching to offline mode"
    # GitHub-only assets (Actions workflows, CODEOWNERS, PR template) are not useful
    # without a GitHub remote; remove them and ship the offline git-diff workflow instead.
    rm -rf "$project_path/.github"
    print_status "info" "Removed .github (GitHub-only assets)"
    # vercel.json lives at the project ROOT, so the .github sweep above does not reach it —
    # and a Vercel config with no workflow to read it is dead configuration pointing at a
    # deploy that cannot happen. It goes with its workflow.
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
    # Every `cp -r` above copies whatever sits in templates/, caches included (#205).
    scaffold_purge_caches "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    # When the project is not connected to a GitHub remote (no upstream tracking
    # branch after setup), switch to offline mode: drop GitHub-only assets and
    # ship the git-diff sync workflow instead.
    # ⚠️ `@{u}` alone answers "is there an upstream?", never "is it OUR upstream?" — it is TRUE
    # for a pre-existing clone whose origin points elsewhere. Offline is the safe default, so
    # an unverified remote falls here too (#212, raised by review on #215).
    if [ "$SCAFFOLD_REMOTE_VERIFIED" != "1" ] \
        || ! git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        apply_offline_mode "$PROJECT_PATH"
    fi

    print_status "success" "React SPA scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
    print_status "info" "Run 'npm install && npm start' to begin development"
}

main
