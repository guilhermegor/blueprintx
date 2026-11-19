#!/bin/bash

set -euo pipefail

str_root="$(cd "$(dirname "$0")/../.." && pwd)"
str_loader="$str_root/templates/common/bin"
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
	python3 -I - "$str_loader" "$(dirname "$1")" <<'PY'
import pathlib
import sys

sys.path.insert(0, sys.argv[1])
import check_review_threads as gate

if gate.yaml is None:
    sys.exit("PyYAML is not installed, so the roster cannot be read")
path_root = pathlib.Path(sys.argv[2])
try:
    set_logins = gate.reviewer_logins(gate.load_roster(path_root))
    set_logins |= gate.load_marker_posters(path_root)
except Exception as exc:
    sys.exit(f"{type(exc).__name__}: {exc}")
print("\n".join(sorted(set_logins)))
PY
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
	str_rel="${str_roster#"$str_root"/}"
	str_logins="$(roster_logins "$str_roster")" || { fail "$str_rel: unreadable roster (error above)"; continue; }
	[ -n "$str_logins" ] || { fail "$str_rel: no threads/poster logins parsed"; continue; }
	mapfile -t list_logins <<<"$str_logins"
	for str_login in "${list_logins[@]}"; do
		dict_seen[$str_login]=1
		str_name="${dict_names[$str_login]:-}"
		if [ -z "$str_name" ]; then
			fail "roster login '$str_login' ($str_rel) has no display name in dict_names of bin/ci/check_review_bot_prompt_sync.sh"
		elif ! grep -qiwF -- "$str_name" <<<"$str_prompt"; then
			fail "roster login '$str_login' ($str_rel) has no prompt name: '$str_name' is missing from the prompt in bin/lib/scaffold_git_remote.sh"
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
