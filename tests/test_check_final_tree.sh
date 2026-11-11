#!/bin/bash

set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/bin/ci/check_final_tree.sh"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
export HOME="$WORK_DIR" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@e.com GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@e.com
int_failures=0

check() {
    if [ "$2" = "$3" ]; then echo "PASS: $1"; else echo "FAIL: $1 (want '$2', got '$3')"; int_failures=$((int_failures + 1)); fi
}

new_repo() {
    local dir="$WORK_DIR/$1"
    mkdir -p "$dir"
    git -C "$dir" init -q -b main
    : >"$dir/f.txt"
    git -C "$dir" add -A
    git -C "$dir" commit -q -m init
    echo "$dir"
}

with_remote() {
    git init -q --bare "$WORK_DIR/$1.git"
    git -C "$2" remote add origin "$WORK_DIR/$1.git"
}

run_check() {
    (cd "$1" && bash "$SCRIPT" t >"$WORK_DIR/out" 2>&1)
    echo $?
}

dir="$(new_repo clean)"
check "clean repo without origin passes" 0 "$(run_check "$dir")"
grep -q "push check skipped" "$WORK_DIR/out"
check "no origin reports the push check as skipped" 0 $?

dir="$(new_repo dirty)"
: >"$dir/untracked.txt"
check "untracked file fails" 1 "$(run_check "$dir")"

dir="$(new_repo nested)"
mkdir -p "$dir/.specs/features/.specs"
: >"$dir/.specs/features/.specs/x.md"
git -C "$dir" add -A
git -C "$dir" commit -q -m nested
check "nested .specs at any depth fails" 1 "$(run_check "$dir")"

dir="$(new_repo subdir)"
mkdir "$dir/sub"
check "run from a subdirectory of a repo fails" 1 "$(run_check "$dir/sub")"

dir="$(new_repo nofetch)"
with_remote nofetch "$dir"
check "origin set but origin/main never created fails" 1 "$(run_check "$dir")"

dir="$(new_repo pushed)"
with_remote pushed "$dir"
git -C "$dir" push -q origin main
check "main pushed to a bare remote passes" 0 "$(run_check "$dir")"
grep -q "pushed," "$WORK_DIR/out"
check "pushed repo reports the push check as run" 0 $?

: >"$dir/g.txt"
git -C "$dir" add -A
git -C "$dir" commit -q -m ahead
check "local main ahead of origin/main fails" 1 "$(run_check "$dir")"

dir="$(new_repo master)"
git -C "$dir" branch -m master
with_remote master "$dir"
git -C "$dir" push -q origin master
check "origin set but local main missing fails" 1 "$(run_check "$dir")"

[ "$int_failures" -eq 0 ] || { echo "$int_failures failure(s)"; exit 1; }
echo "OK: all final-tree checks behave."
