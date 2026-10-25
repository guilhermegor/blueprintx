#!/bin/bash

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/bin/lib/spec.sh"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_')
export GIT_AUTHOR_NAME=ci-bot GIT_COMMITTER_NAME=ci-bot
export GIT_AUTHOR_EMAIL=ci-bot@example.com GIT_COMMITTER_EMAIL=ci-bot@example.com

RE_GENERATED_ONLY='^(LICENSE|README\.md|AGENTS\.md|Makefile|pyproject\.toml|package\.json|mkdocs\.yml|docusaurus\.config\.js|ventoy-usb\.conf|comment_budget_baseline\.txt|\.blueprintx-provenance\.yaml|poe_tasks\.offline\.toml|bin/git_diff_(apply|check|export)\.sh|bin/project|tests/cli\.bats|tests/helpers/common\.bash|SECURITY\.md|src/project/(_internal/(config/)?)?__init__\.py|tests/unit/test_(main|typing)\.py|docs/(index|usage|contributing|examples|faq)\.md)$|(^|/)\.(keep|gitkeep)$'
RE_LISTED_ONLY='^(\.github/.*|bin/(check_pr_policy|close_linked_issues|dependabot_auto_merge)\.sh|\.review-bots\.yaml)$'

pass() { echo "ok: $1"; }
fail() {
	echo "FAIL ($1): $2"
	int_failures=$((int_failures + 1))
}

run_list() {
	local str_scaffold="$1" str_key="${2:-}"
	shift 2
	(
		cd "$WORK_DIR/cwd" || exit 1
		export HOME="$WORK_DIR/home"
		export GITGUARDIAN_API_KEY=$str_key
		bash "$REPO_ROOT/$str_scaffold" --list-copies "$@" </dev/null
	)
}

scaffold_for_real() {
	local str_name="$1" str_scaffold="$2" str_work="$3"
	if spec_skeleton_supported "$str_name"; then
		spec_stdin_for_skeleton "$str_name" "" \
			| BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold" \
				"$str_work" project "CI list-copies oracle" "0.0.1" >/dev/null 2>&1
	else
		GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold" \
			"$str_work" project "CI list-copies oracle" "0.0.1" \
			< <(printf '\n%.0s' {1..100}) >/dev/null 2>&1
	fi
}

diff_against_real() {
	local str_out="$1" str_project="$2"
	{
		(cd "$str_project" && find . -path ./.git -prune -o -type f -print | sed 's#^\./##') | sed 's/^/G\t/'
		awk -F'\t' '$1 == "COPY" && $2 == "file" { print "F\t" $4 } $1 == "COPY" && $2 == "dir" && $4 != "" { print "D\t" $4 } $1 == "RM" { print "R\t" $2 }' <<<"$str_out"
	} | RE_GEN="$RE_GENERATED_ONLY" RE_LIST="$RE_LISTED_ONLY" awk -F'\t' '
		$1 == "G" { gen[$2] = 1 }
		$1 == "F" { file[$2] = 1 }
		$1 == "D" { sub("/$", "", $2); dir[$2] = 1 }
		$1 == "R" { rm[$2] = 1 }
		END {
			for (f in rm) delete file[f]
			for (g in gen) {
				if (g in file || g ~ ENVIRON["RE_GEN"]) continue
				covered = 0
				for (d in dir) if (index(g, d "/") == 1) covered = 1
				if (!covered) print "generated but not listed: " g
			}
			for (f in file)
				if (!(f in gen) && f !~ ENVIRON["RE_LIST"]) print "listed but not generated: " f
		}' | sort
}

check_scaffold() {
	local str_name="$1" str_scaffold="$2"
	local str_out str_keyed str_diff str_work
	rm -rf "${WORK_DIR:?}/cwd" "${WORK_DIR:?}/home"
	mkdir -p "$WORK_DIR/cwd" "$WORK_DIR/home"

	if ! str_out="$(run_list "$str_scaffold" "" 2>&1)"; then
		fail "$str_name" "--list-copies exited non-zero: $str_out"
		return
	fi
	[[ -n "$str_out" ]] || { fail "$str_name" "empty output"; return; }

	if [[ -n "$(find "$WORK_DIR/cwd" "$WORK_DIR/home" -mindepth 1 -print -quit)" ]]; then
		fail "$str_name" "wrote files into cwd or HOME"
		return
	fi

	str_keyed="$(run_list "$str_scaffold" sentinel-key 2>&1)"
	[[ "$str_out" == "$str_keyed" ]] || { fail "$str_name" "output depends on the API key"; return; }

	if run_list "$str_scaffold" "" --roster false | grep -qE '	\.(github/)?\.review-bots\.yaml$'; then
		fail "$str_name" "--roster false still lists .review-bots.yaml"
		return
	fi

	str_work="$(mktemp -d)"
	if ! scaffold_for_real "$str_name" "$str_scaffold" "$str_work"; then
		fail "$str_name" "the real scaffold failed"
		rm -rf "$str_work"
		return
	fi
	str_diff="$(diff_against_real "$str_out" "$str_work/project")"
	rm -rf "$str_work"
	[[ -z "$str_diff" ]] || { fail "$str_name" "--list-copies drifted from the real scaffold:"$'\n'"$str_diff"; return; }
	pass "$str_name"
}

for str_meta in "$REPO_ROOT"/templates/*/skeleton.meta; do
	str_scaffold="$(grep '^scaffold=' "$str_meta" | cut -d= -f2-)"
	check_scaffold "$(basename "$(dirname "$str_meta")")" "$str_scaffold"
done

if run_list bin/scaffold/ts_lib.sh "" --roster maybe >/dev/null 2>&1; then
	fail "roster-validation" "--roster maybe was accepted"
else
	pass "roster-validation"
fi

((int_failures == 0)) || { echo "$int_failures failure(s)"; exit 1; }
echo "all list-copies checks passed"
