#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ROOT_RC="$REPO_ROOT/.codespellrc"
TEMPLATE_RC="$REPO_ROOT/templates/python-common/.codespellrc"

extract_words() {
	local str_file="$1"
	grep -E '^ignore-words-list = ' "$str_file" |
		head -1 |
		sed -E 's/^ignore-words-list = //' |
		tr ',' '\n' |
		sed 's/^[[:space:]]*//; s/[[:space:]]*$//' |
		sed '/^$/d' |
		sort -u
}

check_lowercase() {
	local str_file="$1"
	local str_cased
	str_cased="$(extract_words "$str_file" | grep -E '[[:upper:]]' || true)"
	if [ -n "$str_cased" ]; then
		echo "Uppercase entries in ${str_file}'s ignore-words-list:" >&2
		printf '%s\n' "$str_cased" | sed 's/^/    /' >&2
		echo "Write them lowercase — codespell lowercases the found word before lookup, so a" >&2
		echo "lowercase entry covers every casing while a capitalised one matches only itself." >&2
		return 1
	fi
	return 0
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

	local int_cased=0
	check_lowercase "$ROOT_RC" || int_cased=1
	check_lowercase "$TEMPLATE_RC" || int_cased=1
	if [ "$int_cased" -ne 0 ]; then
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
