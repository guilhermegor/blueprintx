#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$REPO_ROOT/bin/ci/check_review_bot_prompt_sync.sh"
DIR_SCRATCH="$(mktemp -d)"
trap 'rm -rf "$DIR_SCRATCH"' EXIT

int_failures=0
int_case=0

make_tree() {
	local str_root="$1"
	mkdir -p "$str_root/bin/lib" "$str_root/docs" "$str_root/templates/python-common" "$str_root/templates/ts-common/.github"
	cp "$REPO_ROOT/bin/lib/scaffold_git_remote.sh" "$str_root/bin/lib/"
	cp "$REPO_ROOT/docs/faq.md" "$str_root/docs/"
	cp "$REPO_ROOT/templates/python-common/.review-bots.yaml" "$str_root/templates/python-common/"
	cp "$REPO_ROOT/templates/ts-common/.github/.review-bots.yaml" "$str_root/templates/ts-common/.github/"
}

expect() {
	local str_expect="$1" str_label="$2" str_root="$3" str_needle="${4:-}" str_out int_rc=0
	str_out="$(bash "$GATE" --root "$str_root" 2>&1)" || int_rc=$?
	if { [ "$str_expect" = "pass" ] && [ "$int_rc" -ne 0 ]; } || { [ "$str_expect" = "fail" ] && [ "$int_rc" -eq 0 ]; }; then
		echo "FAIL: $str_label expected $str_expect, rc=$int_rc" >&2
		int_failures=$((int_failures + 1))
	elif [ "$str_expect" = "fail" ] && ! grep -qF -- "$str_needle" <<<"$str_out"; then
		echo "FAIL: $str_label failed without naming '$str_needle': $str_out" >&2
		int_failures=$((int_failures + 1))
	fi
}

new_case() {
	int_case=$((int_case + 1))
	str_case="$DIR_SCRATCH/case$int_case"
	make_tree "$str_case"
}

new_case
expect pass "unmodified copy of the repo" "$str_case"

new_case
sed -i 's/Graphite, //' "$str_case/bin/lib/scaffold_git_remote.sh" "$str_case/docs/faq.md"
expect fail "threads login graphite-app has no prompt name" "$str_case" "graphite-app[bot]"

new_case
sed -i 's/, reviewer-ladder App//' "$str_case/bin/lib/scaffold_git_remote.sh" "$str_case/docs/faq.md"
expect fail "comment-marker poster has no prompt name" "$str_case" "guilhermegor-review-ladder[bot]"

new_case
sed -i 's/Greptile, //' "$str_case/docs/faq.md"
expect fail "faq drifted from the prompt" "$str_case" "docs/faq.md does not quote"

new_case
printf '  - login: newbot[bot]\n    posts: threads\n' >>"$str_case/templates/ts-common/.github/.review-bots.yaml"
expect fail "roster login with no mapping" "$str_case" "newbot[bot]"

new_case
sed -i '/^[[:space:]]*posters:/a\      # a comment\n\n      - newposter[bot]' "$str_case/templates/ts-common/.github/.review-bots.yaml"
expect fail "poster after a comment and blank line is still read" "$str_case" "newposter[bot]"

new_case
sed -i 's/Copilot, //' "$str_case/bin/lib/scaffold_git_remote.sh" "$str_case/docs/faq.md"
sed -i '/copilot-pull-request-reviewer/,+2d' "$str_case/templates/ts-common/.github/.review-bots.yaml"
expect fail "python-common roster is parsed on its own" "$str_case" "templates/python-common/.review-bots.yaml"

new_case
printf '  - posts: threads\n    login: orderbot[bot]\n' >>"$str_case/templates/ts-common/.github/.review-bots.yaml"
expect fail "posts before login is refused, never skipped" "$str_case" "has no login read before it"

new_case
printf '  - kind: comment-marker\n    posters: [flowbot[bot]]\n' >>"$str_case/templates/ts-common/.github/.review-bots.yaml"
expect fail "flow-style posters is refused, never skipped" "$str_case" "flow-style YAML"

new_case
printf '  - login: "quotedbot[bot]"\n    posts: "threads"\n' >>"$str_case/templates/ts-common/.github/.review-bots.yaml"
expect fail "quoted login and posts values are read, never skipped" "$str_case" "'quotedbot[bot]'"

new_case
printf '  - {login: mapbot[bot], posts: threads}\n' >>"$str_case/templates/ts-common/.github/.review-bots.yaml"
expect fail "flow-mapping entry is refused, never skipped" "$str_case" "flow-style YAML"

new_case
sed -i 's/^scaffold_prompt_review_bot_roster()/function scaffold_prompt_review_bot_roster/' "$str_case/bin/lib/scaffold_git_remote.sh"
expect fail "an unreadable prompt function prints its diagnostic" "$str_case" "no review-bot prompt found"

new_case
sed -i 's/^\(  - login: \)graphite-app\[bot\]$/\1gonebot[bot]/' "$str_case/templates/python-common/.review-bots.yaml" "$str_case/templates/ts-common/.github/.review-bots.yaml"
expect fail "a dict_names key with no roster login is refused" "$str_case" "dict_names key 'graphite-app'"

new_case
printf '  - login: statusbot[bot]\n    posts: status\n  -  login: twospace[bot]\n    posts: threads\n' >>"$str_case/templates/ts-common/.github/.review-bots.yaml"
expect fail "a login is never carried over to the next entry" "$str_case" "'twospace[bot]'"

new_case
printf '  - login: coderabbitai[bot]\n    posts: [threads]\n' >>"$str_case/templates/ts-common/.github/.review-bots.yaml"
expect fail "flow-list posts is refused, never skipped" "$str_case" "flow-style YAML"

new_case
rm "$str_case/docs/faq.md"
expect fail "missing faq checks nothing" "$str_case" "the gate checked nothing"

bash "$GATE" >/dev/null || { echo "FAIL: the real tree does not conform" >&2; int_failures=$((int_failures + 1)); }

if [ "$int_failures" -ne 0 ]; then
	exit 1
fi
echo "PASS: check_review_bot_prompt_sync"
