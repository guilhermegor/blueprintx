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
if re.search(r"@(import|layer)\b[^{;]*;", str_css):
    refuse("statement at-rule (@import/@layer) can reorder or replace the slate block")
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

read -r -d '' PY_YML <<'PY'
import sys

import yaml

dict_cfg = yaml.safe_load(open(sys.argv[1])) or {}
dict_theme = dict_cfg.get("theme") or {}
list_palette = dict_theme.get("palette") or []
list_css = dict_cfg.get("extra_css") or []
list_features = dict_theme.get("features") or []
list_why = []
if not list_css or list_css[-1] != "stylesheets/brand.css":
    list_why.append("stylesheets/brand.css must be the last extra_css entry")
if not list_palette or any(
    not isinstance(d, dict) or d.get("primary") != "custom" or "accent" in d for d in list_palette
):
    list_why.append("needs primary: custom on every palette entry and no accent:")
list_bad = {"navigation.top", "content.code.annotate"} & {str(f) for f in list_features}
if list_bad:
    list_why.append(f"enables {sorted(list_bad)}: the brand.css gate does not cover them")
print("; ".join(list_why))
sys.exit(1 if list_why else 0)
PY

yml_problem() {
	python3 -I -c "$PY_YML" "$1"
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

NL=$'\n'

mutate() {
	local str_src="$1" str_dst="$2"
	shift 2
	sed "$@" "$str_src" >"$str_dst"
	if cmp -s "$str_src" "$str_dst"; then
		echo "FAIL: mutation produced no change: $str_dst"
		int_failures=$((int_failures + 1))
	fi
}

yml_expect() {
	local str_name="$1" str_yml="$2" str_want="$3" str_got=ok
	yml_problem "$str_yml" >/dev/null || str_got=refuse
	if [ "$str_got" = "$str_want" ]; then
		echo "ok: $str_name ($str_got)"
	else
		echo "FAIL: $str_name expected $str_want, got $str_got"
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
	str_problem="$(yml_problem "$str_yml")" || { echo "FAIL: $str_yml: $str_problem"; int_failures=$((int_failures + 1)); }
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
mutate "$CSS" "$TMP/no-accent.css" 's/--md-accent-fg-color:[^;]*;//'
mutate "$CSS" "$TMP/no-link.css" 's/--md-typeset-a-color:[^;]*;//'

GOOD_YML="${list_ymls[0]}"
if [ -n "${GOOD_YML:-}" ]; then
	yml_expect "template mkdocs.yml passes the yml gate" "$GOOD_YML" ok
	mutate "$GOOD_YML" "$TMP/late.yml" -e "s|^  - stylesheets/brand.css\$|  - stylesheets/brand.css\\${NL}  - stylesheets/later.css|"
	yml_expect "should-fail: a later extra_css entry follows brand.css" "$TMP/late.yml" refuse
	mutate "$GOOD_YML" "$TMP/flow.yml" -e "s|^    - navigation.tabs\$|    - navigation.tabs\\${NL}    - \"navigation.top\" # flow|"
	yml_expect "should-fail: quoted feature with a trailing comment" "$TMP/flow.yml" refuse
	mutate "$GOOD_YML" "$TMP/accent-top.yml" -e "s|^extra_css:\$|extra:\\${NL}  accent: red\\${NL}extra_css:|"
	yml_expect "accent: outside palette is not a palette accent" "$TMP/accent-top.yml" ok
	mutate "$GOOD_YML" "$TMP/accent-pal.yml" -e "s|^      primary: custom\$|      primary: custom\\${NL}      accent: red|"
	yml_expect "should-fail: accent: under a palette entry" "$TMP/accent-pal.yml" refuse
	printf 'theme:\n  features: [content.code.annotate]\n  palette: [{scheme: default, primary: custom}]\nextra_css: [stylesheets/brand.css]\n' >"$TMP/flowlist.yml"
	yml_expect "should-fail: flow-style feature list" "$TMP/flowlist.yml" refuse
	before=$int_failures
	mutate "$GOOD_YML" "$TMP/noop.yml" -e 's|no-such-text-anywhere|x|' >/dev/null
	if [ "$int_failures" -eq $((before + 1)) ]; then
		int_failures=$before
		echo "ok: should-fail: no-op mutation is detected"
	else
		echo "FAIL: no-op mutation went unnoticed"
	fi
fi

check "template slate links and hover meet 4.5:1" "$CSS" pass
check "should-fail: old slate block (link falls back to navy primary)" "$TMP/old.css" contrast
check "should-fail: slate block without a hover colour (Material accent)" "$TMP/no-accent.css" contrast
mutate "$CSS" "$TMP/no-link-commented.css" -E 's|(--md-typeset-a-color:[^;]*;)|/* \1 */|'
check "should-fail: commented-out link colour is not live" "$TMP/no-link-commented.css" contrast
check "should-fail: slate block without a link colour" "$TMP/no-link.css" contrast
printf ':root {\n  --md-primary-fg-color: #0d2c54;\n}\n' >"$TMP/no-slate.css"
check "should-fail: no slate block" "$TMP/no-slate.css" refuse
{ cat "$CSS"; printf '\n[data-md-color-scheme="slate"] {\n  --md-hue: 200;\n}\n'; } >"$TMP/hue.css"
check "should-fail: --md-hue override" "$TMP/hue.css" refuse
mutate "$CSS" "$TMP/unparseable.css" -E 's|(--md-typeset-a-color:)[^;]*;|\1 rgb(1, 2, 3);|'
check "should-fail: unparseable link value" "$TMP/unparseable.css" refuse
{ cat "$CSS"; printf '@import "later.css";\n'; } >"$TMP/import.css"
check "should-fail: statement at-rule @import" "$TMP/import.css" refuse

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; exit 1; }
echo "all cases passed"
