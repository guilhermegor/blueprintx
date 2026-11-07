#!/bin/bash

: "${SCAFFOLD_GH_GRAPHQL_BUDGET:=1120}"
: "${SCAFFOLD_GH_GRAPHQL_SITES:=16}"
: "${SCAFFOLD_GH_GRAPHQL_MEASURED:=17}"
: "${SCAFFOLD_RERUN_CMD:=the same blueprintx command}"
: "${SCAFFOLD_GH_REQUIRED_SCOPES=repo project}"

gh_classify_failure() {
	local str_text="$1"
	case "$str_text" in
	*[Rr]ate\ limit* | *RATE_LIMIT* | *[Ss]econdary\ rate* | *[Aa]buse* | *[Rr]etry-[Aa]fter*) printf 'rate' ;;
	*"HTTP 401"* | *"HTTP 403"* | *[Aa]uthentication* | *[Bb]ad\ credentials* | *[Ss]cope* | *INSUFFICIENT_SCOPES* | *"gh auth"* | *"authentication token"*) printf 'auth' ;;
	*"resolve host"* | *"no such host"* | *[Cc]onnection* | *[Tt]imeout* | *timed\ out* | *dial\ tcp* | *network* | *EOF*) printf 'network' ;;
	*) printf 'other' ;;
	esac
}

gh_wait_message() {
	local str_text="$1" str_secs str_epoch int_now int_mins
	str_secs="$(sed -n 's/.*[Rr]etry-[Aa]fter:* *\([0-9][0-9]*\).*/\1/p' <<<"$str_text" | head -n1)"
	if [ -n "$str_secs" ]; then
		printf 'retry in %s s (Retry-After from GitHub)' "$str_secs"
		return 0
	fi
	str_epoch="${GH_RESET_EPOCH:-}"
	[ -n "$str_epoch" ] ||
		str_epoch="$(gh api rate_limit --jq '([(.resources.core, .resources.graphql) | select(.remaining == 0) | .reset] | max) // .resources.graphql.reset' 2>/dev/null)" || str_epoch=""
	if [[ "$str_epoch" =~ ^[0-9]+$ ]]; then
		int_now="$(date +%s)"
		int_mins=$(((str_epoch - int_now + 59) / 60))
		[ "$int_mins" -ge 1 ] || int_mins=1
		printf 'retry in %s min, after %s' "$int_mins" "$({ date -u -d "@${str_epoch}" +%H:%MZ || date -u -r "${str_epoch}" +%H:%MZ; } 2>/dev/null)"
		return 0
	fi
	printf 'unknown, retry later'
}

gh_stop_online() {
	local str_step="$1" str_text="${2:-}" str_kind
	str_kind="$(gh_classify_failure "$str_text")"
	print_status "error" "GitHub step failed: ${str_step}"
	case "$str_kind" in
	rate) print_status "error" "Cause: GitHub rate limit. When to retry: $(gh_wait_message "$str_text")." ;;
	auth) print_status "error" "Cause: authentication. Fix: run 'gh auth login' (or 'gh auth refresh -s project'), then retry." ;;
	network) print_status "error" "Cause: network. Fix: check the connection to api.github.com, then retry." ;;
	*) print_status "error" "Cause: unexpected gh failure: $(head -n1 <<<"${str_text:-no output from gh}")" ;;
	esac
	gh_stop_footer
}

gh_stop_footer() {
	if [ -n "${SCAFFOLD_CREATED_REPO:-}" ]; then
		print_status "error" "Stopping: ${SCAFFOLD_CREATED_REPO} already exists on GitHub, so re-running would fail at repo creation. Finish the remaining steps by hand, or delete it ('gh repo delete ${SCAFFOLD_CREATED_REPO}') and re-run ${SCAFFOLD_RERUN_CMD}."
	else
		print_status "error" "Stopping: a half-created online project is never acceptable. Re-run ${SCAFFOLD_RERUN_CMD} once fixed."
	fi
	exit 1
}

gh_run() {
	local str_step="$1" str_err
	shift
	str_err="$(mktemp)"
	"$@" >/dev/null 2>"$str_err" || {
		gh_stop_online "$str_step" "$(cat "$str_err"; rm -f "$str_err")"
	}
	rm -f "$str_err"
}

gh_read() {
	local str_step="$1" str_err str_out
	shift
	str_err="$(mktemp)"
	str_out="$("$@" 2>"$str_err")" || {
		gh_stop_online "$str_step" "$(cat "$str_err"; rm -f "$str_err")"
	}
	rm -f "$str_err"
	printf '%s' "$str_out"
}

gh_missing_scopes() {
	local str_have="${1//[[:space:]]/}" str_scope str_missing=""
	for str_scope in $SCAFFOLD_GH_REQUIRED_SCOPES; do
		case ",${str_have}," in
		*",${str_scope},"*) ;;
		*) str_missing+="${str_missing:+ }${str_scope}" ;;
		esac
	done
	printf '%s' "$str_missing"
}

gh_check_scopes() {
	local str_err str_head str_line str_have str_missing str_scope
	str_err="$(mktemp)"
	str_head="$(gh api -i user 2>"$str_err")" || {
		gh_stop_online "preflight: token scopes (gh api -i user)" "$(cat "$str_err"; rm -f "$str_err")"
	}
	rm -f "$str_err"
	str_line="$(grep -i -m1 '^x-oauth-scopes:' <<<"$str_head")" || str_line=""
	if [ -z "$str_line" ]; then
		print_status "info" "Token scopes are not reported (fine-grained or app token): not verified"
		return 0
	fi
	str_have="$(tr -d '\r[:space:]' <<<"${str_line#*:}")"
	str_missing="$(gh_missing_scopes "$str_have")"
	[ -z "$str_missing" ] && return 0
	print_status "error" "GitHub step failed: preflight: token scopes (have: ${str_have:-none})"
	for str_scope in $str_missing; do
		print_status "error" "Cause: the token lacks the '${str_scope}' scope. Fix: run 'gh auth refresh -s ${str_scope}'."
	done
	gh_stop_footer
}

gh_require_workflow_for_https() {
	[ "$(gh config get git_protocol -h github.com 2>/dev/null)" = ssh ] ||
		SCAFFOLD_GH_REQUIRED_SCOPES+=" workflow"
}

gh_preflight() {
	local str_err str_login str_rl int_left
	str_err="$(mktemp)"
	gh api graphql -f query='{viewer{login}}' >/dev/null 2>"$str_err" ||
		gh_stop_online "preflight: GraphQL API" "$(cat "$str_err")"
	str_login="$(gh api user -q .login 2>"$str_err")" ||
		gh_stop_online "preflight: REST API (gh api user)" "$(cat "$str_err")"
	[ -n "$str_login" ] || gh_stop_online "preflight: gh api user returned a blank login" "authentication"
	gh_check_scopes
	str_rl="$(gh api rate_limit --jq '.resources.graphql | "\(.remaining) \(.reset)"' 2>"$str_err")" ||
		gh_stop_online "preflight: gh api rate_limit" "$(cat "$str_err")"
	rm -f "$str_err"
	int_left="${str_rl%% *}"
	[[ "$int_left" =~ ^[0-9]+$ ]] || gh_stop_online "preflight: unreadable rate_limit answer" "$str_rl"
	if [ "$int_left" -lt "$SCAFFOLD_GH_GRAPHQL_BUDGET" ]; then
		GH_RESET_EPOCH="${str_rl##* }" gh_stop_online "preflight: GraphQL budget (${int_left} points left, ${SCAFFOLD_GH_GRAPHQL_BUDGET} points needed)" "rate limit"
	fi
	print_status "success" "gh preflight passed (${str_login}, ${int_left} GraphQL points left)"
}
