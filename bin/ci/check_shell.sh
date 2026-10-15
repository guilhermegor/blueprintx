#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

find bin -name '*.sh' -print0 | xargs -0 shellcheck -x --severity=warning

find bin -name '*.sh' -print0 |
	xargs -0 shellcheck -x --severity=info --include=SC2030,SC2031
