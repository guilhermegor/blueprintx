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


def block(str_selector, str_name):
    list_blocks = re.findall(str_selector + r"\s*\{([^}]*)\}", str_css)
    if not list_blocks:
        refuse(f"no {str_name} block")
    return ";\n".join(list_blocks)


str_slate = block(r"\[data-md-color-scheme\s*=\s*[\"']?slate[\"']?\s*\]", "slate")
str_root = block(r"(?<![\w-]):root", "root")
str_light = ";\n".join(re.findall(r"\[data-md-color-scheme\s*=\s*[\"']?default[\"']?\s*\]\s*\{([^}]*)\}", str_css))
if "--md-hue" in str_css or "--md-default-bg-color" in str_css:
    refuse("--md-hue or --md-default-bg-color overridden: background unresolved")


def var(str_block, str_name):
    list_found = re.findall(rf"(?<![\w-]){str_name}\s*:\s*([^;]+)", str_block)
    if not list_found:
        return None
    match_hex = re.fullmatch(r"#[0-9a-fA-F]{6}", list_found[-1].strip())
    return match_hex.group(0).lower() if match_hex else refuse(f"{str_name}: unparseable value")


int_bad = 0
for str_scheme, str_block, str_accent, str_page in (
    ("slate", str_slate, str_slate, str_bg),
    ("light", str_root, str_light, "#ffffff"),
):
    str_link = var(str_block, "--md-typeset-a-color") or var(str_block, "--md-primary-fg-color")
    str_hover = var(str_accent, "--md-accent-fg-color") or MATERIAL_DEFAULT_ACCENT
    for str_label, str_color in (("link", str_link), ("hover", str_hover)):
        if str_color is None:
            refuse(f"{str_scheme} {str_label}: unresolved")
        float_ratio = ratio(str_color, str_page)
        print(f"{str_scheme} {str_label} {str_color} on {str_page} = {float_ratio:.2f}")
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

yml_problem() {
	local str_yml="$1" int_primary int_scheme
	int_primary=$(grep -cE '^\s*primary:\s*custom\s*$' "$str_yml")
	int_scheme=$(grep -cE '^\s*-\s*scheme:' "$str_yml")
	grep -qE '^\s*-\s*stylesheets/brand\.css\s*$' "$str_yml" || { echo "no stylesheets/brand.css in extra_css"; return; }
	grep -qE '^\s*accent:' "$str_yml" && { echo "accent: set"; return; }
	{ [ "$int_primary" -ne "$int_scheme" ] || [ "$int_scheme" -eq 0 ]; } && { echo "primary: custom missing on a palette entry"; return; }
	grep -qE '^\s*-\s*(navigation\.top|content\.code\.annotate)\s*$' "$str_yml" && { echo "navigation.top or content.code.annotate enabled"; return; }
	return 0
}

check_yml() {
	local str_name="$1" str_yml="$2" str_expect="$3" str_why
	str_why="$(yml_problem "$str_yml")"
	if { [ -z "$str_why" ] && [ "$str_expect" = pass ]; } || { [ -n "$str_why" ] && [ "$str_expect" = refuse ]; }; then
		echo "ok: $str_name (${str_expect})"
	else
		echo "FAIL: $str_name expected $str_expect, got: ${str_why:-pass}"
		int_failures=$((int_failures + 1))
	fi
}

shopt -s nullglob
list_ymls=("$REPO_ROOT"/templates/*/mkdocs.yml)
list_docs=("$REPO_ROOT"/templates/*/docs)
shopt -u nullglob
if [ "${#list_ymls[@]}" -eq 0 ]; then
	echo "FAIL: no templates/*/mkdocs.yml found"
	int_failures=$((int_failures + 1))
fi
for str_yml in "${list_ymls[@]}"; do
	check_yml "$str_yml invariants" "$str_yml" pass
done
if grep -rl --exclude=contributing.md 'md-button' "${list_docs[@]}" "${list_ymls[@]}" >/dev/null 2>&1; then
	echo "FAIL: md-button used; contributing.md says the template has none"
	int_failures=$((int_failures + 1))
fi

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

YML="$REPO_ROOT/templates/lib-minimal/mkdocs.yml"
sed 's/^\(\s*\)- scheme: default/&\n\1  accent: indigo/' "$YML" >"$TMP/accent.yml"
check_yml "should-fail: accent: set in mkdocs.yml" "$TMP/accent.yml" refuse
sed '0,/primary: custom/{/primary: custom/d}' "$YML" >"$TMP/no-primary.yml"
check_yml "should-fail: primary: custom missing" "$TMP/no-primary.yml" refuse
sed '/stylesheets\/brand\.css/d' "$YML" >"$TMP/no-css.yml"
check_yml "should-fail: brand.css not in extra_css" "$TMP/no-css.yml" refuse
sed 's/^\(\s*\)- navigation\.tabs$/&\n\1- navigation.top/' "$YML" >"$TMP/nav-top.yml"
check_yml "should-fail: navigation.top enabled" "$TMP/nav-top.yml" refuse
sed 's/^\(\s*\)- navigation\.tabs$/&\n\1- content.code.annotate/' "$YML" >"$TMP/annotate.yml"
check_yml "should-fail: content.code.annotate enabled" "$TMP/annotate.yml" refuse

sed "s/\"slate\"/slate/" "$CSS" >"$TMP/unquoted.css"
check "slate selector unquoted" "$TMP/unquoted.css" pass
sed "s/\"slate\"/'slate'/" "$CSS" >"$TMP/single.css"
check "slate selector single-quoted" "$TMP/single.css" pass
sed -E 's|(--md-accent-fg-color--transparent:[^;]*);|\1|' "$CSS" >"$TMP/no-semi.css"
check "last declaration without trailing semicolon" "$TMP/no-semi.css" pass
sed '0,/--md-accent-fg-color:[^;]*;/s///' "$CSS" >"$TMP/no-root-accent.css"
check "should-fail: light scheme without a hover colour (Material accent 4.25:1)" "$TMP/no-root-accent.css" contrast
sed '0,/--md-accent-fg-color:[^;]*;/s//--md-accent-fg-color: #526cfe;/' "$CSS" >"$TMP/root-default.css"
check "should-fail: light hover is the Material default" "$TMP/root-default.css" contrast
sed -E 's|(--md-accent-fg-color:)[^;]*;|\1 #8c9eff;|' "$CSS" >"$TMP/root-pale.css"
check "should-fail: light hover too pale for white" "$TMP/root-pale.css" contrast

{ cat "$CSS"; printf '\n[data-md-color-scheme="slate"] {\n  --md-primary-fg-color: #0b2140;\n}\n'; } >"$TMP/split-slate-ok.css"
check "split slate block keeps the earlier link colour (cascade)" "$TMP/split-slate-ok.css" pass
{ printf '[data-md-color-scheme="slate"] {\n  --md-typeset-a-color: #102030;\n}\n'; grep -v -- '--md-typeset-a-color: #8ab4f8' "$CSS"; } >"$TMP/split-slate-dark.css"
check "should-fail: split slate block, earlier block holds a dark link colour" "$TMP/split-slate-dark.css" contrast
{ printf '[data-md-color-scheme="default"] {\n  --md-accent-fg-color: #3f51b5;\n}\n'; sed '0,/--md-accent-fg-color:[^;]*;/s///' "$CSS"; } >"$TMP/split-light.css"
check "split light block resolves across both blocks" "$TMP/split-light.css" pass
{ printf '[data-md-color-scheme="default"] { --md-accent-fg-color: #3f51b5 }\n'; sed '0,/--md-accent-fg-color:[^;]*;/s///' "$CSS"; } >"$TMP/split-light-nosemi.css"
check "split light block, earlier block without a final semicolon" "$TMP/split-light-nosemi.css" pass
{ printf ':root {\n  --md-accent-fg-color: #3f51b5;\n}\n'; sed '0,/--md-accent-fg-color:[^;]*;/s///' "$CSS"; } >"$TMP/root-accent-only.css"
check "should-fail: a :root hover colour loses to Material's body accent rule" "$TMP/root-accent-only.css" contrast

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; exit 1; }
echo "all cases passed"
