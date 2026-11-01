#!/bin/bash

set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

check() {
    if [ "$2" = "$3" ]; then echo "PASS: $1"; else echo "FAIL: $1 (want '$2', got '$3')"; int_failures=$((int_failures + 1)); fi
}

load_copy() {
    local str_name="$1" dir="$WORK_DIR/copy-$1"
    mkdir -p "$dir/bin/scaffold"
    ln -sfn "$REPO_ROOT/bin/lib" "$dir/bin/lib"
    ln -sfn "$REPO_ROOT/templates" "$dir/templates"
    sed '/^main$/d; /^main "\$@"$/d' "$REPO_ROOT/bin/scaffold/$str_name.sh" >"$dir/bin/scaffold/$str_name.sh"
    echo "$dir/bin/scaffold/$str_name.sh"
}

seed_repo() {
    local proj="$1" bare="$2"
    mkdir -p "$proj"
    git -C "$proj" init -q -b main
    git -C "$proj" -c user.email=t@e.com -c user.name=T commit -q --allow-empty -m "chore: seed"
    git init -q --bare "$bare"
    git -C "$proj" remote add origin "$bare"
}

test_ts_lib_patches_delete_branch_on_merge() {
    local log="$WORK_DIR/gh.log" proj="$WORK_DIR/proj-ts"
    seed_repo "$proj" "$WORK_DIR/ts.git"
    : >"$log"
    printf 'y\n1\n' | GH_LOG="$log" BLUEPRINTX_STDIN_ANSWERS=1 bash -c '
        source "$1"
        GITHUB_USERNAME=o; PROJECT_NAME=r; PROJECT_DESCRIPTION=d
        scaffold_kanban_setup() { :; }
        gh() {
            echo "$*" >>"$GH_LOG"
            case "$*" in "api repos/o/r --jq"*) echo true ;; esac
            return 0
        }
        scaffold_create_github_repo "$3"
    ' _ "$(load_copy ts_lib)" "$log" "$proj" >"$WORK_DIR/ts.out" 2>&1
    check "ts-lib sends the delete_branch_on_merge PATCH" 1 \
        "$(grep -c 'api -X PATCH repos/o/r -F delete_branch_on_merge=true' "$log")"
    check "ts-lib reads the setting back" 1 "$(grep -c 'api repos/o/r --jq .delete_branch_on_merge' "$log")"
}

test_failed_patch_only_warns() {
    local proj="$WORK_DIR/proj-fail" rc
    seed_repo "$proj" "$WORK_DIR/fail.git"
    printf 'y\n1\n' | BLUEPRINTX_STDIN_ANSWERS=1 bash -c '
        source "$1"
        GITHUB_USERNAME=o; PROJECT_NAME=r; PROJECT_DESCRIPTION=d
        scaffold_kanban_setup() { :; }
        gh() { case "$1 $2" in "api -X") return 1 ;; esac; return 0; }
        scaffold_create_github_repo "$2"
    ' _ "$(load_copy ts_lib)" "$proj" >"$WORK_DIR/fail.out" 2>&1
    rc=$?
    check "a failed PATCH does not abort" 0 "$rc"
    check "a failed PATCH warns" 1 "$(grep -c 'delete_branch_on_merge' "$WORK_DIR/fail.out")"
}

test_scaffolded_repo_prunes_on_fetch() {
    local str_name proj
    for str_name in ts_lib etcher_chromeos ventoy_usb; do
        proj="$WORK_DIR/init-$str_name"
        mkdir -p "$proj"
        : >"$proj/f.txt"
        env HOME="$WORK_DIR" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
            GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@e.com GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@e.com \
            bash -c 'source "$1"; initialize_git_repo "$2"' _ "$(load_copy "$str_name")" "$proj" \
            >"$WORK_DIR/init-$str_name.out" 2>&1
        check "$str_name sets fetch.prune" true "$(git -C "$proj" config --local fetch.prune 2>/dev/null)"
    done
}

test_ts_lib_patches_delete_branch_on_merge
test_failed_patch_only_warns
test_scaffolded_repo_prunes_on_fetch

[ "$int_failures" -eq 0 ] || { echo "$int_failures failure(s)"; exit 1; }
echo "all passed"
