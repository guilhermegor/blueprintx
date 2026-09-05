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

# ============================================================================
# FUNCTIONS
# ============================================================================

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
    read -r -p "$(prompt_main "GitHub username (default: $DEFAULT_GITHUB_USERNAME): ")" input || true
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
    read -r -p "$(prompt_main "Choice [1]: ")" sm_choice || true
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
    read -r -p "$(prompt_main "Choice [1]: ")" deploy_choice || true
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
    read -r -p "$(prompt_main "Enable Webpack Module Federation? [y/N]: ")" mf_answer || true
    case "$mf_answer" in
        y|Y) USE_MODULE_FEDERATION=1
             print_status "config" "Module Federation: enabled" ;;
        *)   USE_MODULE_FEDERATION=0
             print_status "config" "Module Federation: disabled" ;;
    esac
}

prompt_docker() {
    echo ""
    read -r -p "$(prompt_main "Add a Docker setup (multi-stage build → nginx)? [y/N]: ")" docker_answer || true
    case "$docker_answer" in
        y|Y) USE_DOCKER=1
             print_status "config" "Docker: enabled (Dockerfile + nginx.conf + .dockerignore)" ;;
        *)   USE_DOCKER=0
             print_status "config" "Docker: disabled" ;;
    esac
}

prompt_js_copy_delivery() {
    echo ""
    read -r -p "$(prompt_main "Ship a plain-JavaScript delivery copy script (js-copy)? [y/N]: ")" js_copy_answer || true
    case "$js_copy_answer" in
        y|Y) USE_JS_COPY_DELIVERY=1
             print_status "config" "JS-copy delivery: enabled (npm run js-copy:build / js-copy:verify)" ;;
        *)   USE_JS_COPY_DELIVERY=0
             print_status "config" "JS-copy delivery: disabled" ;;
    esac
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

    if [ "${USE_DOCKER:-0}" -ne 1 ]; then
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

    if [ "${USE_JS_COPY_DELIVERY:-0}" -ne 1 ]; then
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
    sed -i "s#'\*\*/dist/\*\*',#'**/dist/**',\n      '**/js-copy/**',#" \
        "$project_path/eslint.config.js"
    # scripts/*.mjs are Node CLI tooling, not app code — they fall outside every
    # `files:` block that grants browser/node globals, so process/console read
    # as undefined without this.
    sed -i "s#  // 9. Prettier config#  // 9. scripts/ (js-copy delivery tooling) — Node CLI, not app code\n  {\n    files: ['scripts/**/*.mjs'],\n    languageOptions: { globals: { ...globals.node } },\n  },\n\n  // 10. Prettier config#" \
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

    if [ "$USE_MODULE_FEDERATION" -eq 1 ]; then
        print_status "info" "Applying Module Federation webpack config..."
        cp "$SKELETON_TEMPLATE_ROOT/webpack.mf.config.js" "$project_path/webpack.config.js"
        sed -i "s/__APP_NAME__/$PROJECT_NAME/g" "$project_path/webpack.config.js"
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

copy_common_templates() {
    local project_path="$1"

    print_status "info" "Applying common TypeScript templates..."

    PROJECT_LICENSE="${LICENSE_CHOICE}"
    export PROJECT_NAME PROJECT_DESCRIPTION PROJECT_LICENSE GITHUB_USERNAME \
           STATE_MANAGEMENT_VARIANT STATE_MANAGEMENT_DESC STATE_MANAGEMENT_ANTIPATTERN
    envsubst '${PROJECT_NAME} ${PROJECT_DESCRIPTION}' \
        < "$COMMON_TEMPLATE_ROOT/package.json" \
        > "$project_path/package.json"
    envsubst '${PROJECT_NAME} ${STATE_MANAGEMENT_VARIANT} ${STATE_MANAGEMENT_DESC} ${STATE_MANAGEMENT_ANTIPATTERN}' \
        < "$SKELETON_TEMPLATE_ROOT/CLAUDE.md" \
        > "$project_path/CLAUDE.md"
    envsubst '${PROJECT_NAME} ${PROJECT_DESCRIPTION} ${PROJECT_LICENSE} ${GITHUB_USERNAME} ${STATE_MANAGEMENT_VARIANT}' \
        < "$SKELETON_TEMPLATE_ROOT/README.md" \
        > "$project_path/README.md"

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
                    # Solo: keep status checks + linear history, drop required reviews.
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
        *) print_status "info" "Skipped branch protection" ;;
    esac
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
    read -r -p "$(prompt_main "Wait for the first deploy and enable Pages automatically? [Y/n]: ")" wait_ans || true
    case "$wait_ans" in
    n | N)
        print_status "info" "After the first deploy finishes, enable Pages with:"
        print_status "info" "  $manual_cmd"
        return 1
        ;;
    esac

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
    read -r -p "$(prompt_main "Enable GitHub Pages (deploy from gh-pages branch) now? [y/N]: ")" pages_ans || true
    case "$pages_ans" in
    y | Y) ;;
    *)
        print_status "info" "Skipped GitHub Pages setup"
        return
        ;;
    esac

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

# ============================================================================
# MAIN
# ============================================================================

main() {
    PROJECT_PATH="$PROJECT_ROOT/$PROJECT_NAME"

    print_section "React SPA (Webpack) scaffold"
    print_status "config" "Target: $PROJECT_PATH"

    validate_inputs
    resolve_github_username
    prompt_state_management
    prompt_deploy_target
    prompt_module_federation
    prompt_docker
    prompt_js_copy_delivery
    create_directory_structure "$PROJECT_PATH"
    copy_skeleton_files "$PROJECT_PATH"
    apply_docker_files "$PROJECT_PATH"
    apply_file_variants "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    apply_package_variants "$PROJECT_PATH"
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
