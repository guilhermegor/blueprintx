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

# A SECOND, TARGETED PASS for one class that sits BELOW the warning floor and should not.
#
# SC2030/SC2031 report a variable modified inside a `( … )` subshell, where the change is
# lost to the parent. ShellCheck rates that `info`, so `--severity=warning` filtered it out
# — and it had been filtering out a real bug the whole time: `prompt_git_remote_setup` set
# `push_done=1` inside a subshell, so the follow-up push ALWAYS ran, in six scaffolds. The
# gate had the finding and threw it away.
#
# The rest of the `info` tier is genuinely noise here (SC2059/SC2016/SC1091, ~78 findings,
# almost all intentional), which is why the floor is not simply lowered. `--include` asks
# for exactly the two codes instead: an assignment that silently does nothing is the same
# family of defect as a gate that silently does not run.
find bin -name '*.sh' -print0 |
	xargs -0 shellcheck -x --severity=info --include=SC2030,SC2031
