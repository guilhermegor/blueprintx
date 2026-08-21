#!/usr/bin/env bash
# Lints every shell script under bin/ with ShellCheck at severity >= warning.
# Single source of truth shared by the Scaffold Checks CI (lint-shell job) and
# the root pre-commit hook.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# `-x` makes ShellCheck FOLLOW `source` into bin/lib/*.sh, guided by the
# `# shellcheck source=` directives in the callers. Without it, a variable whose only
# consumer lives in a sourced lib reads as SC2034 "appears unused" — which is not a
# false positive to silence but a question ShellCheck cannot answer while it analyses
# one file at a time. Following the source lets it analyse the real program instead,
# so the finding disappears because it stopped being true, not because it was muted.
find bin -name '*.sh' -print0 | xargs -0 shellcheck -x --severity=warning
