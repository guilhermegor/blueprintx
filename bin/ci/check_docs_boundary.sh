#!/usr/bin/env bash
# Guards the docs/ boundary (blueprintx#536): docs/ is solely for published MkDocs
# documentation. Working material about HOW the work gets done — backlog ledgers, lesson
# stores, .superpowers material, spec/plan artifacts — belongs outside it. This is the
# owner's standing rule (2026-09-18): "docs/backlog, docs/**/*lessons*, .superpowers and
# any other work related to lessons to other packages/repos/frameworks/ai handling/
# superpowers — the boundary is to stay here, docs/ is solely for documentation."
#
# Root-repo-only for now, unlike the rest of the `--root` gate family. BlueprintX's own
# docs/ is the published-site source, and the live violation there (docs/backlog/, still
# MANDATED by the root CLAUDE.md's "Backlog discipline" section) is unambiguous. Running
# this same deny-list over templates/*/docs/ is a separate, larger question:
# templates/python-common/ ships its OWN docs/backlog/ *ledger* feature
# (bin/check_backlog_ledger.py, wired into that tier's pre-commit + CI) as a deliberate,
# gated product feature for GENERATED projects, not an accidental violation of this rule.
# Conflating the two would flag an intentional feature as a defect — left to a follow-up
# issue rather than decided here (see the blueprintx#536 PR body).
#
# Deny-list (working material, never published docs):
#   - docs/backlog/ (the directory itself, and everything under it)
#   - any path whose basename contains "lesson" (case-insensitive) — a lessons store
#   - any path with a .superpowers* segment
#   - any path whose basename is exactly design.md or plan.md — spec/plan artifacts have
#     their own home since blueprintx#447: .specs/
#
# A directory that matches the deny-list is reported ONCE and not descended into — the
# violation is the whole path, not each file under it (the spike that sized this gate
# already counted those separately; see the PR body).

set -euo pipefail

# `*` skips dot-prefixed entries (the check_specs_structure.sh defect this gate must not
# repeat) — dotglob covers a `.superpowers/` directory; nullglob keeps an empty directory
# from yielding the literal glob pattern as a filename.
shopt -s dotglob nullglob

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DOCS_DIR="$REPO_ROOT/docs"
errors=0
checked=0

# No docs/ at all is not an error — some scaffolds/contexts have none.
if [ ! -d "$DOCS_DIR" ]; then
    echo "check_docs_boundary: no docs/ directory — nothing to check."
    exit 0
fi

# Present but unreadable must FAIL, never silently pass as "clean" — same rule as
# gate_free_surface: a check that cannot see its subject is not a check that passed one.
if [ ! -r "$DOCS_DIR" ]; then
    echo "ERROR: docs/ exists but is not readable" >&2
    exit 1
fi

is_denied() {
    # $1 = path relative to docs/, e.g. "backlog" or "guide/lessons-learned.md".
    # Prints the reason and returns 0 on a match; returns 1 (no output) otherwise.
    local rel="$1" base parts segment
    base="$(basename "$rel")"
    case "$rel" in
        backlog | backlog/*)
            echo "under docs/backlog/ (working material, not published docs)"
            return 0
            ;;
    esac
    case "${base,,}" in
        *lesson*)
            echo "basename matches *lesson* (a lessons store, not published docs)"
            return 0
            ;;
        design.md | plan.md)
            echo "is a spec/plan artifact — belongs in .specs/, not docs/ (blueprintx#447)"
            return 0
            ;;
    esac
    IFS='/' read -ra parts <<< "$rel"
    for segment in "${parts[@]}"; do
        case "${segment,,}" in
            .superpowers*)
                echo "has a .superpowers path segment (not published docs)"
                return 0
                ;;
        esac
    done
    return 1
}

walk() {
    # $1 = absolute directory to walk.
    local dir="$1" entry rel reason
    for entry in "$dir"/*; do
        [ -e "$entry" ] || continue
        rel="${entry#"$DOCS_DIR"/}"
        checked=$((checked + 1))
        if reason="$(is_denied "$rel")"; then
            echo "ERROR: docs/$rel — $reason" >&2
            errors=$((errors + 1))
            continue # denied dir: already flagged as a whole, don't enumerate its contents
        fi
        if [ -d "$entry" ]; then
            walk "$entry"
        fi
    done
}

walk "$DOCS_DIR"

# A readable docs/ that yields zero entries is suspicious (an empty dir, or a walk bug),
# not evidence of a clean tree — report it as a failure rather than a silent pass.
if [ "$checked" -eq 0 ]; then
    echo "ERROR: docs/ exists but contains nothing to check" >&2
    exit 1
fi

if [ "$errors" -gt 0 ]; then
    echo "check_docs_boundary: $errors error(s) found." >&2
    exit 1
fi

echo "check_docs_boundary: docs/ boundary is clean ($checked entries checked)."
