#!/usr/bin/env bash
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CSS="$REPO_ROOT/templates/python-common/docs/stylesheets/brand.css"
int_failures=0

contrast_report() {
	python3 -I - "$1" <<'PY'
import colorsys
import re
import sys

FLOAT_MIN = 4.5
MATERIAL_DEFAULT_ACCENT = "#526cfe"  # indigo, mkdocs-material >=9.5 (asserted below)


def luminance(str_hex):
    list_rgb = [int(str_hex[int_i:int_i + 2], 16) / 255 for int_i in (1, 3, 5)]
    list_lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in list_rgb]
    return 0.2126 * list_lin[0] + 0.7152 * list_lin[1] + 0.0722 * list_lin[2]


def ratio(str_a, str_b):
    float_hi, float_lo = sorted((luminance(str_a), luminance(str_b)), reverse=True)
    return (float_hi + 0.05) / (float_lo + 0.05)


tuple_bg = colorsys.hls_to_rgb(225 / 360, 0.14, 0.15)
str_bg = "#" + "".join(f"{round(c * 255):02x}" for c in tuple_bg)

str_css = re.sub(r"/\*.*?\*/", "", open(sys.argv[1]).read(), flags=re.S)
match_block = re.search(r'\[data-md-color-scheme="slate"\]\s*\{([^}]*)\}', str_css)
if not match_block:
    print("no slate block")
    sys.exit(0)
str_block = match_block.group(1)


def var(str_name):
    match_var = re.search(rf"{str_name}:\s*([^;]+);", str_block)
    if not match_var:
        return None
    match_hex = re.fullmatch(r"#[0-9a-fA-F]{6}", match_var.group(1).strip())
    return match_hex.group(0).lower() if match_hex else "unparseable"


if "--md-hue" in str_css:
    print("--md-hue overridden: background unresolved")
    sys.exit(0)

str_link = var("--md-typeset-a-color") or var("--md-primary-fg-color")
str_hover = var("--md-accent-fg-color") or MATERIAL_DEFAULT_ACCENT
if "unparseable" in (str_link, str_hover):
    print("unresolved: value is not a 6-digit hex")
    sys.exit(0)
for str_label, str_color in (("link", str_link), ("hover", str_hover)):
    if str_color is None:
        print(f"{str_label}: unresolved")
        continue
    float_ratio = ratio(str_color, str_bg)
    print(f"{str_label} {str_color} on {str_bg} = {float_ratio:.2f}")
    if float_ratio < FLOAT_MIN:
        print(f"{str_label}: below {FLOAT_MIN}")
PY
}

check() {
	local str_name="$1" str_css="$2" str_expect="$3" str_out str_got
	if ! str_out="$(contrast_report "$str_css")"; then
		echo "FAIL: $str_name: contrast checker failed"
		int_failures=$((int_failures + 1))
		return
	fi
	if grep -qE 'below|unresolved|no slate' <<<"$str_out"; then
		str_got=fail
	else
		str_got=pass
	fi
	if [ "$str_got" = "$str_expect" ]; then
		echo "ok: $str_name ($str_got)"
	else
		echo "FAIL: $str_name expected $str_expect, got $str_got"
		echo "$str_out"
		int_failures=$((int_failures + 1))
	fi
}

for str_yml in "$REPO_ROOT"/templates/*/mkdocs.yml; do
	if grep -qE '^\s*accent:' "$str_yml" || grep -E '^\s*primary:' "$str_yml" | grep -qv custom; then
		echo "FAIL: $str_yml sets accent or a named primary; the gate models indigo accent + custom primary"
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
check "should-fail: old slate block (link falls back to navy primary)" "$TMP/old.css" fail
check "should-fail: slate block without a hover colour (Material accent)" "$TMP/no-accent.css" fail
sed -E 's|(--md-typeset-a-color:[^;]*;)|/* \1 */|' "$CSS" >"$TMP/no-link-commented.css"
check "should-fail: commented-out link colour is not live" "$TMP/no-link-commented.css" fail
check "should-fail: slate block without a link colour" "$TMP/no-link.css" fail

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; exit 1; }
echo "all cases passed"
