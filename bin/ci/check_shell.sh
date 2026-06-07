#!/usr/bin/env bash
# Lints every shell script under bin/ with ShellCheck at severity >= warning.
# Single source of truth shared by the Scaffold Checks CI (lint-shell job) and
# the root pre-commit hook.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

find bin -name '*.sh' -print0 | xargs -0 shellcheck --severity=warning
