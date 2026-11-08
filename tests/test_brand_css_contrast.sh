#!/usr/bin/env bash
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CSS="$REPO_ROOT/templates/python-common/docs/stylesheets/brand.css"
int_failures=0

read -r -d '' PY_CHECK <<'PY'
import colorsys
import re
import sys

FLOAT_MIN = 4.5
MATERIAL_DEFAULT_ACCENT = "#526cfe"  # indigo, mkdocs-material >=9.5 (the no-accent check below keeps it the true fallback)


def luminance(str_hex):
    list_rgb = [int(str_hex[int_i:int_i + 2], 16) / 255 for int_i in (1, 3, 5)]
    list_lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in list_rgb]
    return 0.2126 * list_lin[0] + 0.7152 * list_lin[1] + 0.0722 * list_lin[2]


def ratio(str_a, str_b):
    float_hi, float_lo = sorted((luminance(str_a), luminance(str_b)), reverse=True)
    return (float_hi + 0.05) / (float_lo + 0.05)


tuple_bg = colorsys.hls_to_rgb(225 / 360, 0.14, 0.15)
str_bg = "#" + "".join(f"{round(c * 255):02x}" for c in tuple_bg)
INT_GATE_FAIL = 3
INT_REFUSED = 4

str_css = re.sub(r"/\*.*?\*/", "", open(sys.argv[1]).read(), flags=re.S)


def refuse(str_why):
    print(str_why)
    sys.exit(INT_REFUSED)


list_blocks = re.findall(r'\[data-md-color-scheme="slate"\]\s*\{([^}]*)\}', str_css)
if not list_blocks:
    refuse("no slate block")
str_block = list_blocks[-1]
if "--md-hue" in str_css or "--md-default-bg-color" in str_css:
    refuse("--md-hue or --md-default-bg-color overridden: background unresolved")


def var(str_name):
    list_found = re.findall(rf"{str_name}:\s*([^;]+);", str_block)
    if not list_found:
        return None
    match_hex = re.fullmatch(r"#[0-9a-fA-F]{6}", list_found[-1].strip())
    return match_hex.group(0).lower() if match_hex else refuse(f"{str_name}: unparseable value")


str_link = var("--md-typeset-a-color") or var("--md-primary-fg-color")
str_hover = var("--md-accent-fg-color") or MATERIAL_DEFAULT_ACCENT
int_bad = 0
for str_label, str_color in (("link", str_link), ("hover", str_hover)):
    if str_color is None:
        refuse(f"{str_label}: unresolved")
    float_ratio = ratio(str_color, str_bg)
    print(f"{str_label} {str_color} on {str_bg} = {float_ratio:.2f}")
    int_bad += float_ratio < FLOAT_MIN
sys.exit(INT_GATE_FAIL if int_bad else 0)
PY

contrast_report() {
	python3 -I -c "$PY_CHECK" "$1"
}

check() {
	local str_name="$1" str_css="$2" str_expect="$3" str_out int_rc str_got
	str_out="$(contrast_report "$str_css")"
	int_rc=$?
	case "$int_rc" in
		0) str_got=pass ;;
		3) str_got=contrast ;;
		4) str_got=refuse ;;
		*) echo "FAIL: $str_name: contrast checker crashed (exit $int_rc)"
			int_failures=$((int_failures + 1)); return ;;
	esac
	if [ "$str_got" = "$str_expect" ]; then
		echo "ok: $str_name ($str_got)"
	else
		echo "FAIL: $str_name expected $str_expect, got $str_got"
		echo "$str_out"
		int_failures=$((int_failures + 1))
	fi
}

shopt -s nullglob
list_ymls=("$REPO_ROOT"/templates/*/mkdocs.yml)
shopt -u nullglob
if [ "${#list_ymls[@]}" -eq 0 ]; then
	echo "FAIL: no templates/*/mkdocs.yml found"
	int_failures=$((int_failures + 1))
fi
for str_yml in "${list_ymls[@]}"; do
	int_primary=$(grep -cE '^\s*primary:\s*custom\s*$' "$str_yml")
	int_scheme=$(grep -cE '^\s*-\s*scheme:' "$str_yml")
	if ! grep -qE '^\s*-\s*stylesheets/brand\.css\s*$' "$str_yml"; then
		echo "FAIL: $str_yml does not list stylesheets/brand.css in extra_css"
		int_failures=$((int_failures + 1))
	fi
	if grep -qE '^\s*accent:' "$str_yml" || [ "$int_primary" -ne "$int_scheme" ] || [ "$int_scheme" -eq 0 ]; then
		echo "FAIL: $str_yml needs primary: custom on every palette entry and no accent:"
		int_failures=$((int_failures + 1))
	fi
done

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cat >"$TMP/old.css" <<'EOF'
:root {
  --md-primary-fg-color: #0d2c54;
}

[data-md-color-scheme="slate"] {
  --md-primary-fg-color: #0b2140;
  --md-primary-fg-color--light: #1f3a62;
  --md-primary-fg-color--dark: #06142a;
}
EOF
sed 's/--md-accent-fg-color:[^;]*;//' "$CSS" >"$TMP/no-accent.css"
sed 's/--md-typeset-a-color:[^;]*;//' "$CSS" >"$TMP/no-link.css"

check "template slate links and hover meet 4.5:1" "$CSS" pass
check "should-fail: old slate block (link falls back to navy primary)" "$TMP/old.css" contrast
check "should-fail: slate block without a hover colour (Material accent)" "$TMP/no-accent.css" contrast
sed -E 's|(--md-typeset-a-color:[^;]*;)|/* \1 */|' "$CSS" >"$TMP/no-link-commented.css"
check "should-fail: commented-out link colour is not live" "$TMP/no-link-commented.css" contrast
check "should-fail: slate block without a link colour" "$TMP/no-link.css" contrast
printf ':root {\n  --md-primary-fg-color: #0d2c54;\n}\n' >"$TMP/no-slate.css"
check "should-fail: no slate block" "$TMP/no-slate.css" refuse
{ cat "$CSS"; printf '\n[data-md-color-scheme="slate"] {\n  --md-hue: 200;\n}\n'; } >"$TMP/hue.css"
check "should-fail: --md-hue override" "$TMP/hue.css" refuse
sed -E 's|(--md-typeset-a-color:)[^;]*;|\1 rgb(1, 2, 3);|' "$CSS" >"$TMP/unparseable.css"
check "should-fail: unparseable link value" "$TMP/unparseable.css" refuse

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; exit 1; }
echo "all cases passed"
