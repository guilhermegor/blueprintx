#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
SCRIPT="$REPO_ROOT/templates/python-common/bin/enable_pages.sh"
WORKFLOW="$REPO_ROOT/templates/lib-minimal/.github/workflows/release-pypi.yaml"

while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_')

int_failures=0
str_tmp="$(mktemp -d)"
trap 'rm -rf "$str_tmp"' EXIT

mkdir -p "$str_tmp/bin" "$str_tmp/proj/bin/lib"
cat > "$str_tmp/bin/gh" <<'STUB'
#!/bin/bash
case "$*" in
	"auth status" | "api repos/o/r/branches/gh-pages" | "api repos/o/r/pages") exit 0 ;;
	"api repos/o/r/pages --jq .build_type") cat "$STUB_DIR/build_type" ;;
	"api -X PUT repos/o/r/pages --input -")
		str_bt="$(jq -r '.build_type // empty')"
		if [ -n "$str_bt" ]; then printf '%s' "$str_bt" > "$STUB_DIR/build_type"; fi ;;
	*) exit 1 ;;
esac
STUB
chmod +x "$str_tmp/bin/gh"
printf 'extra:\n  version:\n    provider: mike\n' > "$str_tmp/proj/mkdocs.yml"
cp "$REPO_ROOT/templates/python-common/bin/lib/common.sh" "$str_tmp/proj/bin/lib/common.sh"
git -C "$str_tmp/proj" init -q
git -C "$str_tmp/proj" remote add origin https://github.com/o/r.git

run_script() {
	cp "$1" "$str_tmp/proj/bin/enable_pages.sh"
	printf 'workflow' > "$str_tmp/build_type"
	(cd "$str_tmp/proj" && STUB_DIR="$str_tmp" PATH="$str_tmp/bin:$PATH" bash bin/enable_pages.sh 2>&1)
}

expect() {
	local str_desc="$1"
	shift
	if ! "$@"; then
		print_status "error" "$str_desc"
		int_failures=$((int_failures + 1))
	fi
}

refute() {
	local str_desc="$1"
	shift
	if "$@"; then
		print_status "error" "$str_desc"
		int_failures=$((int_failures + 1))
	fi
}

str_ok="now serves the versioned docs"

str_out="$(run_script "$SCRIPT")"
expect "new payload flips build_type workflow -> legacy" grep -qx legacy "$str_tmp/build_type"
expect "new payload reports success after readback" grep -q "$str_ok" <<<"$str_out"

sed 's/{"build_type":"legacy","source"/{"source"/' "$SCRIPT" > "$str_tmp/old.sh"
str_out="$(run_script "$str_tmp/old.sh")"
expect "old payload leaves build_type=workflow" grep -qx workflow "$str_tmp/build_type"
refute "old payload is not reported as success" grep -q "$str_ok" <<<"$str_out"

sed 's/"\$str_build_type" != "legacy"/"x" = "y"/' "$str_tmp/old.sh" > "$str_tmp/noread.sh"
str_out="$(run_script "$str_tmp/noread.sh")"
expect "no readback: old payload falsely succeeds" grep -q "$str_ok" <<<"$str_out"

str_filter="$(grep -o "\-\-jq '[^']*build_type[^']*'" "$WORKFLOW" | sed "s/--jq '//; s/'\$//")"
expect "workflow Report step filter includes build_type" test -n "$str_filter"
str_wf='{"build_type":"workflow","source":{"branch":"gh-pages","path":"/"}}'
str_lg='{"build_type":"legacy","source":{"branch":"gh-pages","path":"/"}}'
str_old='.source.branch + ":" + .source.path'
expect "legacy reads as legacy:gh-pages:/" test "$(jq -r "$str_filter" <<<"$str_lg")" = "legacy:gh-pages:/"
expect "workflow reads as workflow:gh-pages:/" test "$(jq -r "$str_filter" <<<"$str_wf")" = "workflow:gh-pages:/"
expect "Report step compares against legacy:gh-pages:/" grep -qF '"$str_source" = "legacy:gh-pages:/"' "$WORKFLOW"
expect "old filter wrongly yields gh-pages:/ for workflow" test "$(jq -r "$str_old" <<<"$str_wf")" = "gh-pages:/"

if [ "$int_failures" -ne 0 ]; then
	print_status "error" "$int_failures enable_pages assertion(s) failed"
	exit 1
fi
print_status "success" "enable_pages: legacy payload + readback and Report-step build_type check hold; old payload/comparison fail"
