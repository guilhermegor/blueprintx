#!/bin/bash

set -euo pipefail

while IFS= read -r str_var; do unset "$str_var"; done < <(compgen -e | grep '^GIT_' || true)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
# shellcheck source=bin/lib/scaffold_readme.sh
source "$REPO_ROOT/bin/lib/scaffold_readme.sh"

GATE="$REPO_ROOT/templates/common/bin/check_readme_structure.sh"
int_failures=0

expect() {
    if [ "$2" = "$3" ]; then
        return
    fi
    print_status "error" "$1 (want '$2', got '$3')"
    int_failures=$((int_failures + 1))
}

linkedin_for() {
    (
        unset LINKEDIN_URL
        [ -z "${1:-}" ] || LINKEDIN_URL="$1"
        resolve_linkedin_url >/dev/null 2>&1 </dev/null
        printf '%s' "$LINKEDIN_URL"
    )
}

render_python_readme() {
    local str_skeleton="$1" path_out="$2"
    (
        BLUEPRINTX_ROOT="$REPO_ROOT"
        PROJECT_NAME=acme PROJECT_DESCRIPTION="A test project." PROJECT_DISPLAY_NAME=Acme
        GITHUB_USERNAME=ci-bot LICENSE_CHOICE=MIT LINKEDIN_URL="$LINKEDIN_URL"
        scaffold_render_readme "$str_skeleton" "$REPO_ROOT/templates/python-common/README.md" "$path_out" >/dev/null
    )
}

test_env_value_wins() {
    expect "LINKEDIN_URL from the environment is kept" \
        "https://www.linkedin.com/in/ci-bot" "$(linkedin_for https://www.linkedin.com/in/ci-bot)"
}

test_no_value_writes_the_flagged_placeholder() {
    expect "no env, no tty -> placeholder" "$STR_LINKEDIN_PLACEHOLDER_URL" "$(linkedin_for "")"
}

test_piped_stdin_is_never_consumed() {
    local str_got
    str_got="$(printf 'https://www.linkedin.com/in/piped\n' | BLUEPRINTX_STDIN_ANSWERS=1 bash -c '
        source "$1/bin/lib/common.sh"; source "$1/bin/lib/scaffold_readme.sh"
        unset LINKEDIN_URL; resolve_linkedin_url >/dev/null 2>&1; printf "%s" "$LINKEDIN_URL"' _ "$REPO_ROOT")"
    expect "a piped answer feed is not eaten by the LinkedIn step" "$STR_LINKEDIN_PLACEHOLDER_URL" "$str_got"
}

test_archetype_blocks_follow_the_skeleton() {
    local path_lib path_svc
    path_lib="$(mktemp)"
    path_svc="$(mktemp)"
    LINKEDIN_URL=https://www.linkedin.com/in/ci-bot render_python_readme lib-minimal "$path_lib"
    LINKEDIN_URL=https://www.linkedin.com/in/ci-bot render_python_readme ddd-service-native-db "$path_svc"
    expect "library README has Public API" "1" "$(grep -c '^## Public API$' "$path_lib")"
    expect "library README has no Configuration" "0" "$(grep -c '^## Configuration$' "$path_lib")"
    expect "service README has Configuration" "1" "$(grep -c '^## Configuration$' "$path_svc")"
    expect "service README has no Public API" "0" "$(grep -c '^## Public API$' "$path_svc")"
    expect "no archetype marker left in the output" "0" "$(cat "$path_lib" "$path_svc" | grep -c 'only:' || true)"
    rm -f "$path_lib" "$path_svc"
}

test_rendered_readme_passes_the_gate_only_with_a_real_linkedin() {
    local path_ok path_bad
    path_ok="$(mktemp)"
    path_bad="$(mktemp)"
    LINKEDIN_URL=https://www.linkedin.com/in/ci-bot render_python_readme lib-minimal "$path_ok"
    LINKEDIN_URL="$STR_LINKEDIN_PLACEHOLDER_URL" render_python_readme lib-minimal "$path_bad"
    expect "rendered with a real LinkedIn URL passes" "0" "$(bash "$GATE" "$path_ok" >/dev/null 2>&1 && echo 0 || echo 1)"
    expect "rendered with the placeholder fails" "1" "$(bash "$GATE" "$path_bad" >/dev/null 2>&1 && echo 0 || echo 1)"
    rm -f "$path_ok" "$path_bad"
}

test_skeleton_without_archetype_is_refused() {
    local path_root str_got
    path_root="$(mktemp -d)"
    mkdir -p "$path_root/templates/fake"
    printf 'language=python\n' >"$path_root/templates/fake/skeleton.meta"
    str_got="$(BLUEPRINTX_ROOT="$path_root" GITHUB_USERNAME=x scaffold_render_readme fake /dev/null /dev/null 2>&1 && echo ok || echo refused)"
    rm -rf "$path_root"
    expect "meta without readme_archetype is refused" "refused" "${str_got##*$'\n'}"
}

test_linkedin_destination_is_escaped() {
    local path_out
    path_out="$(mktemp)"
    LINKEDIN_URL="https://www.linkedin.com/in/a(b) c" render_python_readme ddd-service-native-db "$path_out"
    grep -qF '[LinkedIn](https://www.linkedin.com/in/a%28b%29%20c)' "$path_out" \
        || expect "parenthesis and space in LINKEDIN_URL are percent-encoded" "encoded" "raw"
    rm -f "$path_out"
}

test_rendered_readme_carries_absolute_urls_and_footer() {
    local path_out str_raw="https://raw.githubusercontent.com/ci-bot/acme/main"
    path_out="$(mktemp)"
    LINKEDIN_URL=https://www.linkedin.com/in/ci-bot render_python_readme lib-minimal "$path_out"
    expect "logo is an absolute raw URL at width 200" "1" \
        "$(grep -cF "img src=\"$str_raw/assets/logo_lorem_ipsum.png\" width=\"200\"" "$path_out")"
    expect "coverage badge is an absolute raw URL" "1" "$(grep -cF "(${str_raw%/main}/badges/coverage.svg)" "$path_out")"
    expect "no relative image left" "0" "$(grep -cE '(src="|\]\()(\./|assets/|coverage)' "$path_out" || true)"
    expect "footer names the tier" "1" "$(grep -cF '<sub>Generated from the lib-minimal template via [BlueprintX](https://github.com/guilhermegor/blueprintx).' "$path_out")"
    expect "library README has Documentation" "1" "$(grep -c '^## Documentation$' "$path_out")"
    expect "library README has the pypi badge" "1" "$(grep -c 'img.shields.io/pypi/v/acme' "$path_out")"
    rm -f "$path_out"
}

test_library_badge_row_is_live_and_not_duplicated() {
    local path_out str_scaffold="$REPO_ROOT/bin/scaffold/python_lib_minimal.sh"
    path_out="$(mktemp)"
    LINKEDIN_URL=https://www.linkedin.com/in/ci-bot render_python_readme lib-minimal "$path_out"
    expect "scaffold script no longer appends badges" "0" \
        "$(grep -c 'add_library_badges\|snyk\.io\|pepy\.tech' "$str_scaffold" || true)"
    expect "the PyPI version badge is emitted once" "1" "$(grep -c 'img.shields.io/pypi/v/' "$path_out")"
    expect "no Snyk badge" "0" "$(grep -c 'snyk' "$path_out" || true)"
    expect "one shields downloads badge" "1" "$({ grep -oF 'img.shields.io/pepy/dt/acme' "$path_out" || true; } | wc -l | tr -d '[:space:]')"
    expect "no pepy-hosted image badge" "0" "$(grep -cE 'static\.pepy\.tech|pepy\.tech/badge' "$path_out" || true)"
    expect "type-checked text is escaped for shields" "1" "$(grep -cF 'badge/type--checked-mypy-blue' "$path_out")"
    expect "linting separator is escaped for shields" "1" "$(grep -cF 'badge/linting-ruff_%7C_codespell-blue' "$path_out")"
    expect "docs badge links the project docs site" "1" \
        "$(grep -cF 'badge/docs-latest-blue.svg)](https://ci-bot.github.io/acme/)' "$path_out")"
    rm -f "$path_out"
}

test_real_scaffold_readme_has_one_pypi_badge_and_no_dead_ones() {
    local path_work path_readme
    path_work="$(mktemp -d)"
    path_readme="$path_work/ci-scaffold/README.md"
    LINKEDIN_URL=https://www.linkedin.com/in/ci-bot GITHUB_USERNAME=ci-bot \
        bash "$REPO_ROOT/bin/scaffold/python_lib_minimal.sh" "$path_work" ci-scaffold "CI badge check" 0.0.1 \
        < <(printf '\n%.0s' {1..100}) >/dev/null 2>&1 || true
    expect "the real scaffold wrote a README" "1" "$([ -f "$path_readme" ] && echo 1 || echo 0)"
    expect "scaffolded README has the PyPI badge once" "1" "$(grep -c 'img.shields.io/pypi/v/' "$path_readme" || true)"
    expect "scaffolded README has no Snyk badge" "0" "$(grep -c 'snyk' "$path_readme" || true)"
    expect "scaffolded README has one shields downloads badge" "1" "$({ grep -oF 'img.shields.io/pepy/dt/ci-scaffold' "$path_readme" || true; } | wc -l | tr -d '[:space:]')"
    expect "scaffolded README has no pepy-hosted image badge" "0" "$(grep -cE 'static\.pepy\.tech|pepy\.tech/badge' "$path_readme" || true)"
    rm -rf "$path_work"
}

test_ts_lib_readme_has_one_npm_downloads_badge() {
    local path_out int_render=0
    path_out="$(mktemp)"
    (
        BLUEPRINTX_ROOT="$REPO_ROOT"
        PROJECT_NAME=acme PROJECT_DESCRIPTION="A test project." PROJECT_DISPLAY_NAME=Acme
        GITHUB_USERNAME=ci-bot LICENSE_CHOICE=MIT LINKEDIN_URL=https://www.linkedin.com/in/ci-bot
        scaffold_render_readme ts-lib "$REPO_ROOT/templates/ts-lib/README.md" "$path_out" >/dev/null
    ) || int_render=$?
    expect "ts-lib README renders" "0" "$int_render"
    expect "ts-lib README has one npm downloads badge" "1" "$({ grep -oF 'img.shields.io/npm/d18m/acme' "$path_out" || true; } | wc -l | tr -d '[:space:]')"
    expect "ts-lib downloads badge links the npm page" "1" \
        "$(grep -cF '[![Downloads](https://img.shields.io/npm/d18m/acme)](https://www.npmjs.com/package/acme)' "$path_out")"
    rm -f "$path_out"
}

test_service_readme_has_no_documentation_or_pypi() {
    local path_out
    path_out="$(mktemp)"
    LINKEDIN_URL=https://www.linkedin.com/in/ci-bot render_python_readme ddd-service-native-db "$path_out"
    expect "service README has no Documentation section" "0" "$(grep -c '^## Documentation$' "$path_out" || true)"
    expect "service README has no pypi badge" "0" "$(grep -c 'pypi' "$path_out" || true)"
    expect "service README has no downloads badge" "0" "$(grep -c 'shields.io/pepy/\|shields.io/npm/d' "$path_out" || true)"
    rm -f "$path_out"
}

render_ptbr_readme() {
    local str_description="$1" path_out="$2"
    (
        BLUEPRINTX_ROOT="$REPO_ROOT"
        PROJECT_NAME=acme PROJECT_DESCRIPTION="$str_description" PROJECT_DISPLAY_NAME=Acme
        GITHUB_USERNAME=ci-bot LICENSE_CHOICE=MIT LINKEDIN_URL="https://www.linkedin.com/in/ci-bot"
        scaffold_render_readme lib-minimal "$REPO_ROOT/templates/lib-minimal/README.pt-BR.md" "$path_out" >/dev/null 2>&1 </dev/null
    )
}

test_ptbr_readme_refuses_an_english_description() {
    local path_out int_rc=0 str_err
    path_out="$(mktemp)"
    str_err="$(
        BLUEPRINTX_ROOT="$REPO_ROOT"
        PROJECT_NAME=acme PROJECT_DESCRIPTION="This library is a tool that can parse the files. It is not for the users, and it will be fast." PROJECT_DISPLAY_NAME=Acme
        GITHUB_USERNAME=ci-bot LICENSE_CHOICE=MIT LINKEDIN_URL="https://www.linkedin.com/in/ci-bot"
        scaffold_render_readme lib-minimal "$REPO_ROOT/templates/lib-minimal/README.pt-BR.md" "$path_out" 2>&1 >/dev/null </dev/null
    )" || int_rc=$?
    expect "English description is refused for a pt-BR README" "1" "$int_rc"
    expect "refusal names the pt-BR requirement" "1" "$(grep -c 'other than pt-BR' <<<"$str_err" || true)"
    rm -f "$path_out"
}

test_ptbr_readme_reports_a_checker_that_cannot_run() {
    local path_out int_rc=0 str_err
    path_out="$(mktemp)"
    str_err="$(
        BLUEPRINTX_ROOT="$REPO_ROOT"
        PROJECT_NAME=acme PROJECT_DESCRIPTION="Texto qualquer." PROJECT_DISPLAY_NAME=Acme
        GITHUB_USERNAME=ci-bot LICENSE_CHOICE=MIT LINKEDIN_URL="https://www.linkedin.com/in/ci-bot"
        description_reads_as_ptbr() { return 127; }
        scaffold_render_readme lib-minimal "$REPO_ROOT/templates/lib-minimal/README.pt-BR.md" "$path_out" 2>&1 >/dev/null </dev/null
    )" || int_rc=$?
    expect "a checker that cannot run fails the render" "1" "$int_rc"
    expect "that failure is told apart from a language refusal" "1" "$(grep -c 'could not run' <<<"$str_err" || true)"
    rm -f "$path_out"
}

test_ptbr_readme_keeps_a_short_ptbr_description() {
    local path_out str_description="Utilitários para CNPJ"
    path_out="$(mktemp)"
    render_ptbr_readme "$str_description" "$path_out"
    expect "short pt-BR description is rendered" "1" "$(grep -cxF "$str_description" "$path_out" || true)"
    rm -f "$path_out"
}

test_ptbr_readme_refuses_an_empty_answer_at_eof() {
    local path_out int_rc=0
    path_out="$(mktemp)"
    (
        BLUEPRINTX_ROOT="$REPO_ROOT" BLUEPRINTX_STDIN_ANSWERS=1
        PROJECT_NAME=acme PROJECT_DESCRIPTION="This library is a tool that can parse the files. It is not for the users." PROJECT_DISPLAY_NAME=Acme
        GITHUB_USERNAME=ci-bot LICENSE_CHOICE=MIT LINKEDIN_URL="https://www.linkedin.com/in/ci-bot"
        scaffold_render_readme lib-minimal "$REPO_ROOT/templates/lib-minimal/README.pt-BR.md" "$path_out" >/dev/null 2>&1 </dev/null
    ) || int_rc=$?
    expect "an empty answer at EOF is refused" "1" "$int_rc"
    rm -f "$path_out"
}

test_ptbr_readme_keeps_a_ptbr_description() {
    local path_out str_description="Esta biblioteca é uma ferramenta que lê os arquivos. Ela não é para os usuários, e será rápida."
    path_out="$(mktemp)"
    render_ptbr_readme "$str_description" "$path_out"
    expect "pt-BR description is rendered unchanged" "1" "$(grep -cxF "$str_description" "$path_out" || true)"
    rm -f "$path_out"
}

test_ptbr_readme_reprompts_in_interactive_mode() {
    local path_out str_ptbr="Esta biblioteca é uma ferramenta que lê os arquivos. Ela não é para os usuários."
    path_out="$(mktemp)"
    (
        BLUEPRINTX_ROOT="$REPO_ROOT" BLUEPRINTX_STDIN_ANSWERS=1
        PROJECT_NAME=acme PROJECT_DESCRIPTION="This library is a tool that can parse the files. It is not for the users." PROJECT_DISPLAY_NAME=Acme
        GITHUB_USERNAME=ci-bot LICENSE_CHOICE=MIT LINKEDIN_URL="https://www.linkedin.com/in/ci-bot"
        scaffold_render_readme lib-minimal "$REPO_ROOT/templates/lib-minimal/README.pt-BR.md" "$path_out" >/dev/null 2>&1 <<<"$str_ptbr"
    )
    expect "interactive mode takes the replacement pt-BR description" "1" "$(grep -cxF "$str_ptbr" "$path_out" || true)"
    rm -f "$path_out"
}

main() {
    local str_test
    for str_test in $(declare -F | awk '$3 ~ /^test_/ { print $3 }'); do
        "$str_test"
    done
    if [ "$int_failures" -gt 0 ]; then
        print_status "error" "$int_failures scaffold_readme case(s) failed"
        exit 1
    fi
    print_status "success" "scaffold_readme resolves LinkedIn and filters archetype blocks"
}

main "$@"
