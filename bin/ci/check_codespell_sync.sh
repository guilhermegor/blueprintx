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
	# Print the ignore-words-list entries, one per line, VERBATIM and sorted.
	#
	# ⚠️ Do NOT lowercase here. An earlier version did, on the belief that codespell matches
	# case-insensitively — it does not, and the difference is the whole point of this gate.
	# codespell splits the list in two (`process_ignore_words`): entries that are already
	# lowercase filter its typo dictionary, while a CASED entry goes to a separate set and only
	# ever matches that exact capitalisation. So `classe` and `Classe` are NOT interchangeable,
	# and folding case before comparing would report two configs as "in sync" while they behave
	# differently — the gate would be blind to the very drift it exists to catch.
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
	# Reject any entry carrying an uppercase letter.
	#
	# codespell lowercases the word it FOUND before looking it up, so a lowercase entry covers
	# every capitalisation (`classe` silences `classe`/`Classe`/`CLASSE`) while a capitalised
	# entry silences only itself. A cased entry is therefore never more useful than its
	# lowercase form and is usually a mistake — the configs carried `Classe,classe` pairs that
	# existed only to work around this.
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
