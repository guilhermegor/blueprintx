#!/bin/bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$REPO_ROOT/templates/python-common/bin/check_logo_sync.sh"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

make_project() {
	local path_p="$1"
	mkdir -p "$path_p/assets" "$path_p/docs/assets"
	printf 'logo-bytes' >"$path_p/assets/logo_lorem_ipsum.png"
	printf 'logo-bytes' >"$path_p/docs/assets/logo.png"
	cat >"$path_p/README.md" <<'MD'
<p align="center"><img src="https://raw.githubusercontent.com/me/proj/main/assets/logo_lorem_ipsum.png" width="200"></p>
MD
	printf '# Proj <img src="assets/logo.png" align="right">\n' >"$path_p/docs/index.md"
	printf 'theme:\n  logo: assets/logo.png\n  favicon: assets/logo.png\n' >"$path_p/mkdocs.yml"
}

expect() {
	local str_name="$1" int_want="$2" path_p="$3" int_got=0
	bash "$GATE" "$path_p" >/dev/null 2>&1 || int_got=$?
	if [[ "$int_got" -ne "$int_want" ]]; then
		echo "FAIL ($str_name): exit $int_got, wanted $int_want"
		int_failures=$((int_failures + 1))
	else
		echo "ok   ($str_name)"
	fi
}

make_project "$WORK_DIR/match"
expect "matching images pass" 0 "$WORK_DIR/match"

make_project "$WORK_DIR/readme"
printf 'emblem' >"$WORK_DIR/readme/assets/logo_lorem_ipsum.png"
expect "replaced README image fails" 1 "$WORK_DIR/readme"

make_project "$WORK_DIR/docs"
printf 'emblem' >"$WORK_DIR/docs/docs/assets/logo.png"
expect "replaced docs image fails" 1 "$WORK_DIR/docs"

make_project "$WORK_DIR/missing"
rm "$WORK_DIR/missing/docs/assets/logo.png"
expect "missing file fails" 1 "$WORK_DIR/missing"

make_project "$WORK_DIR/noref"
printf '# no image\n' >"$WORK_DIR/noref/README.md"
expect "missing README reference fails" 1 "$WORK_DIR/noref"

make_project "$WORK_DIR/badge"
printf 'logo-bytes' >"$WORK_DIR/badge/docs/assets/badge.png"
printf 'emblem' >"$WORK_DIR/badge/docs/assets/hero.png"
printf '<img src="assets/badge.png">\n# Proj <img src="assets/hero.png" align="right">\n' >"$WORK_DIR/badge/docs/index.md"
expect "replaced heading logo fails behind an earlier image" 1 "$WORK_DIR/badge"

make_project "$WORK_DIR/quoted"
printf 'theme:\n  logo: "assets/logo.png"\n  favicon: '"'"'assets/logo.png'"'"'\n' >"$WORK_DIR/quoted/mkdocs.yml"
expect "quoted mkdocs paths pass" 0 "$WORK_DIR/quoted"

exit "$int_failures"
