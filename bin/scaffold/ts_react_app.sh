#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/logging.sh"

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
    read -r -p "GitHub username (default: $DEFAULT_GITHUB_USERNAME): " input || true
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
    read -r -p "Choice [1]: " sm_choice || true
    STATE_MGMT_CHOICE="${sm_choice:-1}"
    case "$STATE_MGMT_CHOICE" in
        1) print_status "config" "State management: React Context" ;;
        2) print_status "config" "State management: Zustand" ;;
        3) print_status "config" "State management: Redux Toolkit" ;;
        *) print_status "warning" "Invalid choice; defaulting to React Context"
           STATE_MGMT_CHOICE=1 ;;
    esac
}

prompt_module_federation() {
    echo ""
    read -r -p "Enable Webpack Module Federation? [y/N]: " mf_answer || true
    case "$mf_answer" in
        y|Y) USE_MODULE_FEDERATION=1
             print_status "config" "Module Federation: enabled" ;;
        *)   USE_MODULE_FEDERATION=0
             print_status "config" "Module Federation: disabled" ;;
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
            python3 -c "
import json
with open('$project_path/package.json') as f:
    pkg = json.load(f)
pkg['dependencies']['zustand'] = '^5.0.0'
with open('$project_path/package.json', 'w') as f:
    json.dump(pkg, f, indent=2)
    f.write('\n')
"
            ;;
        3)
            print_status "info" "Adding Redux Toolkit dependencies..."
            python3 -c "
import json
with open('$project_path/package.json') as f:
    pkg = json.load(f)
pkg['dependencies']['@reduxjs/toolkit'] = '^2.0.0'
pkg['dependencies']['react-redux'] = '^9.0.0'
with open('$project_path/package.json', 'w') as f:
    json.dump(pkg, f, indent=2)
    f.write('\n')
"
            ;;
        *) ;;
    esac

    print_status "success" "Package variants applied"
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
    cp "$SHARED_TEMPLATE_ROOT/.github/CODEOWNERS" "$project_path/.github/CODEOWNERS"
    cp "$SHARED_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
    # Overlay react-spa-webpack-specific .github contents (e.g. deploy-spa.yml)
    # on top of the universal ts-common .github. Skeleton overlays win on
    # name collision; ts-common files survive when the skeleton is silent.
    if [ -d "$SKELETON_TEMPLATE_ROOT/.github" ]; then
        cp -r "$SKELETON_TEMPLATE_ROOT/.github/." "$project_path/.github"
    fi
    envsubst < "$LICENSES_TEMPLATE_ROOT/${LICENSE_CHOICE}" > "$project_path/LICENSE"

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

prompt_pages_setup() {
    # GitHub stopped auto-enabling Pages on gh-pages pushes (~2022). The
    # deploy-spa workflow pushes the build to gh-pages, but the Pages
    # service stays off — and a fresh deploy 404s — until it's enabled
    # once. The default GITHUB_TOKEN lacks the permission to do it from
    # the workflow, so we offer it here using the local gh token.
    local repo="${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}"
    local owner="${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}"

    if ! command -v gh >/dev/null 2>&1; then
        return
    fi
    if ! gh auth status >/dev/null 2>&1; then
        return
    fi
    if ! gh repo view "$repo" >/dev/null 2>&1; then
        return
    fi

    print_status "info" "GitHub Pages must be enabled once per repo (GitHub no longer auto-enables it on gh-pages pushes)."
    read -r -p "Enable GitHub Pages (deploy from gh-pages branch) now? [y/N]: " pages_ans || true
    case "$pages_ans" in
        y|Y)
            if gh api --method POST "/repos/$repo/pages" \
                -f 'source[branch]=gh-pages' -f 'source[path]=/' >/dev/null 2>&1; then
                print_status "success" "GitHub Pages enabled — live at https://$owner.github.io/${PROJECT_NAME}/ after the first deploy."
            else
                print_status "warning" "Could not enable Pages yet — the 'gh-pages' branch must exist first (the deploy workflow creates it on the first push to main)."
                print_status "info" "After the first deploy, run: gh api -X POST repos/$repo/pages -f 'source[branch]=gh-pages' -f 'source[path]=/'"
            fi
            ;;
        *) print_status "info" "Skipped GitHub Pages setup" ;;
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
                    print_status "warning" "Remote 'origin' already exists; skipped add"
                else
                    git remote add origin "git@github.com:${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}.git" || true
                fi
            )
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
                                print_status "warning" "gh repo create failed; check authentication or if the repo already exists."
                                print_status "info" "Manual fallback: create the repo on GitHub and run 'git push -u origin main'."
                            fi
                        )
                        ;;
                    *) print_status "info" "Skipped GitHub repo creation/push" ;;
                esac
            else
                print_status "info" "gh CLI not found; to publish run: git push -u origin main (ensure repo exists on GitHub)."
            fi
            if [ "$push_done" -eq 0 ]; then
                if git -C "$project_path" remote get-url origin >/dev/null 2>&1; then
                    if git -C "$project_path" push -u origin main >/dev/null 2>&1; then
                        print_status "success" "Pushed to origin/main."
                    else
                        print_status "warning" "Push to origin/main failed; create the repo on GitHub and retry 'git push -u origin main'."
                    fi
                else
                    print_status "warning" "Remote 'origin' missing; cannot push. Create repo and run 'git push -u origin main'."
                fi
            fi
            print_status "success" "Git repo initialized."
            ;;
        *)
            print_status "info" "Skipped remote setup"
            ;;
    esac

    apply_branch_protection "$project_path"
    prompt_pages_setup
}

apply_offline_mode() {
    local project_path="$1"

    print_status "info" "No GitHub remote connected — switching to offline mode"
    # GitHub-only assets (Actions workflows, CODEOWNERS, PR template) are not useful
    # without a GitHub remote; remove them and ship the offline git-diff workflow instead.
    rm -rf "$project_path/.github"
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
    python3 -c "
import json
with open('$project_path/package.json') as f:
    pkg = json.load(f)
pkg.setdefault('scripts', {})
pkg['scripts']['git:diff:export'] = 'bash bin/git_diff_export.sh'
pkg['scripts']['git:diff:check'] = 'bash bin/git_diff_check.sh'
pkg['scripts']['git:diff:apply'] = 'bash bin/git_diff_apply.sh'
with open('$project_path/package.json', 'w') as f:
    json.dump(pkg, f, indent=2)
    f.write('\n')
"
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
    prompt_module_federation
    create_directory_structure "$PROJECT_PATH"
    copy_skeleton_files "$PROJECT_PATH"
    apply_file_variants "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    apply_package_variants "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    # When the project is not connected to a GitHub remote (no upstream tracking
    # branch after setup), switch to offline mode: drop GitHub-only assets and
    # ship the git-diff sync workflow instead.
    if ! git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        apply_offline_mode "$PROJECT_PATH"
    fi

    print_status "success" "React SPA scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
    print_status "info" "Run 'npm install && npm start' to begin development"
}

main
