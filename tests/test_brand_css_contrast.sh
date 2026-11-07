#!/usr/bin/env bash
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CSS="$REPO_ROOT/templates/python-common/docs/stylesheets/brand.css"
int_failures=0

contrast_failures() {
	python3 -I - "$1" <<'PY'
import colorsys
import re
import sys

FLOAT_MIN = 4.5
MATERIAL_DEFAULT_ACCENT = "#526cfe"


def luminance(str_hex):
    list_rgb = [int(str_hex[int_i:int_i + 2], 16) / 255 for int_i in (1, 3, 5)]
    list_lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in list_rgb]
    return 0.2126 * list_lin[0] + 0.7152 * list_lin[1] + 0.0722 * list_lin[2]


def ratio(str_a, str_b):
    float_hi, float_lo = sorted((luminance(str_a), luminance(str_b)), reverse=True)
    return (float_hi + 0.05) / (float_lo + 0.05)


tuple_bg = colorsys.hls_to_rgb(225 / 360, 0.14, 0.15)
str_bg = "#" + "".join(f"{round(c * 255):02x}" for c in tuple_bg)

str_css = open(sys.argv[1]).read()
match_block = re.search(r'\[data-md-color-scheme="slate"\]\s*\{([^}]*)\}', str_css)
if not match_block:
    print("no slate block")
    sys.exit(0)
str_block = match_block.group(1)


def var(str_name):
    match_var = re.search(rf"{str_name}:\s*(#[0-9a-fA-F]{{6}})\s*;", str_block)
    return match_var.group(1).lower() if match_var else None


str_link = var("--md-typeset-a-color") or var("--md-primary-fg-color")
str_hover = var("--md-accent-fg-color") or MATERIAL_DEFAULT_ACCENT
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
	local str_name="$1" str_css="$2" str_expect="$3" str_out
	str_out="$(contrast_failures "$str_css")"
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
sed 's/--md-accent-fg-color: #8c9eff;//' "$CSS" >"$TMP/no-accent.css"
sed 's/--md-typeset-a-color: #8ab4f8;//' "$CSS" >"$TMP/no-link.css"

check "template slate links and hover meet 4.5:1" "$CSS" pass
check "should-fail: old slate block (link falls back to navy primary)" "$TMP/old.css" fail
check "should-fail: slate block without a hover colour (Material accent)" "$TMP/no-accent.css" fail
check "should-fail: slate block without a link colour" "$TMP/no-link.css" fail

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; exit 1; }
echo "all cases passed"
