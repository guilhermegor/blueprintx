#!/usr/bin/env bash
# The repo-root .codespellrc and templates/python-common/.codespellrc must carry the SAME
# ignore-words-list.
#
# Why a gate and not a comment: the two lists drifted in BOTH directions before anyone
# noticed — 30 words present here and missing from the template, 25 the other way — and the
# stale copy was the TEMPLATE, the one scaffolded into every new project. So the cost did not
# land on this repo; it landed on each generated project, which inherited an older vocabulary
# and re-learned the same words one rejected commit at a time. Nothing in either file could
# reveal that, because each list is perfectly plausible read on its own.
#
# Locale vocabulary is learned the expensive way (a full gate run per discovery), so a word
# this repo pays for must reach the template that ships it onward.
#
# Compared case-insensitively and order-independently: codespell itself matches
# case-insensitively, and the order in the file carries no meaning.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ROOT_RC="$REPO_ROOT/.codespellrc"
TEMPLATE_RC="$REPO_ROOT/templates/python-common/.codespellrc"

extract_words() {
	# Print the ignore-words-list entries, one per line, lowercased and sorted.
	local str_file="$1"
	grep -E '^ignore-words-list = ' "$str_file" |
		head -1 |
		sed -E 's/^ignore-words-list = //' |
		tr ',' '\n' |
		tr '[:upper:]' '[:lower:]' |
		sed '/^[[:space:]]*$/d' |
		sort -u
}

main() {
	local str_root_words str_template_words
	str_root_words="$(extract_words "$ROOT_RC")"
	str_template_words="$(extract_words "$TEMPLATE_RC")"

	if [ -z "$str_root_words" ] || [ -z "$str_template_words" ]; then
		echo "Could not read ignore-words-list from one of the .codespellrc files:" >&2
		echo "  $ROOT_RC" >&2
		echo "  $TEMPLATE_RC" >&2
		exit 1
	fi

	local str_only_root str_only_template
	str_only_root="$(comm -23 <(printf '%s\n' "$str_root_words") <(printf '%s\n' "$str_template_words"))"
	str_only_template="$(comm -13 <(printf '%s\n' "$str_root_words") <(printf '%s\n' "$str_template_words"))"

	if [ -z "$str_only_root" ] && [ -z "$str_only_template" ]; then
		echo "codespell ignore-words-list in sync (root == templates/python-common)."
		return 0
	fi

	echo "codespell ignore-words-list has drifted between the two .codespellrc files:" >&2
	if [ -n "$str_only_root" ]; then
		echo "  only in .codespellrc (missing from the template that ships to new projects):" >&2
		printf '%s\n' "$str_only_root" | sed 's/^/    /' >&2
	fi
	if [ -n "$str_only_template" ]; then
		echo "  only in templates/python-common/.codespellrc (missing from this repo):" >&2
		printf '%s\n' "$str_only_template" | sed 's/^/    /' >&2
	fi
	echo "Add the missing words to BOTH files — a word one side paid for must reach the other." >&2
	exit 1
}

main "$@"
