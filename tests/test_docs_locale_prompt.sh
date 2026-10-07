#!/bin/bash
# Should-fail regression tests for the documentation-locale scaffold choice (blueprintx#247).
#
# Three things can silently rot: the prompt's choice→value mapping, the `${DOCS_LOCALE}`
# placeholder in a skeleton's mkdocs.yml, and the scaffold's envsubst list that renders it.
# A placeholder present in the template but missing from the envsubst list ships a literal
# `${DOCS_LOCALE}` into every generated project, with no red check anywhere — so each leg
# is asserted here rather than trusted.
#
# Usage: bash tests/test_docs_locale_prompt.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

int_failures=0

fail() {
    print_status "error" "FAIL: $1"
    int_failures=$((int_failures + 1))
}

pass() {
    print_status "success" "PASS: $1"
}

# Runs prompt_docs_locale with $1 on stdin and prints its stdout — the value the menu
# hands to the scaffold. Sourced in a subshell so blueprintx.sh's main never runs.
run_prompt() {
    local str_answer="$1"
    (
        # The top-level option loop parses "$@" on source, so hand it nothing.
        set --
        # shellcheck source=bin/blueprintx.sh
        source "$REPO_ROOT/bin/blueprintx.sh"
        printf '%s\n' "$str_answer" | prompt_docs_locale 2>/dev/null
    )
}

expect_prompt() {
    # $1 = stdin answer, $2 = expected value
    local str_got
    str_got="$(run_prompt "$1")"
    if [ "$str_got" = "$2" ]; then
        pass "answer '$1' -> '$2'"
    else
        fail "answer '$1' -> '$str_got' (expected '$2')"
    fi
}

test_prompt_mapping() {
    expect_prompt "" "en"
    expect_prompt "1" "en"
    expect_prompt "2" "pt-BR"
    # An invalid answer re-prompts and reads the next line; "9" must never leak through.
    local str_got
    str_got="$(run_prompt $'9\n2')"
    [ "$str_got" = "pt-BR" ] && pass "invalid answer re-prompts, then accepts '2'" \
        || fail "invalid answer produced '$str_got'"
}

test_templates_and_scaffolds_wired() {
    local f str_scaffold int_seen=0
    for f in "$REPO_ROOT"/templates/*/mkdocs.yml; do
        int_seen=$((int_seen + 1))
        grep -q '^  language: \${DOCS_LOCALE}$' "$f" \
            && pass "placeholder in ${f#"$REPO_ROOT"/}" \
            || fail "no \${DOCS_LOCALE} placeholder in ${f#"$REPO_ROOT"/}"
    done
    [ "$int_seen" -gt 0 ] || fail "discovered zero templates/*/mkdocs.yml"

    int_seen=0
    for str_scaffold in "$REPO_ROOT"/bin/scaffold/python_*.sh; do
        grep -q 'mkdocs.yml' "$str_scaffold" || continue
        int_seen=$((int_seen + 1))
        grep -q 'export DOCS_LOCALE="\${DOCS_LOCALE:-en}"' "$str_scaffold" \
            && grep -q "envsubst '\${PROJECT_DISPLAY_NAME} \${REPOSITORY} \${DOCS_LOCALE}'" "$str_scaffold" \
            && pass "default + envsubst in ${str_scaffold#"$REPO_ROOT"/}" \
            || fail "DOCS_LOCALE not rendered in ${str_scaffold#"$REPO_ROOT"/}"
    done
    [ "$int_seen" -gt 0 ] || fail "discovered zero mkdocs-rendering scaffolds"
}

test_render_falls_back_to_en() {
    # The exact command a scaffold runs, in a clean environment: no DOCS_LOCALE set.
    local str_out
    str_out="$(env -u DOCS_LOCALE bash -c '
        export DOCS_LOCALE="${DOCS_LOCALE:-en}"
        PROJECT_DISPLAY_NAME=x REPOSITORY=y \
            envsubst "\${PROJECT_DISPLAY_NAME} \${REPOSITORY} \${DOCS_LOCALE}" \
            < "$1"' _ "$REPO_ROOT/templates/lib-minimal/mkdocs.yml")"
    grep -q '^  language: en$' <<<"$str_out" \
        && pass "unset DOCS_LOCALE renders language: en" \
        || fail "unset DOCS_LOCALE did not render language: en"
    str_out="$(DOCS_LOCALE=pt-BR PROJECT_DISPLAY_NAME=x REPOSITORY=y \
        envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY} ${DOCS_LOCALE}' \
        < "$REPO_ROOT/templates/lib-minimal/mkdocs.yml")"
    grep -q '^  language: pt-BR$' <<<"$str_out" \
        && pass "DOCS_LOCALE=pt-BR renders language: pt-BR" \
        || fail "DOCS_LOCALE=pt-BR did not render language: pt-BR"
}

main() {
    test_prompt_mapping
    test_templates_and_scaffolds_wired
    test_render_falls_back_to_en
    if [ "$int_failures" -gt 0 ]; then
        print_status "error" "$int_failures failure(s)"
        exit 1
    fi
    print_status "success" "all docs-locale checks passed"
}

main "$@"
