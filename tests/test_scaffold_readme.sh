#!/bin/bash

set -euo pipefail

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
    expect "coverage badge is an absolute raw URL" "1" "$(grep -cF "($str_raw/coverage.svg)" "$path_out")"
    expect "no relative image left" "0" "$(grep -cE '(src="|\]\()(\./|assets/|coverage)' "$path_out" || true)"
    expect "footer names the tier" "1" "$(grep -c '^<sub>Generated from the lib-minimal template via BlueprintX' "$path_out")"
    expect "library README has Documentation" "1" "$(grep -c '^## Documentation$' "$path_out")"
    expect "library README has the pypi badge" "1" "$(grep -c 'img.shields.io/pypi/v/acme' "$path_out")"
    rm -f "$path_out"
}

test_service_readme_has_no_documentation_or_pypi() {
    local path_out
    path_out="$(mktemp)"
    LINKEDIN_URL=https://www.linkedin.com/in/ci-bot render_python_readme ddd-service-native-db "$path_out"
    expect "service README has no Documentation section" "0" "$(grep -c '^## Documentation$' "$path_out" || true)"
    expect "service README has no pypi badge" "0" "$(grep -c 'pypi' "$path_out" || true)"
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
