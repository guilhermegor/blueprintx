#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TEMPLATES_DIR="$REPO_ROOT/templates"
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"
REQUIRED_FIELDS=(language display_name description scaffold ships_docs)
CHECK_README="$REPO_ROOT/templates/common/bin/check_readme_structure.sh"
errors=0

weakening_gate_for() {
    case "$1" in
        python) echo "templates/python-common/bin/check_assertion_weakening.py" ;;
        typescript) echo "templates/ts-common/src/utils/assertion-weakening.cjs" ;;
        bash) echo "-" ;;
        *) echo "" ;;
    esac
}

if [ ! -f "$CLAUDE_MD" ]; then
    echo "ERROR: $CLAUDE_MD not found — cannot check skeleton documentation" >&2
    errors=$((errors + 1))
fi

for meta in "$TEMPLATES_DIR"/*/skeleton.meta; do
    [ -f "$meta" ] || continue
    skeleton_dir="$(basename "$(dirname "$meta")")"
    echo "Checking: templates/$skeleton_dir/skeleton.meta"

    for field in "${REQUIRED_FIELDS[@]}"; do
        value="$(grep "^${field}=" "$meta" | cut -d= -f2- | tr -d '[:space:]' || true)"
        if [ -z "$value" ]; then
            echo "  ERROR: field '$field' is missing or empty" >&2
            errors=$((errors + 1))
        fi
    done

    scaffold_rel="$(grep '^scaffold=' "$meta" | cut -d= -f2- || true)"
    if [ -n "$scaffold_rel" ] && [ ! -f "$REPO_ROOT/$scaffold_rel" ]; then
        echo "  ERROR: scaffold path does not exist: $scaffold_rel" >&2
        errors=$((errors + 1))
    fi

    if [ "$(grep -c '^ships_docs=' "$meta" || true)" -gt 1 ]; then
        echo "  ERROR: ships_docs is declared more than once" >&2
        errors=$((errors + 1))
    fi
    str_ships_docs="$(grep -m1 '^ships_docs=' "$meta" | cut -d= -f2- || true)"
    if [ -n "$str_ships_docs" ] && [ "$str_ships_docs" != "true" ] && [ "$str_ships_docs" != "false" ]; then
        echo "  ERROR: ships_docs $(printf '%q' "$str_ships_docs") must be exactly true or false" >&2
        errors=$((errors + 1))
    elif [ -n "$str_ships_docs" ] && [ -f "$REPO_ROOT/$scaffold_rel" ]; then
        str_actual=false
        str_code="$(grep -vE '^[[:space:]]*#' "$REPO_ROOT/$scaffold_rel" | sed -E 's/[[:space:]]+#.*$//' || true)"
        grep -qE 'mkdocs\.yml|docusaurus\.config' <<< "$str_code" && str_actual=true
        if [ "$str_actual" != "$str_ships_docs" ]; then
            echo "  ERROR: ships_docs=$str_ships_docs but the scaffold script implies $str_actual" >&2
            errors=$((errors + 1))
        fi
    fi

    str_archetype="$(grep '^readme_archetype=' "$meta" | cut -d= -f2- | tr -d '[:space:]' || true)"
    if [ -n "$str_archetype" ] && ! bash "$CHECK_README" --list-archetypes | grep -qxF -- "$str_archetype"; then
        echo "  ERROR: readme_archetype '$str_archetype' is not one of: $(bash "$CHECK_README" --list-archetypes | tr '\n' ' ')" >&2
        errors=$((errors + 1))
    fi

    str_language="$(grep '^language=' "$meta" | cut -d= -f2- | tr -d '[:space:]' || true)"
    str_gate="$(weakening_gate_for "$str_language")"
    if [ -n "$str_language" ] && [ -z "$str_gate" ]; then
        echo "  ERROR: language '$str_language' ships no assertion-weakening gate" >&2
        errors=$((errors + 1))
    elif [ -n "$str_gate" ] && [ "$str_gate" != "-" ] && [ ! -f "$REPO_ROOT/$str_gate" ]; then
        echo "  ERROR: assertion-weakening gate missing: $str_gate" >&2
        errors=$((errors + 1))
    fi

    if [ -f "$CLAUDE_MD" ] && ! grep -qF -- "$skeleton_dir" "$CLAUDE_MD"; then
        echo "  ERROR: skeleton '$skeleton_dir' is not mentioned in CLAUDE.md" >&2
        errors=$((errors + 1))
    fi
done

if [ "$errors" -gt 0 ]; then
    echo "validate_meta: $errors error(s) found." >&2
    exit 1
fi

echo "validate_meta: all skeleton.meta files are valid."
