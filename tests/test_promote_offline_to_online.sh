#!/bin/bash

set -uo pipefail
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

test_supported_tiers_are_known() {
    local tier
    for tier in api-service-native-db ts-lib bash-cli; do
        expect_refuses_with "$tier is a known tier (reaches the git-repo check)" "not a git repository" "$WORK_DIR" --tier "$tier"
    done
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
    local before after
    before="$(git -C "$dir" rev-parse HEAD)$(git -C "$dir" status --porcelain)"
    expect_succeeds "already-online project is a clean no-op" "$dir" --tier lib-minimal
    after="$(git -C "$dir" rev-parse HEAD)$(git -C "$dir" status --porcelain)"
    if [ "$before" = "$after" ]; then
        echo "ok: the no-op left HEAD and the tree untouched"
    else
        echo "FAIL (no-op untouched): the already-online run changed the project"
        int_failures=$((int_failures + 1))
    fi
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

test_copy_manifests_match_templates() {
    local tier dir
    for tier in ddd-service-native-db ddd-service-orm-db mvc-service-native-db mvc-service-orm-db api-service-native-db lib-minimal react-spa-webpack ts-lib bash-cli; do
        dir="$WORK_DIR/manifest-$tier"
        mkdir -p "$dir"
        if bash -c 'source "$1"; PROJECT_PATH="$2"; TIER="$3"; GITHUB_USERNAME=octo; PROJECT_NAME=demo; PROJECT_DISPLAY_NAME=Demo; REPOSITORY=octo/demo; export PROJECT_NAME GITHUB_USERNAME PROJECT_DISPLAY_NAME REPOSITORY; copy_online_assets' _ "$PROMOTE_SCRIPT" "$dir" "$tier" >/dev/null 2>&1 \
            && grep -q '@octo' "$dir/.github/CODEOWNERS" && ! grep -q '\${' "$dir/.github/CODEOWNERS"; then
            echo "ok: $tier copy manifest resolves against templates/ and renders CODEOWNERS"
        else
            echo "FAIL ($tier): copy manifest failed against templates/ or CODEOWNERS kept a placeholder"
            int_failures=$((int_failures + 1))
        fi
    done
    for tier in react-spa-webpack ts-lib bash-cli; do
        if grep -q 'cooldown:' "$WORK_DIR/manifest-$tier/.github/dependabot.yml"; then
            echo "ok: $tier promotion restores dependabot.yml with a cooldown"
        else
            echo "FAIL ($tier): promotion did not restore .github/dependabot.yml"
            int_failures=$((int_failures + 1))
        fi
    done
    for tier in ts-lib bash-cli; do
        local wf=release.yml
        [ "$tier" = ts-lib ] && wf=release-npm.yml
        if grep -q 'demo' "$WORK_DIR/manifest-$tier/.github/workflows/$wf" \
            && ! grep -q '\${PROJECT_NAME}' "$WORK_DIR/manifest-$tier/.github/workflows/$wf"; then
            echo "ok: $tier release workflow rendered with PROJECT_NAME"
        else
            echo "FAIL ($tier): $wf not rendered with PROJECT_NAME"
            int_failures=$((int_failures + 1))
        fi
    done
    for tier in react-spa-webpack ts-lib; do
        if [ -f "$WORK_DIR/manifest-$tier/.github/workflows/lint.yml" ]; then
            echo "ok: $tier carries the ts-common workflows"
        else
            echo "FAIL ($tier): ts-common .github/workflows missing from the copy manifest"
            int_failures=$((int_failures + 1))
        fi
    done
}

test_nested_repo_is_refused() {
    local parent
    parent="$(make_git_repo "nested-parent")"
    mkdir -p "$parent/child"
    expect_refuses_with "a directory inside another repo is refused" "inside another git repository" "$parent/child" --tier lib-minimal
}

test_double_dash_takes_the_path() {
    local out
    out="$("$PROMOTE_SCRIPT" --tier lib-minimal -- "$WORK_DIR/nope" 2>&1)" || true
    if [[ "$out" == *"No such directory"* ]]; then
        echo "ok: -- passes the project path through"
    else
        echo "FAIL (-- passes the project path through): $out"
        int_failures=$((int_failures + 1))
    fi
}

test_resume_refuses_foreign_dirty_path() {
    local dir
    dir="$(make_git_repo "resume-foreign")"
    mkdir -p "$dir/.github"
    echo "* @example" >"$dir/.github/CODEOWNERS"
    echo "mine" >"$dir/src_notes.txt"
    expect_refuses_with "resume refuses a dirty path outside the promotion's own" "changes outside a previous promotion" "$dir" --tier lib-minimal
}

test_secret_is_set_before_the_push() {
    local dir bare log
    dir="$(make_git_repo "secret-order")"
    bare="$WORK_DIR/secret-order.git"
    git init -q --bare "$bare"
    mkdir -p "$dir/.github/workflows"
    echo "name: s" >"$dir/.github/workflows/secret_scan.yaml"
    git -C "$dir" add -A
    git -C "$dir" commit -q -m "chore: seed"
    log="$WORK_DIR/secret-order.log"
    : >"$log"
    GITGUARDIAN_API_KEY=k bash -c '
        source "$1"
        PROJECT_PATH="$2"; REPOSITORY=o/r; VISIBILITY=private; BARE="$3"; LOG="$4"
        gh() {
            if [ "$1 $2" = "repo create" ]; then
                echo "create $*" >>"$LOG"
                git -C "$PROJECT_PATH" remote add origin "$BARE"
            else
                cat >/dev/null
                echo "secret pushed=$(git -C "$BARE" rev-parse --verify -q refs/heads/main >/dev/null && echo yes || echo no)" >>"$LOG"
            fi
        }
        create_remote; set_secret_scan_key; push_initial_commit
    ' _ "$PROMOTE_SCRIPT" "$dir" "$bare" "$log" >/dev/null 2>&1
    if grep -q '^secret pushed=no' "$log" && ! grep -q -- '--push' "$log" \
        && git -C "$bare" rev-parse --verify -q refs/heads/main >/dev/null; then
        echo "ok: the secret is set before the first push"
    else
        echo "FAIL (secret before push): $(tr '\n' '|' <"$log")"
        int_failures=$((int_failures + 1))
    fi
}

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
    test_supported_tiers_are_known
    test_not_a_git_repo
    test_dirty_tree
    test_gh_unauthenticated
    test_invalid_tier_options
    test_origin_without_assets_is_ambiguous
    test_already_online_is_a_noop
    test_origin_never_pushed_is_not_online
    test_flag_without_value
    test_secret_is_set_before_the_push
    test_nested_repo_is_refused
    test_double_dash_takes_the_path
    test_resume_refuses_foreign_dirty_path
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
