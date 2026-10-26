#!/bin/bash

set -uo pipefail
while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e GIT_)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

run_create() {
    local str_mode="$1" dir="$WORK_DIR/proj-$1" bare="$WORK_DIR/$1.git" log="$WORK_DIR/$1.log"
    mkdir -p "$dir"
    git -C "$dir" init -q -b main
    git -C "$dir" -c user.email=t@example.com -c user.name=T commit -q --allow-empty -m "chore: seed"
    git init -q --bare -b main "$bare"
    git -C "$dir" remote add origin "$bare"
    : >"$log"
    printf 'y\n1\n' | BLUEPRINTX_STDIN_ANSWERS=1 GITGUARDIAN_API_KEY=k bash -c '
        source "$1/bin/lib/common.sh"; source "$1/bin/lib/scaffold_git_remote.sh"
        PROJECT_PATH="$2"; BARE="$3"; LOG="$4"; MODE="$5"
        GITHUB_USERNAME=o; PROJECT_NAME=r; PROJECT_DESCRIPTION=d
        scaffold_kanban_setup() { :; }
        gh() {
            case "$1 $2" in
            "repo create")
                echo "create $*" >>"$LOG"
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

test_origin_head_is_set_after_the_push() {
    local str_head
    run_create head >/dev/null
    str_head="$(git -C "$WORK_DIR/proj-head" symbolic-ref --short refs/remotes/origin/HEAD 2>&1)"
    if [ "$str_head" = "origin/main" ]; then
        echo "ok: origin/HEAD is set after the push"
    else
        echo "FAIL (origin/HEAD): $str_head"
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

test_fallback_sets_secret_before_the_push() {
    local dir="$WORK_DIR/proj-fb" bare="$WORK_DIR/fb.git" log="$WORK_DIR/fb.log" out
    mkdir -p "$dir"
    git -C "$dir" init -q -b main
    git -C "$dir" -c user.email=t@example.com -c user.name=T commit -q --allow-empty -m "chore: seed"
    git init -q --bare "$bare"
    : >"$log"
    printf 'y\ny\n1\n' | BLUEPRINTX_STDIN_ANSWERS=1 GITGUARDIAN_API_KEY=k bash -c '
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

test_prompt_fails_when_first_push_fails() {
    local dir="$WORK_DIR/proj-pf" bare="$WORK_DIR/pf.git" rc
    mkdir -p "$dir"
    git -C "$dir" init -q -b main
    git -C "$dir" -c user.email=t@example.com -c user.name=T commit -q --allow-empty -m "chore: seed"
    git init -q --bare "$bare"
    git -C "$dir" remote add origin "$bare"
    printf 'y\ny\n1\n' | BLUEPRINTX_STDIN_ANSWERS=1 bash -c '
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
test_origin_head_is_set_after_the_push
test_fallback_sets_secret_before_the_push
test_failed_push_is_reported_incomplete
test_no_classic_protection_put() {
    if grep -lE 'branches/.*/protection' "$REPO_ROOT"/bin/scaffold/*.sh "$REPO_ROOT/bin/promote_offline_to_online.sh" | grep -q .; then
        echo "FAIL (classic protection PUT still in a scaffold or the promoter)"
        int_failures=$((int_failures + 1))
    else
        echo "ok: no scaffold or promoter PUTs classic branch protection"
    fi
}

test_ruleset_keeps_pull_request_rule() {
    local str_json
    str_json="$(cd "$WORK_DIR" && bash -c 'source "$1"/bin/lib/common.sh 2>/dev/null; sed -n "/^build_rules_json/,/^}/p" "$1/templates/python-common/bin/enable_repo_rules.sh"' _ "$REPO_ROOT")"
    if grep -q '"type":"pull_request"' <<<"$str_json" && grep -q 'RULESET_APPROVALS:-0' <<<"$str_json" && grep -q '"type":"required_linear_history"' <<<"$str_json"; then
        echo "ok: the ruleset requires a pull_request and linear history even in solo mode"
    else
        echo "FAIL (ruleset lost its pull_request rule)"
        int_failures=$((int_failures + 1))
    fi
}

test_no_classic_protection_put
test_ruleset_keeps_pull_request_rule
exit "$int_failures"
