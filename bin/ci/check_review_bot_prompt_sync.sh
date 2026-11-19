#!/bin/bash

set -euo pipefail

str_root="$(cd "$(dirname "$0")/../.." && pwd)"
[ "${1:-}" = "--root" ] && str_root="$(cd "${2:?usage: --root <dir>}" && pwd)"

str_lib="$str_root/bin/lib/scaffold_git_remote.sh"
str_faq="$str_root/docs/faq.md"
list_rosters=(
	"$str_root/templates/python-common/.review-bots.yaml"
	"$str_root/templates/ts-common/.github/.review-bots.yaml"
)

declare -A dict_names=(
	["coderabbitai"]="CodeRabbit"
	["greptile-apps"]="Greptile"
	["graphite-app"]="Graphite"
	["copilot-pull-request-reviewer"]="Copilot"
	["guilhermegor-review-ladder"]="reviewer-ladder"
)

int_failures=0
declare -A dict_seen=()

fail() {
	echo "ERROR: $*" >&2
	int_failures=$((int_failures + 1))
}

roster_logins() {
	awk '
		/^[[:space:]]*-([[:space:]]|$)/ { str_login = "" }
		/^[[:space:]]*- [a-z_]+:/ { bool_in = 0 }
		/^[[:space:]]*-[[:space:]]*[{]/ { print "!flow"; next }
		/^[[:space:]]*-[[:space:]]+["\047]?login["\047]?:/ { str_login = $3; gsub(/["\047]/, "", str_login); next }
		/^[[:space:]]*(-[[:space:]]+)?["\047]?posts["\047]?:[[:space:]]*\[/ { print "!flow"; next }
		/^[[:space:]]*(-[[:space:]]+)?["\047]?posts["\047]?:[[:space:]]*["\047]?threads["\047]?([[:space:]]|$)/ { print (str_login != "" ? str_login : "!order"); str_login = ""; next }
		/^[[:space:]]*(-[[:space:]]+)?["\047]?posts["\047]?:/ { str_login = ""; next }
		/^[[:space:]]*posters:[[:space:]]*[^[:space:]#]/ { print "!flow"; next }
		/^[[:space:]]*posters:/ { bool_in = 1; next }
		bool_in && /^[[:space:]]*(#.*)?$/ { next }
		bool_in && /^[[:space:]]*- / { str_poster = $2; gsub(/["\047]/, "", str_poster); print str_poster; next }
		bool_in { bool_in = 0 }
	' "$1" | sort -u
}

prompt_text() {
	awk '/^scaffold_prompt_review_bot_roster\(\)/ { bool_in = 1 } bool_in && /^}/ { exit } bool_in' "$str_lib" |
		grep -o 'prompt_main "[^"]*' | head -n 1 | sed 's/^prompt_main "//; s/ \[Y\/n\]: $//'
}

squash() {
	sed 's/\*//g' | tr -s '[:space:]' ' '
}

for f in "$str_lib" "$str_faq" "${list_rosters[@]}"; do
	[ -f "$f" ] || { echo "ERROR: missing $f; the gate checked nothing" >&2; exit 1; }
done

str_prompt="$(prompt_text || true)"
[ -n "$str_prompt" ] || { echo "ERROR: no review-bot prompt found in $str_lib" >&2; exit 1; }

for str_roster in "${list_rosters[@]}"; do
	mapfile -t list_logins < <(roster_logins "$str_roster")
	[ "${#list_logins[@]}" -gt 0 ] || fail "${str_roster#"$str_root"/}: no threads/poster logins parsed"
	for str_login in "${list_logins[@]}"; do
		case "$str_login" in
		'!order') fail "${str_roster#"$str_root"/}: a 'posts: threads' entry has no login read before it; make '- login: <name>' (with a space) the entry's first line" && continue ;;
		'!flow') fail "${str_roster#"$str_root"/}: flow-style YAML ('[...]' or '{...}') is not read; write 'posters:' and each entry as a block list" && continue ;;
		esac
		[ -n "$str_login" ] || continue
		str_stem="${str_login%\[bot\]}"
		dict_seen[$str_stem]=1
		str_name="${dict_names[$str_stem]:-}"
		if [ -z "$str_name" ]; then
			fail "roster login '$str_login' (${str_roster#"$str_root"/}) has no display name in dict_names of bin/ci/check_review_bot_prompt_sync.sh"
		elif ! grep -qiF -- "$str_name" <<<"$str_prompt"; then
			fail "roster login '$str_login' (${str_roster#"$str_root"/}) has no prompt name: '$str_name' is missing from the prompt in bin/lib/scaffold_git_remote.sh"
		fi
	done
done

for str_stem in "${!dict_names[@]}"; do
	[ -n "${dict_seen[$str_stem]:-}" ] || fail "dict_names key '$str_stem' matches no roster login; remove it from bin/ci/check_review_bot_prompt_sync.sh"
done

if ! squash <"$str_faq" | grep -qF -- "$(squash <<<"$str_prompt" | sed 's/ $//')"; then
	fail "docs/faq.md does not quote the scaffolder prompt verbatim: $str_prompt"
fi

[ "$int_failures" -eq 0 ] || exit 1
echo "OK: review-bot prompt names every roster login and docs/faq.md quotes it"
