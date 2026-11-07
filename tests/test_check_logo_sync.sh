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
	local str_name="$1" int_want="$2" path_p="$3" str_msg="${4:-}" int_got=0 str_out
	str_out="$(bash "$GATE" "$path_p" 2>&1)" || int_got=$?
	if [[ "$int_got" -ne "$int_want" ]] || ! grep -qE -- "$str_msg" <<<"$str_out"; then
		echo "FAIL ($str_name): exit $int_got, wanted $int_want, message /$str_msg/"
		int_failures=$((int_failures + 1))
	else
		echo "ok   ($str_name)"
	fi
}

make_project "$WORK_DIR/match"
expect "matching images pass" 0 "$WORK_DIR/match" "same image"

make_project "$WORK_DIR/readme"
printf 'emblem' >"$WORK_DIR/readme/assets/logo_lorem_ipsum.png"
expect "replaced README image fails" 1 "$WORK_DIR/readme" "differs from"

make_project "$WORK_DIR/docs"
printf 'emblem' >"$WORK_DIR/docs/docs/assets/logo.png"
expect "replaced docs image fails" 1 "$WORK_DIR/docs" "differs from"

make_project "$WORK_DIR/missing"
rm "$WORK_DIR/missing/docs/assets/logo.png"
expect "missing file fails" 1 "$WORK_DIR/missing" "does not exist"

make_project "$WORK_DIR/noref"
printf '# no image\n' >"$WORK_DIR/noref/README.md"
expect "missing README reference fails" 1 "$WORK_DIR/noref" "no logo reference found"

make_project "$WORK_DIR/badge"
printf 'logo-bytes' >"$WORK_DIR/badge/docs/assets/badge.png"
printf 'emblem' >"$WORK_DIR/badge/docs/assets/hero.png"
printf '<img src="assets/badge.png">\n# Proj <img src="assets/hero.png" align="right">\n' >"$WORK_DIR/badge/docs/index.md"
expect "replaced heading logo fails behind an earlier image" 1 "$WORK_DIR/badge" "differs from"

make_project "$WORK_DIR/quoted"
printf 'theme:\n  logo: "assets/logo.png"\n  favicon: '"'"'assets/logo.png'"'"'\n' >"$WORK_DIR/quoted/mkdocs.yml"
expect "quoted mkdocs paths pass" 0 "$WORK_DIR/quoted" "same image"

make_project "$WORK_DIR/favicon"
printf 'emblem' >"$WORK_DIR/favicon/docs/assets/fav.png"
printf 'theme:\n  logo: assets/logo.png\n  favicon: assets/fav.png\n' >"$WORK_DIR/favicon/mkdocs.yml"
expect "favicon differing from logo fails" 1 "$WORK_DIR/favicon" "theme.favicon.*differs from"

make_project "$WORK_DIR/icon"
printf 'theme:\n  icon:\n    logo: material/library\n  logo: assets/logo.png\n  favicon: assets/logo.png\n' >"$WORK_DIR/icon/mkdocs.yml"
expect "theme.icon.logo is not the logo" 0 "$WORK_DIR/icon" "same image"

make_project "$WORK_DIR/comment"
printf 'theme:\n  logo: assets/logo.png  # brand\n  favicon: assets/logo.png # brand\n' >"$WORK_DIR/comment/mkdocs.yml"
expect "trailing YAML comments pass" 0 "$WORK_DIR/comment" "same image"

make_project "$WORK_DIR/nomkdocs"
rm "$WORK_DIR/nomkdocs/mkdocs.yml"
expect "absent mkdocs.yml fails" 1 "$WORK_DIR/nomkdocs" "mkdocs.yml theme.logo: no logo reference found"

exit "$int_failures"
