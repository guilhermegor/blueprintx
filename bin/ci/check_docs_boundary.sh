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
# 🔴 THE RULE IS THE PRINCIPLE, THE LIST IS ONLY WHAT WE HAVE MET SO FAR.
# Everything under docs/ must be published documentation. Anything that is not does not
# merely get REJECTED — it gets REDIRECTED to the place that owns it. Every rule below
# therefore names a destination, and a rule that cannot name one is not ready to ship:
# "this does not belong here" without "it belongs there" just moves the problem to
# whoever reads the failure.
#
# ⚠️ The deny-list is OPEN and expected to grow. It is a list of cases encountered, not a
# definition of the rule, and the destinations below are examples of the shape — the
# right home may be .specs/, CONTRIBUTING.md, README.md, SECURITY.md, a tool's own
# directory, or somewhere nobody has needed yet. When you meet a new kind of
# working material, add the case AND its destination; do not treat the absence of a rule
# as permission.
#
# Known cases and where each belongs:
#   - docs/backlog/ → out of docs/: a progress ledger beside the work; reader-facing
#     content to README.md / CONTRIBUTING.md
#   - basename contains "lesson" → the operator's ~/.claude/memory/lessons* stores; a
#     lesson that has hardened into a project rule goes to CONTRIBUTING.md as the RULE
#   - basename design.md / plan.md → .specs/features/<feature-name>/ (blueprintx#447)
#   - basename security.md / threat*.md → the ROOT SECURITY.md (GitHub only reads it from
#     the repo root, .github/ or docs/ root, so a nested copy is invisible to the
#     advisory UI)
#   - any .superpowers* path segment → that tool's own home, never the published site
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
            echo "working material, not published docs — move it OUT of docs/: an in-repo" \
                 "progress ledger belongs beside the work it tracks, and anything a reader" \
                 "of the project needs belongs in README.md or CONTRIBUTING.md"
            return 0
            ;;
    esac
    case "${base,,}" in
        *lesson*)
            echo "a lessons store, not published docs — lessons live in the operator's" \
                 "~/.claude/memory/lessons* stores; if a lesson has become a rule this" \
                 "project follows, state the RULE in CONTRIBUTING.md and drop the narrative"
            return 0
            ;;
        design.md | plan.md)
            echo "a spec/plan artifact — belongs in .specs/features/<feature-name>/," \
                 "not docs/ (blueprintx#447)"
            return 0
            ;;
        security.md | threat*.md)
            echo "security policy is not a docs/ page — GitHub reads SECURITY.md from the" \
                 "repository root, .github/ or docs/ root only, so a nested copy is invisible" \
                 "to the advisory UI; move it to the root SECURITY.md"
            return 0
            ;;
    esac
    IFS='/' read -ra parts <<< "$rel"
    for segment in "${parts[@]}"; do
        case "${segment,,}" in
            .superpowers*)
                echo "harness/tooling working material, not published docs — it belongs in" \
                     "the tool's own home (.superpowers/ at the repo root, or the operator's" \
                     "~/.claude), never under the published site"
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
        # A symlink is classified above like any other entry, then treated as a LEAF.
        # Recursing into one lets a link that points at an ancestor re-enter the tree
        # through a longer path: measured on a 3-file fixture with docs/a/b/loop -> docs,
        # the walk reported "163 entries checked" and only stopped because the kernel
        # hit its ELOOP limit. A denied file inside such a loop is also reported many
        # times over. The published site is a file tree; nothing here needs to follow
        # links to classify what lives under docs/.
        if [ -L "$entry" ]; then
            continue
        fi
        if [ -d "$entry" ]; then
            # 🔴 An unreadable/unsearchable directory must FAIL, never pass quietly.
            # `"$dir"/*` yields nothing when the directory cannot be read, so walk would
            # return having recorded no error: measured with docs/secret/ at mode 000
            # holding docs/secret/backlog/, the gate printed "boundary is clean" and
            # exited 0 while a real violation sat inside it. That is the one outcome this
            # gate family forbids — reporting success for having checked nothing.
            if [ ! -r "$entry" ] || [ ! -x "$entry" ]; then
                echo "ERROR: docs/$rel — directory is not readable/searchable, so its" \
                     "contents cannot be checked; this is a broken check, not a clean one" >&2
                errors=$((errors + 1))
                continue
            fi
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
