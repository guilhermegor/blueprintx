#!/usr/bin/env bash
#
# promote_offline_to_online.sh — turn an OFFLINE scaffolded project into an ONLINE one
# without re-scaffolding (blueprintx#382).
#
# Adds the GitHub-only assets apply_offline_mode skipped, creates the GitHub repo and
# pushes, applies best-effort branch protection, and removes/neutralises the offline-only
# fallbacks (git-diff scripts, poe_tasks.offline.toml, the swapped protect-branch hook).
#
# Deliberately standalone: it does NOT source or edit any bin/scaffold/*.sh — those are
# held by other PRs (see docs/offline-to-online.md for the manifest this script mirrors).
#
# Usage: bin/promote_offline_to_online.sh <project_path> --tier <tier> [options]
# See usage() below or --help for the full flag list.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

TIERS=(ddd-service-native-db ddd-service-orm-db mvc-service-native-db mvc-service-orm-db lib-minimal react-spa-webpack)

PROJECT_PATH=""
TIER=""
GITHUB_USERNAME="${GITHUB_USERNAME:-}"
VISIBILITY="private"
DEPLOY_TARGET="none"
PUBLISH_TARGET="none"
SKIP_BRANCH_PROTECTION=false

usage() {
    cat <<'EOF'
Usage: bin/promote_offline_to_online.sh <project_path> --tier <tier> [options]

Required:
  <project_path>           Path to the offline-scaffolded project to promote.
  --tier <tier>             ddd-service-native-db | ddd-service-orm-db |
                             mvc-service-native-db | mvc-service-orm-db |
                             lib-minimal | react-spa-webpack

Options:
  --github-user <user>      GitHub owner for the new repo (default: `gh api user`).
  --visibility public|private  Repo visibility (default: private).
  --deploy-target none|pages|vercel   react-spa-webpack only (default: none — the
                             original choice is not recorded offline; see docs).
  --publish none|pypi|test-pypi|both  lib-minimal only (default: none, same reason).
  --skip-branch-protection  Do not attempt branch protection after repo creation.
  -h, --help                Show this help.
EOF
}

exit_usage_error() {
    usage >&2
    exit_error "$1"
}

parse_args() {
    [ $# -eq 0 ] && exit_usage_error "project_path is required"
    while [ $# -gt 0 ]; do
        case "$1" in
            -h | --help)
                usage
                exit 0
                ;;
            --tier)
                TIER="${2:-}"
                shift 2
                ;;
            --github-user)
                GITHUB_USERNAME="${2:-}"
                shift 2
                ;;
            --visibility)
                VISIBILITY="${2:-}"
                shift 2
                ;;
            --deploy-target)
                DEPLOY_TARGET="${2:-}"
                shift 2
                ;;
            --publish)
                PUBLISH_TARGET="${2:-}"
                shift 2
                ;;
            --skip-branch-protection)
                SKIP_BRANCH_PROTECTION=true
                shift
                ;;
            --)
                shift
                break
                ;;
            -*)
                exit_usage_error "Unknown option: $1"
                ;;
            *)
                [ -n "$PROJECT_PATH" ] && exit_usage_error "Unexpected extra argument: $1"
                PROJECT_PATH="$1"
                shift
                ;;
        esac
    done
    [ -n "$PROJECT_PATH" ] || exit_usage_error "project_path is required"
    [ -n "$TIER" ] || exit_usage_error "--tier is required"
    case "$VISIBILITY" in
        public | private) ;;
        *) exit_usage_error "--visibility must be public or private" ;;
    esac
}

# Refuse loudly rather than guess: an unknown tier, or a tier whose skeleton no longer
# exists in this BlueprintX checkout, must FAIL — never silently copy nothing.
require_known_tier() {
    local tier_ok=false candidate
    for candidate in "${TIERS[@]}"; do
        [ "$candidate" = "$TIER" ] && tier_ok=true
    done
    [ "$tier_ok" = "true" ] || exit_usage_error "Unknown --tier '$TIER' (expected one of: ${TIERS[*]})"
    [ -f "$BLUEPRINTX_ROOT/templates/$TIER/skeleton.meta" ] \
        || exit_error "Tier '$TIER' has no templates/$TIER/skeleton.meta in this BlueprintX checkout — inventory missing, refusing to half-promote."
}

tier_common_root() {
    case "$TIER" in
        react-spa-webpack) echo "ts-common" ;;
        *) echo "python-common" ;;
    esac
}

require_git_repo() {
    [ -d "$PROJECT_PATH" ] || exit_error "No such directory: $PROJECT_PATH"
    git -C "$PROJECT_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
        || exit_error "$PROJECT_PATH is not a git repository — refusing to promote."
}

require_clean_tree() {
    [ -z "$(git -C "$PROJECT_PATH" status --porcelain)" ] \
        || exit_error "$PROJECT_PATH has uncommitted changes — commit or stash them first, then re-run."
}

require_gh_ready() {
    command -v gh >/dev/null 2>&1 || exit_error "gh CLI not found — required to create the repo and apply branch protection."
    gh auth status >/dev/null 2>&1 || exit_error "gh is not authenticated — run 'gh auth login' first."
}

# Sets HAS_ORIGIN / HAS_GITHUB_ASSETS. Both flow into the should-fail witnesses in main():
# already-online is a clean no-op, origin-without-assets is an ambiguous state we refuse.
detect_state() {
    HAS_ORIGIN=false
    git -C "$PROJECT_PATH" remote get-url origin >/dev/null 2>&1 && HAS_ORIGIN=true

    HAS_GITHUB_ASSETS=false
    if [ -d "$PROJECT_PATH/.github/workflows" ] \
        && [ -n "$(find "$PROJECT_PATH/.github/workflows" -mindepth 1 2>/dev/null)" ]; then
        HAS_GITHUB_ASSETS=true
    fi
}

resolve_identity() {
    [ -n "$GITHUB_USERNAME" ] || GITHUB_USERNAME="$(gh api user --jq .login)"
    [ -n "$GITHUB_USERNAME" ] || exit_error "Could not resolve a GitHub username; pass --github-user explicitly."
    PROJECT_NAME="$(basename "$PROJECT_PATH")"
    PROJECT_DISPLAY_NAME="$(echo "$PROJECT_NAME" | tr '_-' '  ' | awk '{for (i = 1; i <= NF; i++) $i = toupper(substr($i, 1, 1)) substr($i, 2); print}')"
    REPOSITORY="$GITHUB_USERNAME/$PROJECT_NAME"
    export PROJECT_NAME PROJECT_DISPLAY_NAME GITHUB_USERNAME REPOSITORY
}

# Mirrors copy_github_assets() in the 4 native/ORM service scaffolds (bin/scaffold/python_*.sh) —
# identical manifest across all four, transcribed rather than sourced (those scripts are held
# by other PRs). See docs/offline-to-online.md for the source table.
copy_online_assets_service_tier() {
    local common="$BLUEPRINTX_ROOT/templates/python-common" shared="$BLUEPRINTX_ROOT/templates/common"
    local dest="$PROJECT_PATH" wf
    mkdir -p "$dest/.github/workflows"
    for wf in tests secret_scan review_threads coderabbit_trigger review_retry pr-gate pr-reconcile contract_drift release; do
        cp "$common/.github/workflows/$wf.yaml" "$dest/.github/workflows/$wf.yaml"
    done
    cp "$shared/docs_version/docs.yaml" "$dest/.github/workflows/docs.yaml"
    envsubst '${GITHUB_USERNAME}' <"$shared/.github/CODEOWNERS" >"$dest/.github/CODEOWNERS"
    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' <"$shared/SECURITY.md" >"$dest/SECURITY.md"
    cp "$common/.github/dependabot.yml" "$dest/.github/dependabot.yml"
    cp "$shared/.github/CLAUDE.md" "$dest/.github/CLAUDE.md"
    cp "$shared/.github/PULL_REQUEST_TEMPLATE.md" "$dest/.github/PULL_REQUEST_TEMPLATE.md"
    print_status "success" "GitHub assets copied (.github, SECURITY.md)"
}

# Mirrors lib_minimal_copy_github_assets() in bin/scaffold/python_lib_minimal.sh. The original
# PyPI/Test-PyPI choice is not recorded offline, so --publish decides which release workflow(s)
# come back; default "none" restores everything except them (see docs/offline-to-online.md).
copy_online_assets_lib_minimal() {
    local common="$BLUEPRINTX_ROOT/templates/python-common" shared="$BLUEPRINTX_ROOT/templates/common"
    local skeleton="$BLUEPRINTX_ROOT/templates/lib-minimal" dest="$PROJECT_PATH" wf
    mkdir -p "$dest/.github/workflows"
    for wf in tests secret_scan review_threads coderabbit_trigger review_retry pr-gate pr-reconcile; do
        cp "$common/.github/workflows/$wf.yaml" "$dest/.github/workflows/$wf.yaml"
    done
    case "$PUBLISH_TARGET" in
        pypi | both) envsubst '${PROJECT_NAME} ${GITHUB_USERNAME}' <"$skeleton/.github/workflows/release-pypi.yaml" >"$dest/.github/workflows/release-pypi.yaml" ;;
    esac
    case "$PUBLISH_TARGET" in
        test-pypi | both) envsubst '${PROJECT_NAME} ${GITHUB_USERNAME}' <"$skeleton/.github/workflows/release-test-pypi.yaml" >"$dest/.github/workflows/release-test-pypi.yaml" ;;
    esac
    cp "$skeleton/.github/workflows/docs.yaml" "$dest/.github/workflows/docs.yaml"
    cp "$shared/.github/CODEOWNERS" "$dest/.github/CODEOWNERS"
    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' <"$shared/SECURITY.md" >"$dest/SECURITY.md"
    cp "$common/.github/dependabot.yml" "$dest/.github/dependabot.yml"
    cp "$shared/.github/CLAUDE.md" "$dest/.github/CLAUDE.md"
    cp "$shared/.github/PULL_REQUEST_TEMPLATE.md" "$dest/.github/PULL_REQUEST_TEMPLATE.md"
    print_status "success" "GitHub assets copied (.github, SECURITY.md, publish=$PUBLISH_TARGET)"
}

# Mirrors the .github copy in bin/scaffold/ts_react_app.sh. No SECURITY.md or dependabot.yml —
# ts-common ships neither. --deploy-target decides the single deploy workflow, for the same
# reason --publish does above: the original choice is not recorded offline.
copy_online_assets_react() {
    local shared="$BLUEPRINTX_ROOT/templates/common" dest="$PROJECT_PATH"
    local deploy_root="$BLUEPRINTX_ROOT/templates/react-spa-webpack/optional/deploy"
    mkdir -p "$dest/.github/workflows"
    cp "$shared/.github/CLAUDE.md" "$dest/.github/CLAUDE.md"
    cp "$shared/.github/CODEOWNERS" "$dest/.github/CODEOWNERS"
    cp "$shared/.github/PULL_REQUEST_TEMPLATE.md" "$dest/.github/PULL_REQUEST_TEMPLATE.md"
    case "$DEPLOY_TARGET" in
        pages) cp "$deploy_root/pages/deploy-spa.yml" "$dest/.github/workflows/deploy-spa.yml" ;;
        vercel)
            cp "$deploy_root/vercel/deploy-vercel.yml" "$dest/.github/workflows/deploy-vercel.yml"
            cp "$deploy_root/vercel/vercel.json" "$dest/vercel.json"
            ;;
        none) print_status "info" "No --deploy-target given; skipped restoring a deploy workflow (add one manually if needed)." ;;
        *) exit_usage_error "--deploy-target must be none, pages or vercel" ;;
    esac
    print_status "success" "GitHub assets copied (.github, deploy-target=$DEPLOY_TARGET)"
}

copy_online_assets() {
    case "$TIER" in
        lib-minimal) copy_online_assets_lib_minimal ;;
        react-spa-webpack) copy_online_assets_react ;;
        *) copy_online_assets_service_tier ;;
    esac
}

# git_diffs/ is where a real offline user parks exported diffs — never rm -rf blindly.
# Removable only when it holds nothing but the .keep placeholder apply_offline_mode created.
remove_git_diffs_dir() {
    local dir="$PROJECT_PATH/git_diffs"
    [ -d "$dir" ] || return 0
    local extra
    extra="$(find "$dir" -mindepth 1 ! -name '.keep')"
    if [ -n "$extra" ]; then
        print_status "warning" "git_diffs/ has content beyond .keep — leaving it in place (manual follow-up)."
        return 0
    fi
    rm -rf "$dir"
    print_status "info" "Removed git_diffs/ (offline-only placeholder)"
}

# Mirrors the removal half of apply_offline_mode() in the 5 python bin/scaffold/python_*.sh
# scripts: bin/new_branch.sh, git_merge_to_main.sh, protect_branch.sh, the git-diff trio,
# and poe_tasks.offline.toml. bin/lib/common.sh is left alone — it is not offline-only.
remove_offline_only_python() {
    local dest="$PROJECT_PATH" f
    for f in bin/git_diff_export.sh bin/git_diff_apply.sh bin/git_diff_check.sh \
        bin/new_branch.sh bin/git_merge_to_main.sh bin/protect_branch.sh poe_tasks.offline.toml; do
        [ -f "$dest/$f" ] && rm -f "$dest/$f" && print_status "info" "Removed $f (offline-only)"
    done
    remove_git_diffs_dir
}

# Mirrors the removal half of apply_offline_mode() in bin/scaffold/ts_react_app.sh: no
# new_branch/git_merge_to_main/protect_branch or poe include there, so only the git-diff
# trio + git_diffs/ + the package.json script entries come back off.
remove_offline_only_react() {
    local dest="$PROJECT_PATH" f
    for f in bin/git_diff_export.sh bin/git_diff_apply.sh bin/git_diff_check.sh; do
        [ -f "$dest/$f" ] && rm -f "$dest/$f" && print_status "info" "Removed $f (offline-only)"
    done
    remove_git_diffs_dir
    strip_package_json_git_diff_scripts
}

remove_offline_only() {
    case "$TIER" in
        react-spa-webpack) remove_offline_only_react ;;
        *)
            remove_offline_only_python
            strip_poe_include
            restore_protect_branch_hook
            ;;
    esac
}

# Reverses add_poe_include() (bin/lib/common.sh): drops "poe_tasks.offline.toml" from
# poe_tasks.toml's [tool.poe] include list, and drops the whole table if it is then empty.
# Idempotent: a no-op when the entry is already absent (never scaffolded, or already promoted).
strip_poe_include() {
    local tasks="$PROJECT_PATH/poe_tasks.toml"
    [ -f "$tasks" ] || return 0
    python3 - "$tasks" <<'PY'
import re
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    text = fh.read()

if '"poe_tasks.offline.toml"' not in text:
    sys.exit(0)

match = re.search(r"\n\[tool\.poe\]\ninclude = \[([^\]]*)\]\n", text)
if not match:
    sys.exit(0)

entries = [e.strip() for e in match.group(1).split(",") if e.strip() and e.strip() != '"poe_tasks.offline.toml"']
replacement = f"\n[tool.poe]\ninclude = [{', '.join(entries)}]\n" if entries else "\n"
text = text[: match.start()] + replacement + text[match.end() :]

with open(path, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
    print_status "info" "Removed poe_tasks.offline.toml from poe_tasks.toml include list"
}

# Reverses swap_protect_branch_hook() (bin/scaffold/python_*.sh): drops the local
# protect-branch hook it inserted and restores the stock no-commit-to-branch hook as the
# first entry of the pre-commit-hooks repo block. Idempotent: a no-op when the local hook
# is already absent (never swapped, or already promoted).
restore_protect_branch_hook() {
    local pc="$PROJECT_PATH/.pre-commit-config.yaml"
    [ -f "$pc" ] || return 0
    python3 - "$pc" <<'PY'
import re
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    text = fh.read()

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
if local_hook not in text:
    sys.exit(0)

text = text.replace(local_hook, "repos:\n", 1)
text, count = re.subn(
    r"(- repo: https://github\.com/pre-commit/pre-commit-hooks\n(?:    rev:.*\n)?    hooks:\n)",
    r"\1      - id: no-commit-to-branch\n        args:\n          - --branch=main\n",
    text,
    count=1,
)
if count == 0:
    raise SystemExit("restore_protect_branch_hook: pre-commit-hooks repo block not found")

with open(path, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
    print_status "info" "Restored stock no-commit-to-branch hook in .pre-commit-config.yaml"
}

# Reverses the git:diff:* entries patch_package_json() added in ts_react_app.sh's
# apply_offline_mode(). Idempotent: json.dump of an already-clean scripts table is a no-op.
strip_package_json_git_diff_scripts() {
    local pkg="$PROJECT_PATH/package.json"
    [ -f "$pkg" ] || return 0
    python3 - "$pkg" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    pkg = json.load(fh)

scripts = pkg.get("scripts", {})
for key in ("git:diff:export", "git:diff:check", "git:diff:apply"):
    scripts.pop(key, None)

with open(path, "w", encoding="utf-8") as fh:
    json.dump(pkg, fh, indent=2)
    fh.write("\n")
PY
    print_status "info" "Removed git:diff:* scripts from package.json"
}

commit_promotion_changes() {
    [ -n "$(git -C "$PROJECT_PATH" status --porcelain)" ] || return 0
    git -C "$PROJECT_PATH" add -A
    git -C "$PROJECT_PATH" commit -q -m "chore: promote project to online GitHub workflow"
    print_status "success" "Committed promotion changes"
}

# gh repo create --source=. --push both creates the remote GitHub repo AND pushes the
# current branch in one step, provided the local commit above already landed.
create_remote_and_push() {
    local visibility_flag="--private"
    [ "$VISIBILITY" = "public" ] && visibility_flag="--public"
    (cd "$PROJECT_PATH" && gh repo create "$REPOSITORY" "$visibility_flag" --source=. --remote=origin --push) \
        || exit_error "Failed to create/push $REPOSITORY via gh repo create."
    print_status "success" "Created $REPOSITORY and pushed"
}

# Best-effort: a fresh repo can lag a moment behind API-visibility, and a solo maintainer's
# exact review policy is a judgment call this script does not prompt for — so a failure here
# warns rather than aborts an otherwise-complete promotion (the assets are already pushed).
apply_branch_protection() {
    [ "$SKIP_BRANCH_PROTECTION" = "true" ] && return 0
    local payload
    payload=$(
        cat <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
    )
    if gh api --method PUT "repos/$REPOSITORY/branches/main/protection" \
        -H "Accept: application/vnd.github+json" --input - <<<"$payload" >/dev/null 2>&1; then
        print_status "success" "Applied baseline branch protection on main"
    else
        print_status "warning" "Could not apply branch protection automatically; configure it on GitHub manually."
    fi
}

print_final_summary() {
    print_section "Promotion complete"
    print_status "success" "$PROJECT_PATH is now online as $REPOSITORY"
    print_status "info" "Re-run this script any time — every step here is idempotent."
}

main() {
    parse_args "$@"
    require_known_tier
    require_git_repo

    detect_state
    if [ "$HAS_ORIGIN" = "true" ] && [ "$HAS_GITHUB_ASSETS" = "true" ]; then
        print_status "success" "$PROJECT_PATH is already online (origin set, .github/workflows populated) — nothing to do."
        exit 0
    fi
    if [ "$HAS_ORIGIN" = "true" ] && [ "$HAS_GITHUB_ASSETS" != "true" ]; then
        exit_error "$PROJECT_PATH already has an 'origin' remote but no .github/workflows — ambiguous state (mid-promotion? a remote added by hand?). Refusing to guess; reconcile manually."
    fi

    require_clean_tree
    require_gh_ready
    resolve_identity

    print_section "Promoting $PROJECT_NAME ($TIER) to online"
    copy_online_assets
    remove_offline_only
    commit_promotion_changes
    create_remote_and_push
    apply_branch_protection
    print_final_summary
}

# Guarded so tests/test_promote_offline_to_online.sh can `source` this file (to exercise
# individual mutation functions against a fixture) without triggering a real run.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
