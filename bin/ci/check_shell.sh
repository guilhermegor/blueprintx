#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

find bin -name '*.sh' -print0 | xargs -0 shellcheck -x --severity=warning

find bin -name '*.sh' -print0 |
	xargs -0 shellcheck -x --severity=info --include=SC2030,SC2031

if command -v shfmt >/dev/null 2>&1; then
	find templates/common -name '*.sh' -print0 | xargs -0 -r shfmt -d
elif [[ "${LINT_SHELL_REQUIRED:-0}" == "1" ]]; then
	echo "shfmt is required but not installed" >&2
	exit 1
fi
