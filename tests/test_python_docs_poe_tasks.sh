#!/usr/bin/env bash
set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/bin/lib/spec.sh"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

export GIT_AUTHOR_NAME=ci-bot GIT_COMMITTER_NAME=ci-bot
export GIT_AUTHOR_EMAIL=ci-bot@example.com GIT_COMMITTER_EMAIL=ci-bot@example.com
export HOME="$WORK_DIR/home"
mkdir -p "$HOME"

int_failures=0
for str_tier in lib-minimal api-service-native-db ddd-service-native-db ddd-service-orm-db \
	mvc-service-native-db mvc-service-orm-db; do
	str_scaffold="$(sed -n 's/^scaffold=//p' "$REPO_ROOT/templates/$str_tier/skeleton.meta")"
	path_project="$WORK_DIR/$str_tier"
	mkdir -p "$path_project.parent"
	GITGUARDIAN_API_KEY="" spec_stdin_for_skeleton "$str_tier" "" \
		| BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot \
			bash "$REPO_ROOT/$str_scaffold" "$path_project.parent" project \
			"CI poe docs oracle" "0.0.1" >"$WORK_DIR/scaffold.log" 2>&1 \
		|| { echo "FAIL: $str_tier scaffold exited non-zero"; tail -20 "$WORK_DIR/scaffold.log"; exit 1; }
	path_project="$path_project.parent/project"

	list_defined="$(cd "$path_project" && python3 -c '
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from check_poe_task_set import load_tasks
print("\n".join(sorted(load_tasks(Path.cwd()))))
' "$REPO_ROOT/bin/ci")"
	[ -n "$list_defined" ] || { echo "FAIL: $str_tier: no poe tasks were read"; exit 1; }

	list_cited="$(grep -rhoE --include='*.md' --exclude-dir=.git --exclude-dir=.venv \
		--exclude-dir=node_modules '(^|`|\$ )[[:space:]]*poe [A-Za-z_][A-Za-z0-9_-]*' \
		"$path_project" | sed -E 's/.*poe //' | sort -u)"
	[ -n "$list_cited" ] || { echo "FAIL: $str_tier: no poe task is cited"; exit 1; }

	while IFS= read -r str_task; do
		if grep -qxF "$str_task" <<<"$list_defined"; then
			echo "ok: $str_tier cites poe $str_task"
		else
			echo "FAIL: $str_tier cites poe $str_task, which the project does not define"
			int_failures=$((int_failures + 1))
		fi
	done <<<"$list_cited"
done

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; exit 1; }
echo "all cases passed"
