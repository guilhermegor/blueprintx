#!/usr/bin/env bash

set -euo pipefail

SKELETON="${1:?skeleton name required}"

fail() { echo "ERROR: [$SKELETON] $*" >&2; exit 1; }

[ "$(git rev-parse --show-toplevel 2>/dev/null)" = "$(pwd -P)" ] \
    || fail "$(pwd -P) is not the root of its own git repository."

if [ -n "$(git status --porcelain)" ]; then
    git status --short >&2
    fail "the tree has uncommitted or untracked changes after the run."
fi

str_pushed_note="push check skipped (no origin remote)"
if git remote get-url origin >/dev/null 2>&1; then
    str_pushed_note="pushed"
    git rev-parse --verify -q refs/heads/main >/dev/null \
        || fail "local branch main is missing; cannot prove it was pushed."
    git rev-parse --verify -q refs/remotes/origin/main >/dev/null \
        || fail "origin is set but origin/main is missing; cannot prove main was pushed."
    str_ahead="$(git rev-list --oneline refs/remotes/origin/main..refs/heads/main)"
    [ -z "$str_ahead" ] || { echo "$str_ahead" >&2; fail "local main has commits origin/main lacks."; }
fi

[ -z "$(find .specs -mindepth 1 -name .specs 2>/dev/null)" ] \
    || fail "a nested .specs directory was scaffolded."

echo "Final tree: committed, $str_pushed_note, no nested .specs."
