#!/usr/bin/env bash
# Scaffolds the ts-lib skeleton: a publishable TypeScript library (ESM + CJS +
# .d.ts via plain tsc, Jest, ESLint). Mechanics mirror ts_react_app.sh; the
# packaging discipline (offline mode, git-remote flow) mirrors every other
# scaffold in bin/scaffold/.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=bin/lib/scaffold_git_remote.sh
source "$SCRIPT_DIR/../lib/scaffold_git_remote.sh"

PROJECT_ROOT="${1:-}"
PROJECT_NAME="${2:-}"
PROJECT_DESCRIPTION="${3:-}"
LICENSE_CHOICE="${LICENSE_CHOICE:-MIT}"
GITHUB_USERNAME="${GITHUB_USERNAME:-}"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SKELETON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/ts-lib"
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
    cp "$SKELETON_TEMPLATE_ROOT/.babelrc" "$project_path/.babelrc"
    cp "$SKELETON_TEMPLATE_ROOT/jest.config.cjs" "$project_path/jest.config.cjs"
    # .mjs (not .js): package.json is "type": "commonjs" (so dist/cjs needs no per-file
    # marker), and these three configs are authored as ESM — the explicit extension makes
    # each tool load them as ESM regardless of the package's own module type.
    cp "$SKELETON_TEMPLATE_ROOT/eslint.config.mjs" "$project_path/eslint.config.mjs"
    cp "$SKELETON_TEMPLATE_ROOT/.prettierrc.mjs" "$project_path/.prettierrc.mjs"
    cp "$SKELETON_TEMPLATE_ROOT/lint-staged.config.mjs" "$project_path/lint-staged.config.mjs"
    cp "$SKELETON_TEMPLATE_ROOT/bin/write_esm_package_json.sh" "$project_path/bin/write_esm_package_json.sh"
    cp "$SKELETON_TEMPLATE_ROOT/bin/smoke_pack.sh" "$project_path/bin/smoke_pack.sh"
    chmod +x "$project_path/bin/write_esm_package_json.sh" "$project_path/bin/smoke_pack.sh"
    # Docusaurus site (#134) + npm OIDC / Verdaccio CI (#135, #136). sidebars.js and the
    # three workflow files below carry no ${VAR} placeholders, so a plain cp is enough;
    # docusaurus.config.js, docs/*.md and release-npm.yml DO carry placeholders and are
    # rendered later in copy_common_templates, where PROJECT_NAME/GITHUB_USERNAME etc.
    # are already exported for envsubst.
    cp "$SKELETON_TEMPLATE_ROOT/sidebars.js" "$project_path/sidebars.js"
    cp "$SKELETON_TEMPLATE_ROOT/.github/workflows/docs.yml" "$project_path/.github/workflows/docs.yml"
    cp "$SKELETON_TEMPLATE_ROOT/.github/workflows/docs-deploy.yml" "$project_path/.github/workflows/docs-deploy.yml"
    cp "$SKELETON_TEMPLATE_ROOT/.github/workflows/pack-smoke.yml" "$project_path/.github/workflows/pack-smoke.yml"

    print_status "success" "Skeleton files copied"
}

# envsubst does no JSON escaping — a description containing a quote or backslash
# (e.g. `A "small" library`) would land in package.json as an unescaped string and
# produce invalid JSON, breaking every npm command. Render it with Python's json
# module instead, which escapes each value before substitution and then re-parses
# the result so a bad render fails loudly here rather than shipping broken JSON.
render_package_json() {
    local project_path="$1"
    python3 - "$SKELETON_TEMPLATE_ROOT/package.json" "$project_path/package.json" \
        "$PROJECT_NAME" "$PROJECT_DESCRIPTION" "$PROJECT_LICENSE" <<'PY'
import json
import sys

path_template, path_out, str_name, str_description, str_license = sys.argv[1:6]


def json_escape(value):
    """Escape a raw string for safe interpolation inside a JSON string literal."""
    return json.dumps(value)[1:-1]


with open(path_template, encoding="utf-8") as fh:
    text = fh.read()

text = text.replace("${PROJECT_NAME}", json_escape(str_name))
text = text.replace("${PROJECT_DESCRIPTION}", json_escape(str_description))
text = text.replace("${PROJECT_LICENSE}", json_escape(str_license))

json.loads(text)  # fail loudly on any render that produced invalid JSON

with open(path_out, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
}

copy_common_templates() {
    local project_path="$1"

    print_status "info" "Applying common TypeScript templates..."

    PROJECT_LICENSE="${LICENSE_CHOICE}"
    export PROJECT_NAME PROJECT_DESCRIPTION PROJECT_LICENSE GITHUB_USERNAME
    render_package_json "$project_path"
    envsubst '${PROJECT_NAME}' \
        < "$SKELETON_TEMPLATE_ROOT/CLAUDE.md" \
        > "$project_path/CLAUDE.md"
    envsubst '${PROJECT_NAME} ${PROJECT_DESCRIPTION} ${PROJECT_LICENSE} ${GITHUB_USERNAME}' \
        < "$SKELETON_TEMPLATE_ROOT/README.md" \
        > "$project_path/README.md"

    cp "$COMMON_TEMPLATE_ROOT/.gitignore" "$project_path/.gitignore"
    cp "$COMMON_TEMPLATE_ROOT/.nvmrc" "$project_path/.nvmrc"
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
    envsubst < "$LICENSES_TEMPLATE_ROOT/${LICENSE_CHOICE}" > "$project_path/LICENSE"

    # Ship the repo->LLM context exporter (and its print_status helper) unconditionally,
    # so `npm run context:export` works whether or not a GitHub remote is connected.
    mkdir -p "$project_path/bin/lib"
    cp "$SHARED_TEMPLATE_ROOT/bin/lib/common.sh" "$project_path/bin/lib/common.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/export_repo_content.sh" "$project_path/bin/export_repo_content.sh"
    chmod +x "$project_path/bin/export_repo_content.sh"

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
            # A solo maintainer cannot satisfy a required-approving-review rule — GitHub
            # forbids self-approval, so the first PR's merge would be permanently blocked.
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
                print_status "warning" "Failed to protect branch '$branch'; adjust settings manually in GitHub."
            fi
            ;;
        *) print_status "info" "Skipped branch protection" ;;
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
    # Branch protection runs only once the remote is verified to be the repository this
    # scaffold names — not merely because the prompt returned (#212).
    if scaffold_prompt_git_remote_setup "$1"; then
        apply_branch_protection "$1"
    fi
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
    commit_offline_artifacts "$project_path"
}

# initialize_git_repo's first commit runs BEFORE apply_offline_mode, so the offline
# rewrites (.github removed, bin/git_diff_*.sh added, package.json's scripts patched)
# are left uncommitted — every offline scaffold would otherwise finish with a dirty
# working tree. --no-verify bypasses the just-installed hooks (HEAD is main).
commit_offline_artifacts() {
    local project_path="$1"
    git -C "$project_path" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
    git -C "$project_path" add -A
    git -C "$project_path" commit -q --no-verify -m "chore: enable offline git workflow" || true
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    PROJECT_PATH="$PROJECT_ROOT/$PROJECT_NAME"

    print_section "TypeScript library (ts-lib) scaffold"
    print_status "config" "Target: $PROJECT_PATH"

    validate_inputs
    resolve_github_username
    create_directory_structure "$PROJECT_PATH"
    copy_skeleton_files "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    # Every `cp -r` above copies whatever sits in templates/, caches included (#205).
    scaffold_purge_caches "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    # When the project is not connected to a GitHub remote (no upstream tracking branch
    # after setup), switch to offline mode: drop GitHub-only assets and ship the
    # git-diff sync workflow instead. Offline is the safe default for an unverified
    # remote too (#212).
    if [ "$SCAFFOLD_REMOTE_VERIFIED" != "1" ] \
        || ! git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        apply_offline_mode "$PROJECT_PATH"
    fi

    print_status "success" "ts-lib scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
    print_status "info" "Run 'npm install && npm run build && npm test' to get started"
}

main
