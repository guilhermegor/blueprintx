#!/usr/bin/env bash
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CSS="$REPO_ROOT/templates/python-common/docs/stylesheets/brand.css"
int_failures=0

read -r -d '' PY_CHECK <<'PY' || true
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

str_css = re.sub(r"/\*.*?\*/", "", open(sys.argv[1], encoding="utf-8").read(), flags=re.S)


def refuse(str_why):
    print(str_why)
    sys.exit(INT_REFUSED)


RE_BARE = re.compile(
    r"\s*(:root|\[data-md-color-scheme\s*=\s*[\"']?(slate|default)[\"']?\s*\])\s*"
)
RE_GATED = re.compile(
    r"(?<![\w-])--md-(accent-fg|primary-fg|typeset-a)-color\s*:"
)
if re.search(r"@(media|supports|container|layer)\b", str_css, re.I):
    refuse("a conditional at-rule wraps rules: the cascade is unresolved")
if re.search(r"@import\b", str_css, re.I):
    refuse("statement at-rule (@import) can reorder or replace the slate block")
for str_prelude, str_body in re.findall(r"([^{}]+)\{([^}]*)\}", str_css):
    if RE_BARE.fullmatch(str_prelude):
        continue
    if re.search(r":root|data-md-color-scheme", str_prelude):
        refuse("selector on :root or a colour scheme other than the bare default or slate: unresolved")
    if RE_GATED.search(str_body):
        refuse("a gated colour variable is set outside the :root, default and slate blocks: unresolved")


def block(str_selector,str_name, is_optional=False):
    list_blocks = re.findall(str_selector + r"\s*\{([^}]*)\}", str_css)
    if not list_blocks and not is_optional:
        refuse(f"no {str_name} block")
    return ";\n".join(list_blocks)


str_slate = block(r"\[data-md-color-scheme\s*=\s*[\"']?slate[\"']?\s*\]", "slate")
str_root = block(r"(?<![\w-]):root", "root")
str_light = block(r"\[data-md-color-scheme\s*=\s*[\"']?default[\"']?\s*\]", "default", True)
if "--md-hue" in str_css or "--md-default-bg-color" in str_css:
    refuse("--md-hue or --md-default-bg-color overridden: background unresolved")


def var(str_block, str_name):
    list_found = re.findall(rf"(?<![\w-]){str_name}\s*:\s*([^;]+)", str_block)
    if not list_found:
        return None
    match_hex = re.fullmatch(r"#[0-9a-fA-F]{6}", list_found[-1].strip())
    return match_hex.group(0).lower() if match_hex else refuse(f"{str_name}: unparseable value")


int_bad = 0
for str_scheme, str_block, str_accent, str_page, str_link_src in (
    ("slate", str_slate, str_slate, str_bg, str_slate),
    ("light", str_root + ";\n" + str_light, str_light, "#ffffff", str_light),
):
    str_link = var(str_link_src, "--md-typeset-a-color") or var(str_block, "--md-primary-fg-color")
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

read -r -d '' PY_YML <<'PY' || true
import sys

import yaml



class Loader(yaml.SafeLoader):
    pass


class Tagged:
    pass


Loader.add_multi_constructor("", lambda loader, suffix, node: Tagged())
try:
    dict_cfg = yaml.load(open(sys.argv[1], encoding="utf-8").read(), Loader=Loader) or {}
except yaml.YAMLError as err:
    print(f"unparseable yml: {type(err).__name__}")
    sys.exit(3)
if not isinstance(dict_cfg, dict):
    dict_cfg = {}
dict_theme = dict_cfg.get("theme")
if not isinstance(dict_theme, dict):
    dict_theme = {}
list_why = []
list_palette = dict_theme.get("palette") or []
if isinstance(list_palette, dict):
    list_palette = [list_palette]
if not isinstance(list_palette, list) or any(isinstance(d, Tagged) for d in list_palette):
    list_why.append("tagged or non-list palette cannot be checked")
    list_palette = []
list_css = dict_cfg.get("extra_css") or []
if isinstance(list_css, str):
    list_css = [list_css]
if not isinstance(list_css, list) or any(isinstance(c, Tagged) for c in list_css):
    list_why.append("tagged or non-list extra_css cannot be checked")
    list_css = []
list_features = dict_theme.get("features") or []
if isinstance(list_features, str):
    list_features = [list_features]
if not isinstance(list_features, list):
    list_features = []
list_dicts = [d for d in list_palette if isinstance(d, dict)]
if "stylesheets/brand.css" not in list_css:
    list_why.append("no stylesheets/brand.css in extra_css")
elif list_css[-1] != "stylesheets/brand.css":
    list_why.append("stylesheets/brand.css must be the last extra_css entry")
if any("accent" in d for d in list_dicts):
    list_why.append("accent: set")
if not any("scheme" in d for d in list_dicts):
    list_why.append("no palette entries (- scheme:) in mkdocs.yml")
elif any(d.get("primary") != "custom" for d in list_dicts):
    list_why.append("primary: custom missing on a palette entry")
if isinstance(dict_theme.get("features"), Tagged) or any(isinstance(f, Tagged) for f in list_features):
    list_why.append("tagged features value cannot be checked")
for str_feature in ("navigation.top", "content.code.annotate"):
    if str_feature in {str(f) for f in list_features}:
        list_why.append(f"{str_feature} enabled")
print("; ".join(list_why))
sys.exit(3 if list_why else 0)
PY

yml_problem() {
	local str_out int_rc
	str_out="$(python3 -I -c "$PY_YML" "$1" 2>&1)"
	int_rc=$?
	[ "$int_rc" -eq 0 ] && return 0
	[ "$int_rc" -eq 3 ] && { echo "$str_out"; return 0; }
	echo "yml gate crashed (exit $int_rc): $str_out"
}

mutate() {
	local str_src="$1" str_dst="$2"
	shift 2
	sed "$@" "$str_src" >"$str_dst"
	if cmp -s "$str_src" "$str_dst"; then
		echo "FAIL: mutation produced no change: $str_dst"
		int_failures=$((int_failures + 1))
	fi
}

check_mutate_guard() {
	local int_before="$int_failures"
	mutate "$1" "$TMP/unmatched.out" "${2:-s/this-pattern-never-matches/x/}" >/dev/null
	if [ "$int_failures" -eq $((int_before + 1)) ]; then
		int_failures="$int_before"
		echo "ok: should-fail: an unmatched mutation is flagged (refuse)"
	else
		echo "FAIL: an unmatched mutation went unflagged"
		int_failures=$((int_failures + 1))
	fi
}

check_yml() {
	local str_name="$1" str_yml="$2" str_expect="$3" str_reason="${4:-}" str_why
	str_why="$(yml_problem "$str_yml")"
	if [[ "$str_why" == "yml gate crashed"* ]]; then
		echo "FAIL: $str_name: $str_why"
		int_failures=$((int_failures + 1))
		return
	fi
	if { [ -z "$str_why" ] && [ "$str_expect" = pass ]; } || { [ -n "$str_why" ] && [ "$str_expect" = refuse ] && [[ "$str_why" == *"$str_reason"* ]]; }; then
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
md_button_users() {
	local str_hits
	[ "$#" -gt 0 ] || return 0
	str_hits="$(grep -rl 'md-button' "$@" 2>&1)"
	[ $? -le 1 ] || { echo "grep failed: $str_hits"; return 2; }
	printf '%s' "$str_hits" | grep -v '/python-common/docs/contributing\.md$'
	return 0
}
str_hits="$(md_button_users "${list_docs[@]}" "${list_ymls[@]}")"
if [ -n "$str_hits" ]; then
	echo "FAIL: md-button used or grep failed; contributing.md says the template has none: $str_hits"
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
check_yml "should-fail: accent: set in mkdocs.yml" "$TMP/accent.yml" refuse "accent: set"
sed '0,/primary: custom/{/primary: custom/d}' "$YML" >"$TMP/no-primary.yml"
check_yml "should-fail: primary: custom missing" "$TMP/no-primary.yml" refuse "primary: custom missing"
sed '/^\s*-\s*scheme:/d' "$YML" >"$TMP/no-palette.yml"
printf 'theme:\n  palette:\n    - media: "(prefers-color-scheme)"\n      primary: custom\n      accent: red\n    - scheme: default\n      primary: custom\nextra_css: [stylesheets/brand.css]\n' >"$TMP/media-accent.yml"
check_yml "should-fail: accent on a scheme-less palette entry" "$TMP/media-accent.yml" refuse "accent: set"
printf 'theme:\n  features: navigation.top\n  palette: [{scheme: default, primary: custom}]\nextra_css: [stylesheets/brand.css]\n' >"$TMP/scalar-feat.yml"
check_yml "should-fail: scalar features value" "$TMP/scalar-feat.yml" refuse "navigation.top"
check_yml "should-fail: no palette entries" "$TMP/no-palette.yml" refuse "no palette entries"
sed '/stylesheets\/brand\.css/d' "$YML" >"$TMP/no-css.yml"
check_yml "should-fail: brand.css not in extra_css" "$TMP/no-css.yml" refuse "no stylesheets/brand.css"
sed 's/^\(\s*\)- navigation\.tabs$/&\n\1- navigation.top/' "$YML" >"$TMP/nav-top.yml"
check_yml "should-fail: navigation.top enabled" "$TMP/nav-top.yml" refuse "navigation.top"
sed 's/^\(\s*\)- navigation\.tabs$/&\n\1- content.code.annotate/' "$YML" >"$TMP/annotate.yml"
check_yml "should-fail: content.code.annotate enabled" "$TMP/annotate.yml" refuse "content.code.annotate"
NL=$'\n'
mutate "$YML" "$TMP/late.yml" -e "s|^  - stylesheets/brand.css\$|  - stylesheets/brand.css\\${NL}  - stylesheets/later.css|"
check_yml "should-fail: a later extra_css entry follows brand.css" "$TMP/late.yml" refuse "last extra_css"
mutate "$YML" "$TMP/flow.yml" -e "s|^    - navigation.tabs\$|    - navigation.tabs\\${NL}    - \"navigation.top\" # flow|"
check_yml "should-fail: quoted feature with a trailing comment" "$TMP/flow.yml" refuse "navigation.top"
printf 'theme:\n  features: [content.code.annotate]\n  palette: [{scheme: default, primary: custom}]\nextra_css: [stylesheets/brand.css]\n' >"$TMP/flowlist.yml"
check_yml "should-fail: flow-style feature list" "$TMP/flowlist.yml" refuse "content.code.annotate"
{ cat "$CSS"; printf '@import "later.css";\n'; } >"$TMP/import.css"
check "should-fail: statement at-rule @import" "$TMP/import.css" refuse
{ printf '@IMPORT "later.css";\n'; cat "$CSS"; } >"$TMP/import-top.css"
check "should-fail: @import at the top of the file" "$TMP/import-top.css" refuse
{ printf '/* @import "x.css"; */\n'; cat "$CSS"; } >"$TMP/import-comment.css"
check "an @import inside a comment is not a statement" "$TMP/import-comment.css" pass
printf 'theme:\n  palette: {scheme: default, primary: custom}\nextra_css: [stylesheets/brand.css]\n' >"$TMP/dictpal.yml"
check_yml "a single-mapping palette is accepted" "$TMP/dictpal.yml" pass
printf 'theme:\n  features: !ENV [UNSET, [navigation.top]]\n  palette: [{scheme: default, primary: custom}]\nextra_css: [stylesheets/brand.css]\n' >"$TMP/tagged-feat.yml"
check_yml "should-fail: tagged features value is refused, not read as empty" "$TMP/tagged-feat.yml" refuse "tagged features"
printf 'theme:\n  features: [!ENV X, content.tabs]\n  palette: [{scheme: default, primary: custom}]\nextra_css: [stylesheets/brand.css]\n' >"$TMP/tagged-item.yml"
check_yml "should-fail: tagged feature item is refused" "$TMP/tagged-item.yml" refuse "tagged features"
check_mutate_guard "$CSS"
int_saved="$int_failures"
check_mutate_guard "$CSS" 's/slate/slat3/' >/dev/null
if [ "$int_failures" -eq $((int_saved + 1)) ]; then
	int_failures="$int_saved"
	echo "ok: should-fail: a guard that sees a matching mutation counts a failure"
else
	echo "FAIL: guard failure not counted"
	int_failures=$((int_failures + 1))
fi
printf 'theme:\n  palette: [!ENV X, {scheme: default, primary: custom}]\nextra_css: [stylesheets/brand.css]\n' >"$TMP/tagged-pal-item.yml"
check_yml "should-fail: tagged palette entry is refused, not dropped" "$TMP/tagged-pal-item.yml" refuse "palette cannot be checked"
printf 'theme:\n  palette: !ENV X\nextra_css: [stylesheets/brand.css]\n' >"$TMP/tagged-pal.yml"
check_yml "should-fail: tagged palette value is refused, not a crash" "$TMP/tagged-pal.yml" refuse "palette cannot be checked"
printf 'theme:\n  palette: [{scheme: default, primary: custom}]\nextra_css: !ENV X\n' >"$TMP/tagged-css.yml"
check_yml "should-fail: tagged extra_css is refused, not a crash" "$TMP/tagged-css.yml" refuse "extra_css cannot be checked"
printf 'theme:\n  palette: [{scheme: default, primary: custom}]\nextra_css: 5\n' >"$TMP/int-css.yml"
check_yml "should-fail: scalar non-string extra_css is refused, not a crash" "$TMP/int-css.yml" refuse "extra_css cannot be checked"
printf 'theme:\n  palette: [{scheme: default, primary: custom}]\nextra_css: {a: b}\n' >"$TMP/dict-css.yml"
check_yml "should-fail: mapping extra_css is refused, not a crash" "$TMP/dict-css.yml" refuse "extra_css cannot be checked"
printf 'theme: [unclosed\n' >"$TMP/broken.yml"
printf 'theme: material\nextra_css: [stylesheets/brand.css]\n' >"$TMP/theme-str.yml"
check_yml "should-fail: string theme is refused, not a crash" "$TMP/theme-str.yml" refuse "no palette entries"
check_yml "should-fail: unparseable yml is refused, never green" "$TMP/broken.yml" refuse "unparseable yml"
printf 'markdown_extensions:\n  - x: !!python/name:a.b.c\ntheme:\n  palette: [{scheme: default, primary: custom}]\nextra_css: [stylesheets/brand.css]\n' >"$TMP/tag.yml"
check_yml "a !!python/name tag does not crash the gate" "$TMP/tag.yml" pass

mutate "$CSS" "$TMP/unquoted.css" "s/\"slate\"/slate/"
check "slate selector unquoted" "$TMP/unquoted.css" pass
mutate "$CSS" "$TMP/single.css" "s/\"slate\"/'slate'/"
check "slate selector single-quoted" "$TMP/single.css" pass
mutate "$CSS" "$TMP/no-semi.css" -E 's|(--md-accent-fg-color--transparent:[^;]*);|\1|'
check "last declaration without trailing semicolon" "$TMP/no-semi.css" pass
sed '0,/--md-accent-fg-color:[^;]*;/s///' "$CSS" >"$TMP/no-light-accent.css"
check "should-fail: light scheme without a hover colour (Material accent 4.25:1)" "$TMP/no-light-accent.css" contrast
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
{ cat "$CSS"; printf '\n[data-md-color-scheme="default"] {\n  --md-typeset-a-color: #aaaaaa;\n}\n'; } >"$TMP/light-link.css"
check "should-fail: low-contrast light link colour in the default block" "$TMP/light-link.css" contrast
{ cat "$CSS"; printf '\n[data-md-color-scheme="default"], [data-md-color-scheme="slate"] {\n  --md-accent-fg-color: #8c9eff;\n}\n'; } >"$TMP/grouped.css"
check "should-fail: grouped scheme selector is refused, not half-parsed" "$TMP/grouped.css" refuse
{ cat "$CSS"; printf '\n:root, [data-md-color-scheme="default"] {\n  --md-accent-fg-color: #8c9eff;\n}\n'; } >"$TMP/grouped-root.css"
check "should-fail: grouped :root selector is refused" "$TMP/grouped-root.css" refuse
{ cat "$CSS"; printf '\n:root {\n  --md-primary-fg-color: #cccccc;\n  --md-typeset-a-color: #0d2c54;\n}\n'; } >"$TMP/root-link.css"
check "should-fail: a :root link colour is shadowed, the real link is the pale primary" "$TMP/root-link.css" contrast
{ cat "$CSS"; printf '\n[data-md-color-scheme="default"] .md-typeset {\n  --md-typeset-a-color: #aaaaaa;\n}\n'; } >"$TMP/descendant.css"
check "should-fail: descendant scheme selector is refused, not skipped" "$TMP/descendant.css" refuse
{ cat "$CSS"; printf '\n[data-md-color-scheme="default"][data-md-color-primary="custom"] {\n  --md-typeset-a-color: #aaaaaa;\n}\n'; } >"$TMP/compound.css"
check "should-fail: compound scheme selector is refused, not skipped" "$TMP/compound.css" refuse
{ printf '/* :root, then slate */\n'; cat "$CSS"; } >"$TMP/comment.css"
check "a comment naming :root and a comma does not trip the selector scan" "$TMP/comment.css" pass
for str_sel in '[data-md-color-accent="indigo"]' '[data-md-color-primary="custom"]' '.md-typeset'; do
	str_file="$TMP/outside-${str_sel//[^a-z]/}.css"
	{ cat "$CSS"; printf '\n%s {\n  --md-accent-fg-color: #8c9eff;\n  --md-typeset-a-color: #aaaaaa;\n}\n' "$str_sel"; } >"$str_file"
	check "should-fail: gated variable set under $str_sel is refused" "$str_file" refuse
done
{ cat "$CSS"; printf '\n.x {\n  --md-primary-fg-color--light: #aaaaaa;\n}\n'; } >"$TMP/ungated.css"
check "an ungated variable outside the scheme blocks passes" "$TMP/ungated.css" pass
{ cat "$CSS"; printf '\n@media (min-width: 60em) {\n  [data-md-color-scheme="default"] {\n    --md-accent-fg-color: #8c9eff;\n  }\n}\n'; } >"$TMP/media.css"
check "should-fail: a rule inside @media is refused, not read as unconditional" "$TMP/media.css" refuse
mkdir "$TMP/docs"
printf '[x](y){ .md-button }\n' >"$TMP/docs/page.md"
[ -n "$(md_button_users "$TMP/docs")" ] && echo "ok: md-button in a docs page is detected" || { echo "FAIL: md-button not detected"; int_failures=$((int_failures + 1)); }
md_button_users "$TMP/missing" >/dev/null && { echo "FAIL: grep read error swallowed"; int_failures=$((int_failures + 1)); } || echo "ok: grep read error is reported"

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; exit 1; }
echo "all cases passed"
