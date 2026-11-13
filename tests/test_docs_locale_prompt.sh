#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_')

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

scaffold_docs_probe() {
    local str_locale="$1" str_dir="$2"
    (
        # shellcheck source=bin/lib/spec.sh
        source "$REPO_ROOT/bin/lib/spec.sh"
        spec_stdin_for_skeleton lib-minimal "" \
            | DOCS_LOCALE="$str_locale" BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot \
                LINKEDIN_URL=https://www.linkedin.com/in/ci-bot \
                bash "$REPO_ROOT/bin/scaffold/python_lib_minimal.sh" \
                "$str_dir" docs-probe "Docs probe" "0.0.1"
    ) >"$str_dir/scaffold.log" 2>&1
}

test_scaffold_passes_docs_gate() {
    local str_locale="$1" str_dir str_out int_rc=0
    str_dir="$(mktemp -d)"
    if ! scaffold_docs_probe "$str_locale" "$str_dir"; then
        fail "lib-minimal $str_locale scaffold failed: $(tail -3 "$str_dir/scaffold.log")"
        rm -rf "$str_dir"
        return
    fi
    str_out="$(python3 "$str_dir/docs-probe/bin/check_docs_language.py" \
        --root "$str_dir/docs-probe" 2>&1)" || int_rc=$?
    if [ "$int_rc" -eq 0 ] && grep -Eq '\([1-9][0-9]* page\(s\) checked\)$' <<<"$str_out"; then
        pass "$str_locale scaffold passes the docs-language gate: $str_out"
    else
        fail "$str_locale scaffold, gate rc=$int_rc: $str_out"
    fi
    [ "$str_locale" = "pt-BR" ] && check_codespell_skips_relative_docs "$str_dir/docs-probe"
    rm -rf "$str_dir"
}

check_codespell_skips_relative_docs() {
    python3 - "$1/.codespellrc" <<'PY' \
        && pass "pt-BR .codespellrc skips the repo-relative path docs/index.md" \
        || fail "pt-BR .codespellrc skip does not match docs/index.md (pre-commit passes relative paths)"
import fnmatch, sys
str_skip = next(l for l in open(sys.argv[1]) if l.startswith("skip = "))[7:].strip()
sys.exit(0 if any(fnmatch.fnmatch("docs/index.md", g) for g in str_skip.split(",")) else 1)
PY
}

test_ptbr_twins_cover_shipped_pages() {
    local str_rel str_lib="$REPO_ROOT/templates/lib-minimal/docs" str_common="$REPO_ROOT/templates/python-common/docs"
    for str_rel in index.md usage.md examples.md faq.md contributing.md api/index.md api/reference.md; do
        [ -f "$str_lib/pt-BR/$str_rel" ] && pass "pt-BR twin of lib-minimal docs/$str_rel" \
            || fail "no pt-BR twin of lib-minimal docs/$str_rel"
    done
    for str_rel in changelog.md releasing-1-0-0.md incidents.md; do
        [ -f "$str_common/pt-BR/$str_rel" ] && pass "pt-BR twin of shipped docs/$str_rel" \
            || fail "no pt-BR twin of shipped docs/$str_rel"
    done
}

test_ptbr_readme_keeps_slugs() {
    local str_want str_got
    # shellcheck source=bin/lib/scaffold_readme.sh
    source "$REPO_ROOT/bin/lib/scaffold_readme.sh"
    str_want="$(scaffold_filter_archetype_blocks library <"$REPO_ROOT/templates/python-common/README.md" \
        | grep -o '<!-- slug: [a-z-]* -->')"
    str_got="$(grep -o '<!-- slug: [a-z-]* -->' "$REPO_ROOT/templates/lib-minimal/README.pt-BR.md")"
    [ "$str_want" = "$str_got" ] \
        && pass "pt-BR README carries the library slug comments unchanged" \
        || fail "pt-BR README slugs differ from the library README: $(diff <(echo "$str_want") <(echo "$str_got"))"
}

main() {
    test_ptbr_twins_cover_shipped_pages
    test_ptbr_readme_keeps_slugs
    test_scaffold_passes_docs_gate en
    test_scaffold_passes_docs_gate pt-BR
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
