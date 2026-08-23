#!/bin/bash
# Pre-commit hook: scan Python docstrings for URLs and validate reachability.
# Results are cached for 1 week to avoid repeated network calls.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

CACHE_DIR=".url_check_cache"
CACHE_TTL=$((60 * 60 * 24 * 7)) # 1 week in seconds

get_cache() {
	local url="$1"
	local str_cache_file
	str_cache_file="${CACHE_DIR}/$(echo -n "$url" | md5sum | cut -d' ' -f1)"

	if [[ -f "$str_cache_file" ]]; then
		local int_timestamp
		int_timestamp=$(stat -c %Y "$str_cache_file")
		local int_now
		int_now=$(date +%s)

		if ((int_now - int_timestamp < CACHE_TTL)); then
			cat "$str_cache_file"
			return 0
		fi
	fi
	return 1
}

set_cache() {
	local url="$1"
	local str_status="$2"
	local str_cache_file
	str_cache_file="${CACHE_DIR}/$(echo -n "$url" | md5sum | cut -d' ' -f1)"
	echo "$str_status" >"$str_cache_file"
}

clean_cache() {
	find "$CACHE_DIR" -type f -mtime +$((CACHE_TTL / 60 / 60 / 24)) -delete 2>/dev/null
}

# Domains that answer a scripted probe with 403/anti-bot pages no matter which method is
# used. Treating them as reachable is a deliberate false-negative: the alternative is a
# permanently red hook that people learn to bypass.
STR_URL_USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
LIST_URL_ALLOWLIST=(
	"platform.openai.com"
	"openai.com"
	"stackoverflow.com"
	"reuters.com"
	"investing.com"
	"code.activestate.com"
	"geeksforgeeks.org"
	"towardsdatascience.com"
	"udemy.com"
)

url_is_allowlisted() {
	# ⚠️ Match the HOSTNAME, never a substring of the whole URL. A plain `*domain*` test
	# allowlists `https://attacker.example/path/openai.com` and
	# `https://openai.com.attacker.example/` — both skip probing and get cached as reachable.
	# Strip scheme, then userinfo, then everything from the first `/`, `?`, `#` or `:`, and
	# require an exact match or a real subdomain.
	local str_url="$1"
	local str_domain str_host

	[[ "$str_url" =~ ^https?:// ]] || return 1
	str_host="${str_url#*://}"
	str_host="${str_host##*@}"
	str_host="${str_host%%/*}"
	str_host="${str_host%%\?*}"
	str_host="${str_host%%#*}"
	str_host="${str_host%%:*}"

	for str_domain in "${LIST_URL_ALLOWLIST[@]}"; do
		if [[ "$str_host" == "$str_domain" || "$str_host" == *".$str_domain" ]]; then
			return 0
		fi
	done
	return 1
}

probe_url_status() {
	# HEAD first (cheapest), GET when the server refuses HEAD, wget last for the servers
	# that refuse curl specifically. Each fallback exists for an observed failure, so the
	# order is load-bearing rather than defensive.
	local str_url="$1"
	local str_status_code
	local -a list_headers=(
		-H "User-Agent: $STR_URL_USER_AGENT"
		-H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
		-H "Accept-Language: en-US,en;q=0.5"
		-H "Connection: keep-alive"
	)

	str_status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 --head \
		"${list_headers[@]}" "$str_url" 2>/dev/null)

	if [[ -z "$str_status_code" || "$str_status_code" -eq 403 || "$str_status_code" -eq 405 ]]; then
		str_status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
			"${list_headers[@]}" -H "Upgrade-Insecure-Requests: 1" "$str_url" 2>/dev/null)
	fi

	if [[ "$str_status_code" -eq 403 ]]; then
		if wget --spider --timeout=10 --user-agent="$STR_URL_USER_AGENT" "$str_url" >/dev/null 2>&1; then
			str_status_code="200"
		fi
	fi

	echo "$str_status_code"
}

check_url() {
	local str_url="$1"
	local str_status_code

	if str_status_code=$(get_cache "$str_url"); then
		echo "$str_status_code"
		return
	fi

	if url_is_allowlisted "$str_url"; then
		set_cache "$str_url" "200"
		echo "200"
		return
	fi

	str_status_code=$(probe_url_status "$str_url")
	if [[ "$str_status_code" =~ ^2 ]]; then
		set_cache "$str_url" "$str_status_code"
	fi
	echo "$str_status_code"
}

# Shared across the scan so a URL repeated in twenty docstrings is fetched once, and so a
# failure anywhere survives to the exit code. They are script-scoped rather than passed
# around because bash cannot return an associative array.
declare -A DICT_PROCESSED_URLS=()
INT_URL_ERRORS=0

report_url_status() {
	local str_file="$1" int_line_num="$2" str_url="$3" str_status_code="$4"

	if [[ -z "$str_status_code" ]]; then
		print_status "error" "Failed to access URL in $str_file (line $int_line_num): $str_url"
	elif [[ "$str_status_code" =~ ^[34] ]]; then
		print_status "error" "URL issue ($str_status_code) in $str_file (line $int_line_num): $str_url"
	elif [[ ! "$str_status_code" =~ ^2 ]]; then
		print_status "error" "URL problem ($str_status_code) in $str_file (line $int_line_num): $str_url"
	else
		return 0
	fi
	INT_URL_ERRORS=1
}

check_urls_in_line() {
	local str_file="$1" int_line_num="$2" str_line="$3"
	local str_url str_status_code

	while [[ "$str_line" =~ (https?://[a-zA-Z0-9./?=_%:-]+[a-zA-Z0-9./?=_%:-]) ]]; do
		str_url="${BASH_REMATCH[1]}"
		str_line="${str_line#*"$str_url"}"

		[[ -n "${DICT_PROCESSED_URLS[$str_url]:-}" ]] && continue
		DICT_PROCESSED_URLS["$str_url"]=1

		# A host-only URL has nothing to 404 on, and fetching it only rate-limits us.
		[[ "$str_url" =~ (https?://[^/]+)$ ]] && continue

		str_status_code=$(check_url "$str_url")
		report_url_status "$str_file" "$int_line_num" "$str_url" "$str_status_code"
	done
}

toggle_docstring_state() {
	# Echoes the state AFTER this delimiter line. A one-line docstring opens and closes on
	# the same line, so it must not flip the state at all.
	local str_line="$1" str_quote="$2" bool_in_docstring="$3"
	local str_after_open="${str_line#*"$str_quote"}"

	if [[ "$bool_in_docstring" == false && "$str_after_open" == *"$str_quote"* ]]; then
		echo "false"
	elif [[ "$bool_in_docstring" == true ]]; then
		echo "false"
	else
		echo "true"
	fi
}

scan_file_for_urls() {
	local str_file="$1"
	local int_line_num=0
	local bool_in_docstring=false
	local str_line

	while IFS= read -r str_line; do
		((int_line_num++))

		# ⚠️ A delimiter line IS docstring content — scan it BEFORE flipping the state.
		# This `continue` used to skip the scan, blinding the gate on TWO shapes (measured
		# with a seeded-cache negative control; blueprintx#206 reported the first):
		#
		#   1. `"""One line holding https://…"""` — the whole docstring, never scanned. This
		#      is the most common docstring shape in the tree, so the blind spot was the
		#      common case and the gate still printed "All docstring URLs are reachable".
		#   2. the OPENING line of a multi-line docstring (`"""Summary … https://…`) — the
		#      summary line is exactly where a reference URL tends to sit.
		#
		# Self-concealing by construction: an unscanned URL is never fetched, so it is never
		# cached and nothing in the output hints a line was skipped — the count printed is of
		# files scanned, not URLs checked.
		#
		# ⚠️ A THIRD shape, deferred when the two above were fixed and closed on review: a
		# closing delimiter sharing a line with text (`… https://…"""`). The guard used to
		# anchor on `^[[:space:]]*"""`, so such a line was not recognised as a delimiter at
		# all — its URL was scanned as ordinary body text (right answer, wrong mechanism) and,
		# worse, the state never flipped back, so every LATER line was read as still inside the
		# docstring and its URLs were fetched too. That over-scans rather than blinds, which is
		# why it was not urgent; it is also two characters to fix. Both delimiters are now
		# matched WHEREVER they sit on the line.
		if [[ "$str_line" == *'"""'* ]]; then
			check_urls_in_line "$str_file" "$int_line_num" "$str_line"
			bool_in_docstring="$(toggle_docstring_state "$str_line" '"""' "$bool_in_docstring")"
			continue
		fi
		if [[ "$str_line" == *"'''"* ]]; then
			check_urls_in_line "$str_file" "$int_line_num" "$str_line"
			bool_in_docstring="$(toggle_docstring_state "$str_line" "'''" "$bool_in_docstring")"
			continue
		fi

		[[ "$bool_in_docstring" == true ]] && check_urls_in_line "$str_file" "$int_line_num" "$str_line"
	done <"$str_file"
}

process_python_files() {
	clean_cache

	local str_root_dir="${1:-.}"
	local str_file
	DICT_PROCESSED_URLS=()
	INT_URL_ERRORS=0

	print_status "info" "Scanning Python docstrings for URLs in '$str_root_dir'..."

	while IFS= read -r -d '' str_file; do
		scan_file_for_urls "$str_file"
	done < <(find "$str_root_dir" -type f -name "*.py" -print0)

	if [[ $INT_URL_ERRORS -eq 0 ]]; then
		print_status "success" "All docstring URLs are reachable"
		return 0
	fi
	return 1
}

main() {
	mkdir -p "$CACHE_DIR"
	process_python_files "${1:-.}" || exit 1
}

main "$@"
