#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

CACHE_TTL=$((60 * 60 * 24 * 7))
CACHE_FAIL_TTL=$((60 * 60 * 6))

resolve_cache_dir() {
	local str_common_dir
	if [[ -n "${URL_CHECK_CACHE_DIR:-}" ]]; then
		echo "$URL_CHECK_CACHE_DIR"
	elif str_common_dir=$(git rev-parse --git-common-dir 2>/dev/null); then
		echo "${str_common_dir}/url_check_cache"
	else
		echo ".url_check_cache"
	fi
}

CACHE_DIR="$(resolve_cache_dir)"

get_cache() {
	local url="$1"
	local str_cache_file str_cached=""
	str_cache_file="${CACHE_DIR}/$(echo -n "$url" | md5sum | cut -d' ' -f1)"
	[[ -f "$str_cache_file" ]] && str_cached=$(<"$str_cache_file")

	if [[ -n "$str_cached" && ! "$str_cached" =~ ^(403|408|429)$ ]]; then
		local int_timestamp int_ttl=$CACHE_FAIL_TTL
		[[ "$str_cached" =~ ^2 ]] && int_ttl=$CACHE_TTL
		int_timestamp=$(stat -c %Y "$str_cache_file")
		local int_now
		int_now=$(date +%s)

		if ((int_now - int_timestamp < int_ttl)); then
			echo "$str_cached"
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
	echo "$str_status" >"${str_cache_file}.$$"
	mv -f "${str_cache_file}.$$" "$str_cache_file"
}

clean_cache() {
	find "$CACHE_DIR" -type f -mtime +$((CACHE_TTL / 60 / 60 / 24)) -delete 2>/dev/null
}

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
	[[ "$str_status_code" =~ ^[1-4][0-9][0-9]$ && ! "$str_status_code" =~ ^(403|408|429)$ ]] && set_cache "$str_url" "$str_status_code"
	echo "$str_status_code"
}

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

	while [[ "$str_line" =~ (https?://[a-zA-Z0-9./?=_%:-]+[a-zA-Z0-9/=_%-]) ]]; do
		str_url="${BASH_REMATCH[1]}"
		str_line="${str_line#*"$str_url"}"

		[[ -n "${DICT_PROCESSED_URLS[$str_url]:-}" ]] && continue
		DICT_PROCESSED_URLS["$str_url"]=1

		[[ "$str_url" =~ (https?://[^/]+)$ ]] && continue

		str_status_code=$(check_url "$str_url")
		report_url_status "$str_file" "$int_line_num" "$str_url" "$str_status_code"
	done
}

toggle_docstring_state() {
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

	local -a list_targets=("$@")
	local str_target str_file
	DICT_PROCESSED_URLS=()
	INT_URL_ERRORS=0
	[[ ${#list_targets[@]} -eq 0 ]] && list_targets=(.)

	print_status "info" "Scanning Python docstrings for URLs in: ${list_targets[*]}"

	for str_target in "${list_targets[@]}"; do
		if [[ -d "$str_target" ]]; then
			while IFS= read -r -d '' str_file; do
				scan_file_for_urls "$str_file"
			done < <(find "$str_target" -type f -name "*.py" -print0)
		elif [[ -f "$str_target" && "$str_target" == *.py ]]; then
			scan_file_for_urls "$str_target"
		elif [[ ! -e "$str_target" ]]; then
			print_status "error" "Path not found: $str_target"
			INT_URL_ERRORS=1
		fi
	done

	if [[ $INT_URL_ERRORS -eq 0 ]]; then
		print_status "success" "All docstring URLs are reachable"
		return 0
	fi
	return 1
}

list_open_trackers() {
	gh issue list --label docstring-urls --state open --limit 100 \
		--json number --jq 'sort_by(.number) | .[].number'
}

track_dead_urls() {
	local str_report="$1"
	local str_pattern='URL (issue|problem)|Failed to access URL'
	local str_marker='<!-- docstring-urls-tracker -->'
	local str_body="docstring_urls_body.md" str_open="" str_existing str_num

	if ! grep -qE "$str_pattern" "$str_report"; then
		if ! grep -qF 'All docstring URLs are reachable' "$str_report"; then
			echo "::error::Docstring URL scan produced no verdict."
			cat "$str_report"
			return 1
		fi
		echo "No dead docstring URLs."
		str_open=$(list_open_trackers) || {
			echo "::warning::Could not list open docstring-urls issues; stale trackers stay open."
			str_open=""
		}
		for str_num in $str_open; do
			gh issue close "$str_num" --comment "All docstring URLs are reachable again." ||
				echo "::warning::Could not close #${str_num}; the next scan retries."
		done
		return 0
	fi

	gh label create docstring-urls --color fbca04 \
		--description "A docstring URL no longer resolves" --force || true
	{
		printf '%s\n\nDead docstring URLs (status, file, line):\n\n```\n' "$str_marker"
		grep -E "$str_pattern" "$str_report"
		printf '```\n'
	} >"$str_body"
	str_open=$(list_open_trackers)
	str_existing=${str_open%%$'\n'*}
	if [[ -z "$str_existing" ]]; then
		gh issue create --title "Dead docstring URLs" \
			--label docstring-urls --body-file "$str_body"
		return 0
	fi
	gh issue comment "$str_existing" --body-file "$str_body"
	for str_num in $str_open; do
		[[ "$str_num" == "$str_existing" ]] || gh issue close "$str_num" --reason "not planned" \
			--comment "Duplicate of #${str_existing}." ||
			echo "::warning::Could not close duplicate #${str_num}; the next scan retries."
	done
}

main() {
	if [[ "${1:-}" == "--track" ]]; then
		track_dead_urls "${2:?--track needs the report file}"
		return
	fi
	if ! mkdir -p "$CACHE_DIR" 2>/dev/null || [[ ! -w "$CACHE_DIR" ]]; then
		CACHE_DIR="$(mktemp -d)"
		trap 'rm -rf "$CACHE_DIR"' EXIT
		print_status "warning" "Cache dir not writable; using ${CACHE_DIR}"
	fi
	process_python_files "$@" || exit 1
}

main "$@"
