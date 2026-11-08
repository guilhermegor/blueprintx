#!/bin/bash

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

run_prompt() {
    local str_answer="$1"
    (
        set --
        # shellcheck source=bin/blueprintx.sh
        source "$REPO_ROOT/bin/blueprintx.sh"
        printf '%s\n' "$str_answer" | prompt_docs_locale 2>/dev/null
    )
}

expect_prompt() {
    local str_got int_rc=0
    str_got="$(run_prompt "$1")" || int_rc=$?
    if [ "$int_rc" -ne 0 ]; then
        fail "answer '$1' -> prompt exited $int_rc (expected '$2')"
    elif [ "$str_got" = "$2" ]; then
        pass "answer '$1' -> '$2'"
    else
        fail "answer '$1' -> '$str_got' (expected '$2')"
    fi
}

test_prompt_mapping() {
    expect_prompt "" "en"
    expect_prompt "1" "en"
    expect_prompt "2" "pt-BR"
    local str_got int_rc=0
    str_got="$(run_prompt $'9\n2')" || int_rc=$?
    if [ "$int_rc" -ne 0 ]; then
        fail "invalid answer then '2' -> prompt exited $int_rc"
    elif [ "$str_got" = "pt-BR" ]; then
        pass "invalid answer re-prompts, then accepts '2'"
    else
        fail "invalid answer produced '$str_got'"
    fi
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
            && grep -q "envsubst '\${PROJECT_DISPLAY_NAME} \${PROJECT_DESCRIPTION_ESC} \${REPOSITORY} \${DOCS_LOCALE}'" "$str_scaffold" \
            && pass "default + envsubst in ${str_scaffold#"$REPO_ROOT"/}" \
            || fail "DOCS_LOCALE not rendered in ${str_scaffold#"$REPO_ROOT"/}"
    done
    [ "$int_seen" -gt 0 ] || fail "discovered zero mkdocs-rendering scaffolds"
}

test_render_falls_back_to_en() {
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

test_marker_step_tolerates_missing_docs_dir() {
    local str_dir str_err
    str_dir="$(mktemp -d)"
    str_err="$(DOCS_LOCALE=pt-BR bash -c \
        'source "$1"; scaffold_mark_untranslated "$2"' _ \
        "$REPO_ROOT/bin/lib/scaffold_docs_locale.sh" "$str_dir" 2>&1)" \
        && [ -z "$str_err" ] \
        && pass "marker step is silent on a tree without docs/" \
        || fail "marker step failed or wrote errors without docs/: $str_err"
    rm -rf "$str_dir"
}

test_marker_step_is_idempotent() {
    local str_dir int_count
    str_dir="$(mktemp -d)"
    mkdir -p "$str_dir/docs"
    printf '# T\n' >"$str_dir/docs/index.md"
    DOCS_LOCALE=pt-BR bash -c \
        'source "$1"; scaffold_mark_untranslated "$2"; scaffold_mark_untranslated "$2"' _ \
        "$REPO_ROOT/bin/lib/scaffold_docs_locale.sh" "$str_dir"
    int_count="$(grep -c 'docs-lang:untranslated' "$str_dir/docs/index.md")"
    [ "$int_count" = "1" ] \
        && pass "marker step run twice leaves one marker" \
        || fail "marker step run twice left $int_count markers"
    rm -rf "$str_dir"
}

main() {
    test_marker_step_is_idempotent
    test_marker_step_tolerates_missing_docs_dir
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
