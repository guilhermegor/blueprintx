#!/bin/bash

set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

unset GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL EMAIL
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

run_first_commit() {
    local str_name="$1" str_mode="$2" proj="$WORK_DIR/proj-$1-$2" hooks="$WORK_DIR/hooks"
    mkdir -p "$proj" "$hooks"
    : >"$proj/f.txt"
    printf '#!/bin/sh\nexit 1\n' >"$hooks/pre-commit"
    chmod +x "$hooks/pre-commit"
    local -a list_env=(HOME="$WORK_DIR" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1)
    list_env+=(GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0="$hooks")
    [ "$str_mode" = hook ] && list_env+=(GIT_CONFIG_COUNT=3 GIT_CONFIG_KEY_1=user.name GIT_CONFIG_VALUE_1=t
        GIT_CONFIG_KEY_2=user.email GIT_CONFIG_VALUE_2=t@e.com)
    env "${list_env[@]}" bash -c '
        source "$1"; initialize_git_repo "$2"' _ "$(load_copy "$str_name")" "$proj" >"$WORK_DIR/$str_name-$str_mode.out" 2>&1
    echo $?
}

for str_name in python_ddd_service python_ddd_service_orm python_api_service python_mvc_service \
    python_mvc_service_orm python_lib_minimal ts_lib ts_react_app bash_cli; do
    for str_mode in hook no-identity; do
        int_rc="$(run_first_commit "$str_name" "$str_mode")"
        check "$str_name exits non-zero on failed first commit ($str_mode)" 1 "$int_rc"
        check "$str_name leaves no half-initialized .git ($str_mode)" no "$([ -e "$WORK_DIR/proj-$str_name-$str_mode/.git" ] && echo yes || echo no)"
        check "$str_name prints no success line ($str_mode)" 0 \
            "$(grep -c 'with first commit' "$WORK_DIR/$str_name-$str_mode.out")"
    done
done

proj="$WORK_DIR/react-offline"
mkdir -p "$proj"
echo '{"scripts":{}}' >"$proj/package.json"
mkdir -p "$proj/.github"
echo x >"$proj/.github/f.yml"
str_status="$(env HOME="$WORK_DIR" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
    GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@e.com GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@e.com \
    bash -c 'source "$1"; initialize_git_repo "$2" && apply_offline_mode "$2"' _ \
    "$(load_copy ts_react_app)" "$proj" >"$WORK_DIR/react.out" 2>&1
    git -C "$proj" status --porcelain)"
check "failure message does not blame the identity" 0 "$(grep -c 'is unset' "$WORK_DIR/python_ddd_service-no-identity.out")"
check "failure message mentions a commit hook" yes "$(grep -q 'commit hook' "$WORK_DIR/python_ddd_service-no-identity.out" && echo yes)"
check "offline React scaffold leaves git status clean" "" "$str_status"
check "offline React scaffold has 2 commits" 2 "$(git -C "$proj" rev-list --count HEAD)"

for str_name in python_ddd_service python_ddd_service_orm python_api_service python_mvc_service \
    python_mvc_service_orm python_lib_minimal ts_lib ts_react_app bash_cli; do
    check "$str_name swallows no artifact commit" 0 "$(grep -c 'no-verify.*|| true' "$REPO_ROOT/bin/scaffold/$str_name.sh")"
done

proj="$WORK_DIR/artifacts"
git init -q -b main "$proj"
echo a >"$proj/a"
str_out="$(env HOME="$WORK_DIR" GIT_CONFIG_GLOBAL=/dev/null GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@e.com \
    GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@e.com bash -c '
    source "$1/bin/lib/common.sh"; source "$1/bin/lib/scaffold_git_remote.sh"
    scaffold_commit_artifacts "$2" clean; echo "clean=$?"; echo b >"$2/b"
    git() { case " $* " in *" commit "*) return 1;; esac; command git "$@"; }
    scaffold_commit_artifacts "$2" boom; echo "boom=$?"' _ "$REPO_ROOT" "$proj" 2>&1)"
parent="$WORK_DIR/parent"
git init -q -b main "$parent"
mkdir "$parent/child"
echo c >"$parent/child/c"
env HOME="$WORK_DIR" GIT_CONFIG_GLOBAL=/dev/null GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@e.com \
    GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@e.com bash -c '
    source "$1/bin/lib/common.sh"; source "$1/bin/lib/scaffold_git_remote.sh"
    scaffold_commit_artifacts "$2" nested' _ "$REPO_ROOT" "$parent/child" >/dev/null 2>&1
check "a project nested in another repo is never committed into it" 0 "$(git -C "$parent" rev-list --all --count 2>/dev/null)"
proj="$WORK_DIR/env-identity"
git init -q -b main "$proj"
echo e >"$proj/e"
git -C "$proj" add e
str_env_out="$(env HOME="$WORK_DIR" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
    GIT_AUTHOR_NAME=envuser GIT_AUTHOR_EMAIL=env@e.com GIT_COMMITTER_NAME=envuser GIT_COMMITTER_EMAIL=env@e.com \
    bash -c 'source "$1/bin/lib/common.sh"; scaffold_git_commit "$2" env-identity' _ "$REPO_ROOT" "$proj" 2>&1)"
check "an identity from the environment is used, not the fallback" env@e.com "$(git -C "$proj" log -1 --format=%ae)"
check "no fallback notice when the environment supplies the identity" 0 "$(grep -c 'No git identity set' <<<"$str_env_out")"
check "an artifact commit that fails stops the scaffold" 0 "$(grep -c '^boom=' <<<"$str_out")"
check "the failure names the commit" 1 "$(grep -c "Could not commit 'boom'" <<<"$str_out")"

[ "$int_failures" -eq 0 ] || { echo "$int_failures failure(s)"; exit 1; }
echo "all passed"
