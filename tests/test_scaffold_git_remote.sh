#!/bin/bash
# Should-fail regression tests for bin/lib/scaffold_git_remote.sh (blueprintx#732).
#
# The first push must land AFTER the GitGuardian key is set, or the first secret_scan run on
# `main` of every new repo goes red. A logging `gh` stub plus a local bare remote make the order
# observable: the stub records whether `main` already exists on the remote when the secret is set.
#
# Usage: bash tests/test_scaffold_git_remote.sh

set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

# Runs scaffold_create_github_repo against a throwaway repo; $1 = "ok" or "fail" (push outcome).
# Prints the stub's log, then the function's exit status.
run_create() {
    local str_mode="$1" dir="$WORK_DIR/proj-$1" bare="$WORK_DIR/$1.git" log="$WORK_DIR/$1.log"
    mkdir -p "$dir"
    git -C "$dir" init -q -b main
    git -C "$dir" -c user.email=t@example.com -c user.name=T commit -q --allow-empty -m "chore: seed"
    git init -q --bare "$bare"
    git -C "$dir" remote add origin "$bare"
    : >"$log"
    printf 'y\n1\n' | GITGUARDIAN_API_KEY=k bash -c '
        source "$1/bin/lib/common.sh"; source "$1/bin/lib/scaffold_git_remote.sh"
        PROJECT_PATH="$2"; BARE="$3"; LOG="$4"; MODE="$5"
        GITHUB_USERNAME=o; PROJECT_NAME=r; PROJECT_DESCRIPTION=d
        scaffold_kanban_setup() { :; }
        gh() {
            case "$1 $2" in
            "repo create")
                echo "create $*" >>"$LOG"
                # Real gh adds the remote itself under --source/--remote and fails if it exists.
                case "$*" in *--source*|*--remote*) return 1 ;; esac
                case "$*" in *--push*) git -C "$PROJECT_PATH" push -q -u origin main ;; esac ;;
            "secret set")
                cat >/dev/null
                echo "secret pushed=$(git -C "$BARE" rev-parse --verify -q refs/heads/main >/dev/null && echo yes || echo no)" >>"$LOG" ;;
            esac
        }
        [ "$MODE" = fail ] && git() { [ "$3" = push ] && return 1; command git "$@"; }
        scaffold_create_github_repo "$2"
        echo "status=$?" >>"$LOG"
    ' _ "$REPO_ROOT" "$dir" "$bare" "$log" "$str_mode" >"$WORK_DIR/$str_mode.out" 2>&1
    cat "$log"
}

test_secret_is_set_before_the_push() {
    local out
    out="$(run_create ok)"
    if grep -q '^secret pushed=no' <<<"$out" && ! grep -q -- '--push' <<<"$out" \
        && git -C "$WORK_DIR/ok.git" rev-parse --verify -q refs/heads/main >/dev/null \
        && grep -q '^status=0' <<<"$out"; then
        echo "ok: the secret is set before the first push"
    else
        echo "FAIL (secret before push): $(tr '\n' '|' <<<"$out")"
        int_failures=$((int_failures + 1))
    fi
}

test_failed_push_is_reported_incomplete() {
    local out
    out="$(run_create fail)"
    if grep -q '^secret pushed=no' <<<"$out" && grep -q '^status=0' <<<"$out" \
        && grep -q 'git push -u origin HEAD:main' "$WORK_DIR/fail.out"; then
        echo "ok: a failed push after the repo exists prints the push command"
    else
        echo "FAIL (failed push): $(tr '\n' '|' <<<"$out")"
        int_failures=$((int_failures + 1))
    fi
}

# Existing-remote fallback: `gh repo create` fails, so the prompt pushes itself - key first.
test_fallback_sets_secret_before_the_push() {
    local dir="$WORK_DIR/proj-fb" bare="$WORK_DIR/fb.git" log="$WORK_DIR/fb.log" out
    mkdir -p "$dir"
    git -C "$dir" init -q -b main
    git -C "$dir" -c user.email=t@example.com -c user.name=T commit -q --allow-empty -m "chore: seed"
    git init -q --bare "$bare"
    : >"$log"
    printf 'y\ny\n1\n' | GITGUARDIAN_API_KEY=k bash -c '
        source "$1/bin/lib/common.sh"; source "$1/bin/lib/scaffold_git_remote.sh"
        PROJECT_PATH="$2"; BARE="$3"; LOG="$4"
        GITHUB_USERNAME=o; PROJECT_NAME=r; PROJECT_DESCRIPTION=d
        scaffold_kanban_setup() { :; }
        scaffold_set_review_trigger_secret() { :; }
        scaffold_add_git_remote() { git -C "$PROJECT_PATH" remote add origin "$BARE"; }
        gh() {
            case "$1 $2" in
            "repo create") return 1 ;;
            "secret set")
                cat >/dev/null
                echo "secret pushed=$(git -C "$BARE" rev-parse --verify -q refs/heads/main >/dev/null && echo yes || echo no)" >>"$LOG" ;;
            esac
        }
        scaffold_prompt_git_remote_setup "$2"
    ' _ "$REPO_ROOT" "$dir" "$bare" "$log" >"$WORK_DIR/fb.out" 2>&1
    out="$(cat "$log")"
    if grep -q '^secret pushed=no' <<<"$out" \
        && git -C "$bare" rev-parse --verify -q refs/heads/main >/dev/null; then
        echo "ok: the fallback sets the secret before its push"
    else
        echo "FAIL (fallback order): $(tr '\n' '|' <<<"$out")"
        int_failures=$((int_failures + 1))
    fi
}

# Create succeeds, push fails: the prompt must return non-zero so callers skip branch protection.
test_prompt_fails_when_first_push_fails() {
    local dir="$WORK_DIR/proj-pf" bare="$WORK_DIR/pf.git" rc
    mkdir -p "$dir"
    git -C "$dir" init -q -b main
    git -C "$dir" -c user.email=t@example.com -c user.name=T commit -q --allow-empty -m "chore: seed"
    git init -q --bare "$bare"
    git -C "$dir" remote add origin "$bare"
    printf 'y\ny\n1\n' | bash -c '
        source "$1/bin/lib/common.sh"; source "$1/bin/lib/scaffold_git_remote.sh"
        PROJECT_PATH="$2"; BARE="$3"
        GITHUB_USERNAME=o; PROJECT_NAME=r; PROJECT_DESCRIPTION=d
        scaffold_set_review_trigger_secret() { :; }
        scaffold_add_git_remote() { :; }
        gh() { return 0; }
        git() { [ "$3" = push ] && return 1; command git "$@"; }
        scaffold_prompt_git_remote_setup "$2"
    ' _ "$REPO_ROOT" "$dir" "$bare" >"$WORK_DIR/pf.out" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "ok: the prompt returns non-zero when the first push failed"
    else
        echo "FAIL (prompt rc after failed push): rc=$rc"
        int_failures=$((int_failures + 1))
    fi
}

test_secret_is_set_before_the_push
test_prompt_fails_when_first_push_fails
test_fallback_sets_secret_before_the_push
test_failed_push_is_reported_incomplete
exit "$int_failures"
