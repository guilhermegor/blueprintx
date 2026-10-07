#!/usr/bin/env bash
# Validates the .specs/ layout (blueprintx#447, #583). One implementation, two callers: this
# repo's own tree (default) and a generated project (`--root <dir>`, as the other gates take it).
# .specs/CLAUDE.md is the human-facing version of every rule below; each is checked, not claimed.
#
#   1. If .specs/ exists, .specs/CLAUDE.md must exist.
#   2. Top level allows only CLAUDE.md, features/, backlog/, _lessons/ (_lessons/ is free-form).
#   3. features/ holds directories only, kebab-case with a letter, and never a change TYPE
#      (bugfix/, chore/, ... — dotfiles-dev#442: features/ splits on lifecycle, not change type).
#   4. features/<name>/ holds at least one of design.md, plan.md, tasks.md. pr.md or
#      pr-<N>-<kebab>.md are recognised but never sufficient; any other pr*.md name fails.
#   5. Every task line in tasks.md uses [ ], [~] <branch> or [x] — [~] must name a branch.
#   6. backlog/ is flat, <kebab-topic>_YYYYMMDD_HHMMSS.md.

set -euo pipefail

# `*` skips dot-prefixed entries, so a stray `.specs/.notes` or a hidden feature directory
# walked straight past both loops below — the scans reported clean on exactly the entries
# a reviewer would least expect to be there. `nullglob` keeps an empty directory from
# yielding the literal pattern as a filename.
shopt -s dotglob nullglob

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [ "${1:-}" = "--root" ]; then
    # A missing --root must fail: every later check would see "no .specs/" and report success.
    [ -n "${2:-}" ] && [ -d "$2" ] || {
        echo "ERROR: --root needs an existing directory (got '${2:-}')" >&2
        exit 2
    }
    REPO_ROOT="$(cd "$2" && pwd)"
    shift 2
fi
[ "$#" -eq 0 ] || {
    echo "ERROR: unexpected argument '$1' (usage: check_specs_structure.sh [--root <dir>])" >&2
    exit 2
}
SPECS_DIR="$REPO_ROOT/.specs"
errors=0

# Conventional-Commit and branch types — a feature directory named after one is a type-folder.
is_change_type() {
    case "$1" in
        feat|feature|fix|bugfix|hotfix|chore|docs|refactor|perf|test|style|build|ci|revert|release)
            return 0 ;;
        *) return 1 ;;
    esac
}

# Every task line (`- [?]` / `* [?]`, outside code fences) must be [ ], [~] <branch> or [x].
check_tasks_markers() {
    local file="$1" label="$2" bad
    bad="$(awk '
        /^[[:space:]]*```/ { fence = !fence; next }
        fence { next }
        match($0, /^[[:space:]]*[-*] \[[^]]*\]/) {
            mark = substr($0, RSTART, RLENGTH); sub(/^[^[]*\[/, "", mark); sub(/\]$/, "", mark)
            rest = substr($0, RLENGTH + 1)
            if (mark != " " && mark != "~" && mark != "x") print NR ": " $0
            else if (mark == "~" && rest !~ /^ +[^ ]/) print NR ": " $0
        }' "$file")"
    if [ -n "$bad" ]; then
        printf '%s\n' "$bad" | while IFS= read -r line; do
            echo "ERROR: $label line $line — markers are [ ], [~] <branch> and [x]" >&2
        done
        errors=$((errors + $(printf '%s\n' "$bad" | wc -l)))
    fi
}

# No .specs/ at all is not an error — it's simply not adopted yet.
if [ ! -d "$SPECS_DIR" ]; then
    echo "check_specs_structure: no .specs/ directory — nothing to check."
    exit 0
fi

if [ ! -f "$SPECS_DIR/CLAUDE.md" ]; then
    echo "ERROR: .specs/ exists but .specs/CLAUDE.md is missing" >&2
    errors=$((errors + 1))
fi

for entry in "$SPECS_DIR"/*; do
    name="$(basename "$entry")"
    case "$name" in
        CLAUDE.md|features|backlog|_lessons) ;;
        *)
            echo "ERROR: unexpected top-level entry .specs/$name (only CLAUDE.md, features/, backlog/, _lessons/ are allowed)" >&2
            errors=$((errors + 1))
            ;;
    esac
done

if [ -d "$SPECS_DIR/features" ]; then
    for entry in "$SPECS_DIR/features"/*; do
        [ -e "$entry" ] || continue
        name="$(basename "$entry")"
        # A placeholder that keeps an otherwise empty features/ in git, as the scaffold ships.
        [ "$name" = ".gitkeep" ] && [ -f "$entry" ] && continue
        if [ ! -d "$entry" ]; then
            echo "ERROR: .specs/features/$name is not a directory" >&2
            errors=$((errors + 1))
            continue
        fi
        # Kebab-case AND at least one letter. `[a-z0-9]` alone accepts a bare `447`,
        # which is the exact case this check was added for — an issue number is not a
        # feature name. Caught by the fixture, not by reading the pattern.
        if ! printf '%s' "$name" | grep -qE '^[a-z0-9]+(-[a-z0-9]+)*$' ||
            ! printf '%s' "$name" | grep -q '[a-z]'; then
            echo "ERROR: .specs/features/$name is not kebab-case — .specs/CLAUDE.md" \
                 "requires lowercase words joined by single hyphens (e.g. 'specs-directory'," \
                 "not '447' or 'Specs_Directory')" >&2
            errors=$((errors + 1))
        fi
        if is_change_type "$name"; then
            echo "ERROR: .specs/features/$name is a change type, not a feature — features/ splits" \
                 "on lifecycle; the type already lives in the branch name and the commit prefix" \
                 "(dotfiles-dev#442)" >&2
            errors=$((errors + 1))
        fi
        if [ ! -f "$entry/design.md" ] && [ ! -f "$entry/plan.md" ] &&
            [ ! -f "$entry/tasks.md" ]; then
            echo "ERROR: .specs/features/$name has none of design.md, plan.md or tasks.md" \
                 "(pr.md alone is not a feature)" >&2
            errors=$((errors + 1))
        fi
        for member in "$entry"/pr.md "$entry"/pr-*.md; do
            member_name="$(basename "$member")"
            if ! printf '%s' "$member_name" | grep -qE '^pr(-[0-9]+-[a-z0-9]+(-[a-z0-9]+)*)?\.md$'; then
                echo "ERROR: .specs/features/$name/$member_name is not pr.md or" \
                     "pr-<N>-<kebab-slug>.md" >&2
                errors=$((errors + 1))
            fi
        done
        if [ -f "$entry/tasks.md" ]; then
            check_tasks_markers "$entry/tasks.md" ".specs/features/$name/tasks.md"
        fi
    done
fi

if [ -d "$SPECS_DIR/backlog" ]; then
    for entry in "$SPECS_DIR/backlog"/*; do
        [ -e "$entry" ] || continue
        name="$(basename "$entry")"
        if [ ! -f "$entry" ]; then
            echo "ERROR: .specs/backlog/$name is not a file — .specs/backlog/ is flat" >&2
            errors=$((errors + 1))
            continue
        fi
        if ! printf '%s' "$name" | grep -qE '^[a-z0-9]+(-[a-z0-9]+)*_[0-9]{8}_[0-9]{6}\.md$'; then
            echo "ERROR: .specs/backlog/$name does not match" \
                 "<kebab-topic>_YYYYMMDD_HHMMSS.md — .specs/CLAUDE.md" >&2
            errors=$((errors + 1))
        fi
    done
fi

if [ "$errors" -gt 0 ]; then
    echo "check_specs_structure: $errors error(s) found." >&2
    exit 1
fi

echo "check_specs_structure: .specs/ layout is valid."
