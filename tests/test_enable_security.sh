#!/bin/bash

set -uo pipefail
while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e GIT_)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

mkdir -p "$WORK_DIR/bin" "$WORK_DIR/withremote" "$WORK_DIR/noremote"
cat >"$WORK_DIR/bin/gh" <<'STUB'
#!/bin/bash
case "$1 $2" in
"auth status") exit 0 ;;
"repo view") echo "graphql down" >&2; exit 1 ;;
esac
exit 0
STUB
chmod +x "$WORK_DIR/bin/gh"
git -C "$WORK_DIR/withremote" init -q
git -C "$WORK_DIR/withremote" remote add origin git@github.com:acme/widget.git
git -C "$WORK_DIR/noremote" init -q

run_in() {
    (cd "$WORK_DIR/$1" && PATH="$WORK_DIR/bin:$PATH" bash "$2" 2>&1)
}

check() {
    local str_label="$1" str_pattern="$2" str_out="$3" bool_want="$4"
    if grep -q -- "$str_pattern" <<<"$str_out"; then
        [ "$bool_want" = 1 ] && { echo "ok: $str_label"; return; }
    else
        [ "$bool_want" = 0 ] && { echo "ok: $str_label"; return; }
    fi
    echo "FAIL ($str_label): $(tr '\n' '|' <<<"$str_out")"
    int_failures=$((int_failures + 1))
}

for str_name in enable_security enable_pages; do
    str_script="$REPO_ROOT/templates/python-common/bin/$str_name.sh"
    str_out="$(run_in withremote "$str_script")"
    check "$str_name resolves origin when GraphQL fails" "No GitHub remote resolved" "$str_out" 0
    str_out="$(run_in noremote "$str_script")"
    check "$str_name with no remote says so" "No GitHub remote resolved" "$str_out" 1
done

str_out="$(run_in withremote "$REPO_ROOT/templates/python-common/bin/enable_security.sh")"
check "enable_security reaches the toggles" "Private vulnerability reporting enabled" "$str_out" 1

git -C "$WORK_DIR/withremote" remote set-url origin https://example.com/x/y
str_out="$(run_in withremote "$REPO_ROOT/templates/python-common/bin/enable_security.sh")"
check "an unresolvable origin reports the gh failure, not no-remote" "gh repo view failed" "$str_out" 1

exit "$int_failures"
