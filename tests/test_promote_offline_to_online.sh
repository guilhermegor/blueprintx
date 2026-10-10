#!/bin/bash
# Should-fail regression tests for bin/promote_offline_to_online.sh (blueprintx#382).
#
# The dangerous direction is a FALSE PASS: a half-promoted project (assets copied, no repo
# created; or a repo created against a dirty tree) reporting success. So the tests that matter
# are the refusal paths — a suite that only proves the happy path would have passed against the
# very defect this script exists to prevent (same shape as bin/ci/check_git_remote_guard.sh).
#
# Runs the real script as a subprocess against throwaway local git repos — no network, no real
# `gh` auth required (a fake `gh` shim shadows the real one in every test).
#
# Usage: bash tests/test_promote_offline_to_online.sh

set -uo pipefail
# Run as a git hook, GIT_DIR points at the host repo and every `git -C <tmp>` below writes there.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMOTE_SCRIPT="$REPO_ROOT/bin/promote_offline_to_online.sh"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

int_failures=0

make_git_repo() {
    local dir="$WORK_DIR/$1"
    mkdir -p "$dir"
    git -C "$dir" init -q -b main
    git -C "$dir" config user.email "test@example.com"
    git -C "$dir" config user.name "Test"
    echo "hello" >"$dir/README.md"
    git -C "$dir" add -A
    git -C "$dir" commit -q -m "chore: initial commit"
    echo "$dir"
}

# A fake `gh` ahead of the real one on PATH for EVERY test: the real gh may be authenticated on a
# developer machine, and a regression in an earlier check must refuse here, never reach
# `gh repo create` with real credentials.
fake_gh_bin_dir() {
    local dir="$WORK_DIR/fake-gh-bin"
    mkdir -p "$dir"
    cat >"$dir/gh" <<'EOF'
#!/bin/bash
case "$1 $2" in
    "auth status") exit 1 ;;
    *) exit 0 ;;
esac
EOF
    chmod +x "$dir/gh"
    echo "$dir"
}

# The refusal must come from the named check: a nonzero exit alone also describes "not a git
# repo", which every other refusal test would otherwise hide behind.
expect_refuses_with() {
    local desc="$1" needle="$2" out
    shift 2
    if out="$("$PROMOTE_SCRIPT" "$@" 2>&1)"; then
        echo "FAIL ($desc): expected a refusal (nonzero exit), got success"
        int_failures=$((int_failures + 1))
    elif [[ "$out" == *"$needle"* ]]; then
        echo "ok: $desc"
    else
        echo "FAIL ($desc): refused, but not by the expected check ($needle)"
        int_failures=$((int_failures + 1))
    fi
}

expect_succeeds() {
    local desc="$1"
    shift
    if "$PROMOTE_SCRIPT" "$@" >/dev/null 2>&1; then
        echo "ok: $desc"
    else
        echo "FAIL ($desc): expected success (exit 0), got a refusal"
        int_failures=$((int_failures + 1))
    fi
}

PATH="$(fake_gh_bin_dir):$PATH"

test_unknown_tier() {
    expect_refuses_with "unknown --tier is refused" "Unknown --tier" "$WORK_DIR/nonexistent" --tier not-a-real-tier
}

test_not_a_git_repo() {
    local dir="$WORK_DIR/plain-dir"
    mkdir -p "$dir"
    expect_refuses_with "a non-git directory is refused" "not a git repository" "$dir" --tier lib-minimal
}

test_dirty_tree() {
    local dir
    dir="$(make_git_repo "dirty-tree")"
    echo "uncommitted" >"$dir/scratch.txt"
    expect_refuses_with "an uncommitted change is refused" "uncommitted changes" "$dir" --tier lib-minimal
}

test_gh_unauthenticated() {
    local dir
    dir="$(make_git_repo "gh-unauth")"
    expect_refuses_with "gh not authenticated is refused" "not authenticated" "$dir" --tier lib-minimal
}

test_invalid_tier_options() {
    local dir="$WORK_DIR/opts"
    mkdir -p "$dir"
    expect_refuses_with "an invalid --publish value is refused" "--publish must be" "$dir" --tier lib-minimal --publish bogus
    expect_refuses_with "an invalid --deploy-target value is refused" "--deploy-target must be" "$dir" --tier react-spa-webpack --deploy-target bogus
    expect_refuses_with "--publish on a non-lib tier is refused" "applies to --tier lib-minimal only" "$dir" --tier mvc-service-native-db --publish pypi
    expect_refuses_with "--deploy-target on a non-react tier is refused" "applies to --tier react-spa-webpack only" "$dir" --tier lib-minimal --deploy-target pages
}

test_origin_without_assets_is_ambiguous() {
    local dir
    dir="$(make_git_repo "origin-no-assets")"
    git -C "$dir" remote add origin "https://github.com/example/does-not-exist.git"
    expect_refuses_with "origin set without .github/workflows is refused (ambiguous)" "ambiguous state" "$dir" --tier lib-minimal
}

test_already_online_is_a_noop() {
    local dir
    dir="$(make_git_repo "already-online")"
    git -C "$dir" remote add origin "https://github.com/example/does-not-exist.git"
    mkdir -p "$dir/.github/workflows"
    echo "name: tests" >"$dir/.github/workflows/tests.yaml"
    git -C "$dir" add -A
    git -C "$dir" commit -q -m "chore: seed github assets"
    git -C "$dir" update-ref refs/remotes/origin/main HEAD
    expect_succeeds "already-online project is a clean no-op" "$dir" --tier lib-minimal
}

test_origin_never_pushed_is_not_online() {
    local dir
    dir="$(make_git_repo "never-pushed")"
    git -C "$dir" remote add origin "https://github.com/example/does-not-exist.git"
    mkdir -p "$dir/.github/workflows"
    echo "name: tests" >"$dir/.github/workflows/tests.yaml"
    git -C "$dir" add -A
    git -C "$dir" commit -q -m "chore: seed github assets"
    expect_refuses_with "origin + workflows but no pushed ref is refused, not 'already online'" "nothing was ever pushed" "$dir" --tier lib-minimal
}

test_flag_without_value() {
    expect_refuses_with "a value flag with no value is refused with usage" "requires a value" "$WORK_DIR/x" --tier
}

# react-spa-webpack with --deploy-target none writes no workflow, so "online" must key on a file
# every tier writes (CODEOWNERS), or a promoted project reads as the ambiguous state forever.
test_react_without_workflows_reads_as_online() {
    local dir
    dir="$(make_git_repo "react-online")"
    git -C "$dir" remote add origin "https://github.com/example/does-not-exist.git"
    mkdir -p "$dir/.github/workflows"
    echo "* @example" >"$dir/.github/CODEOWNERS"
    git -C "$dir" add -A
    git -C "$dir" commit -q -m "chore: seed github assets"
    git -C "$dir" update-ref refs/remotes/origin/main HEAD
    expect_succeeds "react project promoted with no deploy workflow is a clean no-op" "$dir" --tier react-spa-webpack
}

# Dropping the whole [tool.poe] table is only safe when include was its only key; a sibling key
# would otherwise be re-parented under the previous table with no error.
test_poe_strip_keeps_sibling_keys() {
    local dir="$WORK_DIR/poe-siblings"
    mkdir -p "$dir"
    printf '[tool.poe.tasks]\nlint = "ruff check ."\n\n[tool.poe]\ninclude = ["poe_tasks.offline.toml"]\nenvfile = ".env"\n' >"$dir/poe_tasks.toml"
    if bash -c 'source "$1"; PROJECT_PATH="$2"; strip_poe_include' _ "$PROMOTE_SCRIPT" "$dir" >/dev/null 2>&1 \
        && grep -q '^\[tool\.poe\]$' "$dir/poe_tasks.toml" \
        && grep -q '^envfile = ' "$dir/poe_tasks.toml" \
        && ! grep -q 'poe_tasks.offline.toml' "$dir/poe_tasks.toml"; then
        echo "ok: poe include strip keeps the [tool.poe] table when siblings follow"
    else
        echo "FAIL (poe include strip keeps siblings): envfile was re-parented or the strip failed"
        int_failures=$((int_failures + 1))
    fi
}

# Executes every tier's copy manifest against the real templates/ tree, so a renamed or deleted
# template fails here instead of mid-copy on a user's project; CODEOWNERS must be rendered.
test_copy_manifests_match_templates() {
    local tier dir
    for tier in ddd-service-native-db ddd-service-orm-db mvc-service-native-db mvc-service-orm-db lib-minimal react-spa-webpack; do
        dir="$WORK_DIR/manifest-$tier"
        mkdir -p "$dir"
        if bash -c 'source "$1"; PROJECT_PATH="$2"; TIER="$3"; GITHUB_USERNAME=octo; PROJECT_DISPLAY_NAME=Demo; REPOSITORY=octo/demo; export GITHUB_USERNAME PROJECT_DISPLAY_NAME REPOSITORY; copy_online_assets' _ "$PROMOTE_SCRIPT" "$dir" "$tier" >/dev/null 2>&1 \
            && grep -q '@octo' "$dir/.github/CODEOWNERS" && ! grep -q '\${' "$dir/.github/CODEOWNERS"; then
            echo "ok: $tier copy manifest resolves against templates/ and renders CODEOWNERS"
        else
            echo "FAIL ($tier): copy manifest failed against templates/ or CODEOWNERS kept a placeholder"
            int_failures=$((int_failures + 1))
        fi
    done
}

# The restored no-commit-to-branch hook must not block the promotion commit on main, and no
# OTHER hook may be skipped: the stub refuses unless SKIP is exactly that one hook id.
test_promotion_commit_skips_only_no_commit_to_branch() {
    local dir
    dir="$(make_git_repo "commit-skip")"
    printf '#!/bin/bash\n[ "${SKIP:-}" = "no-commit-to-branch" ] || { echo "SKIP=${SKIP:-}" >&2; exit 1; }\n' >"$dir/.git/hooks/pre-commit"
    chmod +x "$dir/.git/hooks/pre-commit"
    echo "promoted" >"$dir/promoted.txt"
    if bash -c 'source "$1"; PROJECT_PATH="$2"; commit_promotion_changes' _ "$PROMOTE_SCRIPT" "$dir" >/dev/null 2>&1 \
        && [ -z "$(git -C "$dir" status --porcelain)" ]; then
        echo "ok: promotion commit skips only no-commit-to-branch"
    else
        echo "FAIL (promotion commit skips only no-commit-to-branch): commit did not land"
        int_failures=$((int_failures + 1))
    fi
}

# White-box: sources the script (guarded — see its trailing BASH_SOURCE check) to call its
# mutation functions directly against a fixture, without a real `gh repo create`/network call.
# Runs in its own `bash -c` subprocess: the sourced script's `set -euo pipefail` must not leak
# into this harness's own shell.
test_mutations_on_offline_fixture() {
    local dir="$WORK_DIR/mutation-fixture"
    mkdir -p "$dir/bin" "$dir/git_diffs"
    echo "#!/bin/bash" >"$dir/bin/protect_branch.sh"
    echo "#!/bin/bash" >"$dir/bin/git_diff_export.sh"
    touch "$dir/git_diffs/.keep"
    echo 'unwanted' >"$dir/git_diffs/user_left_this.txt"
    cat >"$dir/poe_tasks.toml" <<'EOF'
[tool.poe.tasks]
lint = "ruff check ."

[tool.poe]
include = ["poe_tasks.offline.toml"]
EOF
    cat >"$dir/.pre-commit-config.yaml" <<'EOF'
repos:
  - repo: local
    hooks:
      - id: protect-branch
        name: block direct commits to main/master
        entry: bash bin/protect_branch.sh
        language: system
        always_run: true
        pass_filenames: false
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
EOF

    bash -c '
        set -euo pipefail
        source "'"$PROMOTE_SCRIPT"'"
        PROJECT_PATH="'"$dir"'"
        TIER="lib-minimal"
        remove_offline_only
        [ ! -f "$PROJECT_PATH/bin/protect_branch.sh" ] || exit 1
        [ ! -f "$PROJECT_PATH/bin/git_diff_export.sh" ] || exit 1
        [ -f "$PROJECT_PATH/git_diffs/user_left_this.txt" ] || exit 1
        ! grep -q "poe_tasks.offline.toml" "$PROJECT_PATH/poe_tasks.toml" || exit 1
        ! grep -q "id: protect-branch" "$PROJECT_PATH/.pre-commit-config.yaml" || exit 1
        grep -q "id: no-commit-to-branch" "$PROJECT_PATH/.pre-commit-config.yaml" || exit 1
    '
    if [ $? -eq 0 ]; then
        echo "ok: offline-only removal + poe/pre-commit restore, git_diffs/ user content preserved"
    else
        echo "FAIL: offline-only removal did not produce the expected fixture state"
        int_failures=$((int_failures + 1))
    fi
}

main() {
    test_unknown_tier
    test_not_a_git_repo
    test_dirty_tree
    test_gh_unauthenticated
    test_invalid_tier_options
    test_origin_without_assets_is_ambiguous
    test_already_online_is_a_noop
    test_origin_never_pushed_is_not_online
    test_flag_without_value
    test_react_without_workflows_reads_as_online
    test_poe_strip_keeps_sibling_keys
    test_copy_manifests_match_templates
    test_promotion_commit_skips_only_no_commit_to_branch
    test_mutations_on_offline_fixture

    if [ "$int_failures" -eq 0 ]; then
        echo "All promote_offline_to_online.sh refusal-path tests passed."
        exit 0
    fi
    echo "$int_failures promote_offline_to_online.sh test(s) failed." >&2
    exit 1
}

main
