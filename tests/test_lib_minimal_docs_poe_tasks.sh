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

path_project="$WORK_DIR/project"
GITGUARDIAN_API_KEY="" spec_stdin_for_skeleton lib-minimal "" \
	| BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot \
		bash "$REPO_ROOT/bin/scaffold/python_lib_minimal.sh" \
		"$WORK_DIR" project "CI poe docs oracle" "0.0.1" >"$WORK_DIR/scaffold.log" 2>&1 \
	|| { echo "FAIL: lib-minimal scaffold exited non-zero"; tail -20 "$WORK_DIR/scaffold.log"; exit 1; }

list_defined="$(cd "$path_project" && python3 -c '
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from check_poe_task_set import load_tasks
print("\n".join(sorted(load_tasks(Path.cwd()))))
' "$REPO_ROOT/bin/ci")"
[ -n "$list_defined" ] || { echo "FAIL: no poe tasks were read from the scaffold"; exit 1; }

list_cited="$(grep -rhoE '(^|`|\$ )[[:space:]]*poe [a-z_][a-z0-9_]*' "$path_project/docs" \
	| sed -E 's/.*poe //' | sort -u)"
[ -n "$list_cited" ] || { echo "FAIL: no poe task is cited in the scaffold docs"; exit 1; }

int_failures=0
while IFS= read -r str_task; do
	if grep -qxF "$str_task" <<<"$list_defined"; then
		echo "ok: docs cite poe $str_task"
	else
		echo "FAIL: docs cite poe $str_task, which the project does not define"
		int_failures=$((int_failures + 1))
	fi
done <<<"$list_cited"

[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; exit 1; }
echo "all cases passed"
