#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

TIERS=(ddd-service-native-db ddd-service-orm-db mvc-service-native-db mvc-service-orm-db api-service-native-db lib-minimal react-spa-webpack ts-lib bash-cli)

PROJECT_PATH=""
TIER=""
GITHUB_USERNAME="${GITHUB_USERNAME:-}"
VISIBILITY="private"
DEPLOY_TARGET="none"
PUBLISH_TARGET="none"
SKIP_BRANCH_PROTECTION=false
PROTECTION_APPLIED=false

usage() {
    cat <<'EOF'
Usage: bin/promote_offline_to_online.sh <project_path> --tier <tier> [options]

Required:
  <project_path>           Path to the offline-scaffolded project to promote.
  --tier <tier>             ddd-service-native-db | ddd-service-orm-db |
                             mvc-service-native-db | mvc-service-orm-db |
                             api-service-native-db | lib-minimal | react-spa-webpack |
                             ts-lib | bash-cli

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

require_flag_value() {
    [ $# -ge 2 ] || exit_usage_error "$1 requires a value"
}

require_valid_visibility() {
    case "$VISIBILITY" in
        public | private) ;;
        *) exit_usage_error "--visibility must be public or private" ;;
    esac
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
                require_flag_value "$@"
                TIER="$2"
                shift 2
                ;;
            --github-user)
                require_flag_value "$@"
                GITHUB_USERNAME="$2"
                shift 2
                ;;
            --visibility)
                require_flag_value "$@"
                VISIBILITY="$2"
                shift 2
                ;;
            --deploy-target)
                require_flag_value "$@"
                DEPLOY_TARGET="$2"
                shift 2
                ;;
            --publish)
                require_flag_value "$@"
                PUBLISH_TARGET="$2"
                shift 2
                ;;
            --skip-branch-protection)
                SKIP_BRANCH_PROTECTION=true
                shift
                ;;
            --)
                shift
                if [ $# -gt 0 ] && [ -z "$PROJECT_PATH" ]; then
                    PROJECT_PATH="$1"
                    shift
                fi
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
    require_valid_visibility
}

require_valid_tier_options() {
    case "$PUBLISH_TARGET" in
        none | pypi | test-pypi | both) ;;
        *) exit_usage_error "--publish must be none, pypi, test-pypi or both" ;;
    esac
    case "$DEPLOY_TARGET" in
        none | pages | vercel) ;;
        *) exit_usage_error "--deploy-target must be none, pages or vercel" ;;
    esac
    [ "$PUBLISH_TARGET" = "none" ] || [ "$TIER" = "lib-minimal" ] \
        || exit_usage_error "--publish applies to --tier lib-minimal only"
    [ "$DEPLOY_TARGET" = "none" ] || [ "$TIER" = "react-spa-webpack" ] \
        || exit_usage_error "--deploy-target applies to --tier react-spa-webpack only"
}

require_known_tier() {
    local tier_ok=false candidate
    for candidate in "${TIERS[@]}"; do
        [ "$candidate" = "$TIER" ] && tier_ok=true
    done
    [ "$tier_ok" = "true" ] || exit_usage_error "Unknown --tier '$TIER' (expected one of: ${TIERS[*]})"
    [ -f "$BLUEPRINTX_ROOT/templates/$TIER/skeleton.meta" ] \
        || exit_error "Tier '$TIER' has no templates/$TIER/skeleton.meta in this BlueprintX checkout — inventory missing, refusing to half-promote."
}

require_git_repo() {
    [ -d "$PROJECT_PATH" ] || exit_error "No such directory: $PROJECT_PATH"
    git -C "$PROJECT_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
        || exit_error "$PROJECT_PATH is not a git repository — refusing to promote."
    [ "$(git -C "$PROJECT_PATH" rev-parse --show-toplevel)" = "$(cd "$PROJECT_PATH" && pwd -P)" ] \
        || exit_error "$PROJECT_PATH is inside another git repository, not its root — refusing to promote the parent."
}

require_on_main() {
    local branch
    branch="$(git -C "$PROJECT_PATH" symbolic-ref --short HEAD 2>/dev/null || true)"
    [ "$branch" = "main" ] \
        || exit_error "$PROJECT_PATH is on '${branch:-a detached HEAD}', not main — check out main first (the push and branch protection both target main)."
}

require_clean_tree() {
    [ -z "$(git -C "$PROJECT_PATH" status --porcelain)" ] \
        || exit_error "$PROJECT_PATH has uncommitted changes — commit or stash them first, then re-run."
}

require_resumable_tree() {
    local line path
    while IFS= read -r line; do
        path="${line:3}"
        case "$path" in
            .github/* | SECURITY.md | vercel.json | package.json | poe_tasks.toml | poe_tasks.offline.toml \
                | .pre-commit-config.yaml | git_diffs/* | bin/git_diff_*.sh | bin/new_branch.sh \
                | bin/git_merge_to_main.sh | bin/protect_branch.sh) ;;
            *) exit_error "$PROJECT_PATH has changes outside a previous promotion (${path}) — commit or stash them first, then re-run." ;;
        esac
    done < <(git -C "$PROJECT_PATH" status --porcelain)
}

require_gh_ready() {
    command -v gh >/dev/null 2>&1 || exit_error "gh CLI not found — required to create the repo and apply branch protection."
    gh auth status >/dev/null 2>&1 || exit_error "gh is not authenticated — run 'gh auth login' first."
}

detect_state() {
    HAS_ORIGIN=false
    git -C "$PROJECT_PATH" remote get-url origin >/dev/null 2>&1 && HAS_ORIGIN=true

    HAS_GITHUB_ASSETS=false
    if [ -f "$PROJECT_PATH/.github/CODEOWNERS" ] \
        || [ -n "$(find "$PROJECT_PATH/.github/workflows" -mindepth 1 2>/dev/null)" ]; then
        HAS_GITHUB_ASSETS=true
    fi
}

resolve_identity() {
    [ -n "$GITHUB_USERNAME" ] || GITHUB_USERNAME="$(gh api user --jq .login || true)"
    [ -n "$GITHUB_USERNAME" ] || exit_error "Could not resolve a GitHub username; pass --github-user explicitly."
    PROJECT_NAME="$(basename "$(cd "$PROJECT_PATH" && pwd)")"
    PROJECT_DISPLAY_NAME="$(echo "$PROJECT_NAME" | tr '_-' '  ' | awk '{for (i = 1; i <= NF; i++) $i = toupper(substr($i, 1, 1)) substr($i, 2); print}')"
    REPOSITORY="$GITHUB_USERNAME/$PROJECT_NAME"
    export PROJECT_NAME PROJECT_DISPLAY_NAME GITHUB_USERNAME REPOSITORY
}

copy_online_assets_service_tier() {
    local common="$BLUEPRINTX_ROOT/templates/python-common" shared="$BLUEPRINTX_ROOT/templates/common"
    local dest="$PROJECT_PATH" wf
    mkdir -p "$dest/.github/workflows"
    for wf in tests review_threads coderabbit_trigger review_retry pr-gate pr-reconcile contract_drift release; do
        cp "$common/.github/workflows/$wf.yaml" "$dest/.github/workflows/$wf.yaml"
    done
    cp "$shared/docs_version/docs.yaml" "$dest/.github/workflows/docs.yaml"
    envsubst '${GITHUB_USERNAME}' <"$shared/.github/CODEOWNERS" >"$dest/.github/CODEOWNERS"
    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' <"$shared/SECURITY.md" >"$dest/SECURITY.md"
    cp "$common/.github/dependabot.yml" "$dest/.github/dependabot.yml"
    cp "$shared/.github/CLAUDE.md" "$dest/.github/CLAUDE.md"
    cp "$shared/.github/PULL_REQUEST_TEMPLATE.md" "$dest/.github/PULL_REQUEST_TEMPLATE.md"
    mkdir -p "$dest/.github/ISSUE_TEMPLATE" && cp "$shared/.github/ISSUE_TEMPLATE/feature_or_fix.md" "$dest/.github/ISSUE_TEMPLATE/feature_or_fix.md"
    print_status "success" "GitHub assets copied (.github, SECURITY.md)"
}

copy_online_assets_lib_minimal() {
    local common="$BLUEPRINTX_ROOT/templates/python-common" shared="$BLUEPRINTX_ROOT/templates/common"
    local skeleton="$BLUEPRINTX_ROOT/templates/lib-minimal" dest="$PROJECT_PATH" wf
    mkdir -p "$dest/.github/workflows"
    for wf in tests review_threads coderabbit_trigger review_retry pr-gate pr-reconcile; do
        cp "$common/.github/workflows/$wf.yaml" "$dest/.github/workflows/$wf.yaml"
    done
    case "$PUBLISH_TARGET" in
        pypi | both) envsubst '${PROJECT_NAME} ${GITHUB_USERNAME}' <"$skeleton/.github/workflows/release-pypi.yaml" >"$dest/.github/workflows/release-pypi.yaml" ;;
    esac
    case "$PUBLISH_TARGET" in
        test-pypi | both) envsubst '${PROJECT_NAME} ${GITHUB_USERNAME}' <"$skeleton/.github/workflows/release-test-pypi.yaml" >"$dest/.github/workflows/release-test-pypi.yaml" ;;
    esac
    cp "$skeleton/.github/workflows/docs.yaml" "$dest/.github/workflows/docs.yaml"
    envsubst '${GITHUB_USERNAME}' <"$shared/.github/CODEOWNERS" >"$dest/.github/CODEOWNERS"
    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' <"$shared/SECURITY.md" >"$dest/SECURITY.md"
    cp "$common/.github/dependabot.yml" "$dest/.github/dependabot.yml"
    cp "$shared/.github/CLAUDE.md" "$dest/.github/CLAUDE.md"
    cp "$shared/.github/PULL_REQUEST_TEMPLATE.md" "$dest/.github/PULL_REQUEST_TEMPLATE.md"
    mkdir -p "$dest/.github/ISSUE_TEMPLATE" && cp "$shared/.github/ISSUE_TEMPLATE/feature_or_fix.md" "$dest/.github/ISSUE_TEMPLATE/feature_or_fix.md"
    print_status "success" "GitHub assets copied (.github, SECURITY.md, publish=$PUBLISH_TARGET)"
}

copy_online_assets_react() {
    local shared="$BLUEPRINTX_ROOT/templates/common" dest="$PROJECT_PATH"
    local deploy_root="$BLUEPRINTX_ROOT/templates/react-spa-webpack/optional/deploy"
    mkdir -p "$dest/.github/workflows"
    cp -r "$BLUEPRINTX_ROOT/templates/ts-common/.github/." "$dest/.github"
    cp "$BLUEPRINTX_ROOT/templates/ts-common/dependabot.yml" "$dest/.github/dependabot.yml"
    cp "$shared/.github/CLAUDE.md" "$dest/.github/CLAUDE.md"
    envsubst '${GITHUB_USERNAME}' <"$shared/.github/CODEOWNERS" >"$dest/.github/CODEOWNERS"
    cp "$shared/.github/PULL_REQUEST_TEMPLATE.md" "$dest/.github/PULL_REQUEST_TEMPLATE.md"
    mkdir -p "$dest/.github/ISSUE_TEMPLATE" && cp "$shared/.github/ISSUE_TEMPLATE/feature_or_fix.md" "$dest/.github/ISSUE_TEMPLATE/feature_or_fix.md"
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

copy_online_assets_ts_lib() {
    local shared="$BLUEPRINTX_ROOT/templates/common" skeleton="$BLUEPRINTX_ROOT/templates/ts-lib"
    local dest="$PROJECT_PATH" wf
    mkdir -p "$dest/.github/workflows"
    cp -r "$BLUEPRINTX_ROOT/templates/ts-common/.github/." "$dest/.github"
    cp "$BLUEPRINTX_ROOT/templates/ts-common/dependabot.yml" "$dest/.github/dependabot.yml"
    for wf in docs docs-deploy pack-smoke; do
        cp "$skeleton/.github/workflows/$wf.yml" "$dest/.github/workflows/$wf.yml"
    done
    envsubst '${PROJECT_NAME}' <"$skeleton/.github/workflows/release-npm.yml" >"$dest/.github/workflows/release-npm.yml"
    copy_shared_github_overlay
    print_status "success" "GitHub assets copied (.github)"
}

copy_online_assets_bash_cli() {
    local skeleton="$BLUEPRINTX_ROOT/templates/bash-cli" dest="$PROJECT_PATH"
    mkdir -p "$dest/.github/workflows"
    cp "$skeleton/.github/workflows/ci.yml" "$dest/.github/workflows/ci.yml"
    envsubst '${PROJECT_NAME}' <"$skeleton/.github/workflows/release.yml" >"$dest/.github/workflows/release.yml"
    cp "$BLUEPRINTX_ROOT/templates/common/.github/dependabot.yml" "$dest/.github/dependabot.yml"
    copy_shared_github_overlay
    print_status "success" "GitHub assets copied (.github)"
}

copy_shared_github_overlay() {
    local shared="$BLUEPRINTX_ROOT/templates/common" dest="$PROJECT_PATH"
    cp "$shared/.github/CLAUDE.md" "$dest/.github/CLAUDE.md"
    envsubst '${GITHUB_USERNAME}' <"$shared/.github/CODEOWNERS" >"$dest/.github/CODEOWNERS"
    cp "$shared/.github/PULL_REQUEST_TEMPLATE.md" "$dest/.github/PULL_REQUEST_TEMPLATE.md"
    mkdir -p "$dest/.github/ISSUE_TEMPLATE" && cp "$shared/.github/ISSUE_TEMPLATE/feature_or_fix.md" "$dest/.github/ISSUE_TEMPLATE/feature_or_fix.md"
}

copy_secret_scan_if_keyed() {
    case "$TIER" in react-spa-webpack | ts-lib | bash-cli) return 0 ;; esac
    [ -n "${GITGUARDIAN_API_KEY:-}" ] || return 0
    cp "$BLUEPRINTX_ROOT/templates/python-common/.github/workflows/secret_scan.yaml" \
        "$PROJECT_PATH/.github/workflows/secret_scan.yaml"
}

copy_online_assets() {
    case "$TIER" in
        lib-minimal) copy_online_assets_lib_minimal ;;
        react-spa-webpack) copy_online_assets_react ;;
        ts-lib) copy_online_assets_ts_lib ;;
        bash-cli) copy_online_assets_bash_cli ;;
        *) copy_online_assets_service_tier ;;
    esac
    copy_secret_scan_if_keyed
}

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

remove_offline_only_python() {
    local dest="$PROJECT_PATH" f
    for f in bin/git_diff_export.sh bin/git_diff_apply.sh bin/git_diff_check.sh \
        bin/new_branch.sh bin/git_merge_to_main.sh bin/protect_branch.sh poe_tasks.offline.toml; do
        [ -f "$dest/$f" ] && rm -f "$dest/$f" && print_status "info" "Removed $f (offline-only)"
    done
    remove_git_diffs_dir
}

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
        react-spa-webpack | ts-lib | bash-cli) remove_offline_only_react ;;
        *)
            remove_offline_only_python
            strip_poe_include
            restore_protect_branch_hook
            ;;
    esac
}

strip_poe_include() {
    local tasks="$PROJECT_PATH/poe_tasks.toml"
    [ -f "$tasks" ] || return 0
    local outcome
    outcome="$(python3 - "$tasks" <<'PY'
import re
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    text = fh.read()

if '"poe_tasks.offline.toml"' not in text:
    print("absent")
    sys.exit(0)

match = re.search(r"\n\[tool\.poe\]\ninclude = \[([^\]]*)\]\n", text)
if not match:
    sys.exit("strip_poe_include: poe_tasks.offline.toml is listed but the [tool.poe] include table has an unexpected shape — edit poe_tasks.toml by hand, then re-run.")

entries = [e.strip() for e in match.group(1).split(",") if e.strip() and e.strip() != '"poe_tasks.offline.toml"']
# An empty include drops the whole table only when no sibling key follows; otherwise the
# header stays, or `envfile`/`executor` would be re-parented under the previous table.
rest = text[match.end():]
if entries:
    replacement = f"\n[tool.poe]\ninclude = [{', '.join(entries)}]\n"
elif rest.strip() and not rest.lstrip().startswith("["):
    replacement = "\n[tool.poe]\n"
else:
    replacement = "\n"
text = text[: match.start()] + replacement + text[match.end() :]

with open(path, "w", encoding="utf-8") as fh:
    fh.write(text)
print("removed")
PY
)"
    [ "$outcome" = "removed" ] && print_status "info" "Removed poe_tasks.offline.toml from poe_tasks.toml include list"
    return 0
}

restore_protect_branch_hook() {
    local pc="$PROJECT_PATH/.pre-commit-config.yaml"
    [ -f "$pc" ] || return 0
    local outcome
    outcome="$(python3 - "$pc" <<'PY'
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
    if "id: protect-branch" in text:
        sys.exit("restore_protect_branch_hook: a protect-branch hook is present but not in the shape swap_protect_branch_hook writes — restore no-commit-to-branch by hand, then re-run.")
    print("absent")
    sys.exit(0)

text = text.replace(local_hook, "repos:\n", 1)
if "id: no-commit-to-branch" in text:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("restored")
    sys.exit(0)
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
print("restored")
PY
)"
    [ "$outcome" = "restored" ] && print_status "info" "Restored stock no-commit-to-branch hook in .pre-commit-config.yaml"
    return 0
}

strip_package_json_git_diff_scripts() {
    local pkg="$PROJECT_PATH/package.json"
    [ -f "$pkg" ] || return 0
    local outcome
    outcome="$(python3 - "$pkg" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    pkg = json.load(fh)

scripts = pkg.get("scripts", {})
keys = [k for k in ("git:diff:export", "git:diff:check", "git:diff:apply") if k in scripts]
if not keys:
    print("absent")
    sys.exit(0)
for key in keys:
    del scripts[key]

with open(path, "w", encoding="utf-8") as fh:
    json.dump(pkg, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
print("removed")
PY
)"
    [ "$outcome" = "removed" ] && print_status "info" "Removed git:diff:* scripts from package.json"
    return 0
}

commit_promotion_changes() {
    [ -n "$(git -C "$PROJECT_PATH" status --porcelain)" ] || return 0
    git -C "$PROJECT_PATH" add -A
    SKIP=no-commit-to-branch scaffold_git_commit "$PROJECT_PATH" "chore: promote project to online GitHub workflow"
    print_status "success" "Committed promotion changes"
}

has_pushed_remote_ref() {
    git -C "$PROJECT_PATH" show-ref --verify --quiet refs/remotes/origin/main
}

create_remote() {
    local visibility_flag="--private"
    [ "$VISIBILITY" = "public" ] && visibility_flag="--public"
    (cd "$PROJECT_PATH" && gh repo create "$REPOSITORY" "$visibility_flag" --source=. --remote=origin) \
        || exit_error "Failed to create $REPOSITORY via gh repo create. If it now exists on GitHub, add it with: git -C $PROJECT_PATH remote add origin <url> && git -C $PROJECT_PATH push -u origin HEAD"
    print_status "success" "Created $REPOSITORY"
}

push_initial_commit() {
    git -C "$PROJECT_PATH" push -q -u origin HEAD \
        || exit_error "$REPOSITORY was created but the push failed — promotion is INCOMPLETE. Run: git -C $PROJECT_PATH push -u origin HEAD"
    has_pushed_remote_ref \
        || exit_error "$REPOSITORY was created but main was not pushed — promotion is INCOMPLETE. Run: git -C $PROJECT_PATH push -u origin HEAD"
    print_status "success" "Pushed $REPOSITORY"
}

set_secret_scan_key() {
    [ -f "$PROJECT_PATH/.github/workflows/secret_scan.yaml" ] || return 0
    [ -n "${GITGUARDIAN_API_KEY:-}" ] || return 0
    printf '%s' "$GITGUARDIAN_API_KEY" | gh secret set GITGUARDIAN_API_KEY --repo "$REPOSITORY" >/dev/null 2>&1 \
        && print_status "success" "GitGuardian secret-scan key set on $REPOSITORY" \
        || print_status "warning" "Could not set GITGUARDIAN_API_KEY on $REPOSITORY — secret_scan.yaml will fail until you run: gh secret set GITGUARDIAN_API_KEY --repo $REPOSITORY (or delete the workflow)"
}

apply_branch_protection() {
    [ "$SKIP_BRANCH_PROTECTION" = "true" ] && return 0
    PROTECTION_APPLIED=false
    if [ ! -x "$PROJECT_PATH/bin/enable_repo_rules.sh" ]; then
        print_status "warning" "$PROJECT_PATH/bin/enable_repo_rules.sh is missing; configure the branch ruleset on GitHub manually."
        return 0
    fi
    (cd "$PROJECT_PATH" && bash bin/enable_repo_rules.sh) || true
    if (cd "$PROJECT_PATH" && bash bin/enable_repo_rules.sh verify); then
        PROTECTION_APPLIED=true
    fi
}

print_final_summary() {
    print_section "Promotion complete"
    print_status "success" "$PROJECT_PATH is now online as $REPOSITORY"
    [ "$PROTECTION_APPLIED" = "true" ] || print_status "warning" "Branch protection on main is NOT in place (skipped or failed) — set it up on GitHub."
    print_status "info" "Re-running before the first push resumes the promotion; afterwards the project reads as online and nothing is repeated."
}

main() {
    parse_args "$@"
    require_known_tier
    require_valid_tier_options
    require_git_repo

    detect_state
    if [ "$HAS_ORIGIN" = "true" ] && [ "$HAS_GITHUB_ASSETS" = "true" ] && ! has_pushed_remote_ref; then
        exit_error "$PROJECT_PATH has an 'origin' and .github/workflows but nothing was ever pushed (a failed first push?) — not online. Run: git -C $PROJECT_PATH push -u origin HEAD"
    fi
    if [ "$HAS_ORIGIN" = "true" ] && [ "$HAS_GITHUB_ASSETS" = "true" ]; then
        print_status "success" "$PROJECT_PATH is already online (origin set, .github/workflows populated) — nothing to do."
        exit 0
    fi
    if [ "$HAS_ORIGIN" = "true" ] && [ "$HAS_GITHUB_ASSETS" != "true" ]; then
        exit_error "$PROJECT_PATH already has an 'origin' remote but no .github/workflows — ambiguous state (mid-promotion? a remote added by hand?). Refusing to guess; reconcile manually."
    fi

    require_on_main
    if [ "$HAS_GITHUB_ASSETS" = "true" ]; then
        print_status "warning" "$PROJECT_PATH has .github/workflows but no origin — resuming a previous promotion; workflows will be overwritten from the templates."
        require_resumable_tree
    else
        require_clean_tree
    fi
    require_gh_ready
    resolve_identity

    print_section "Promoting $PROJECT_NAME ($TIER) to online"
    copy_online_assets
    remove_offline_only
    commit_promotion_changes
    create_remote
    set_secret_scan_key
    push_initial_commit
    apply_branch_protection
    print_final_summary
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
