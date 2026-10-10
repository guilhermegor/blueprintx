#!/bin/bash
# Should-fail regression tests for bin/ci/check_pr_template.sh (blueprintx#587).
#
# The dangerous direction is a FALSE PASS: a body missing a heading, holding an empty
# section, naming a heading only in prose, or leaving the template's text in place must
# never reach "matches the template layout". Each rule therefore has a violating case that
# must fail NAMING the element, and a legitimate case that must pass — a gate that only
# proves one direction is either noise or blind.
#
# The cases run against the REAL .github/PULL_REQUEST_TEMPLATE.md, so a template edit that
# the gate cannot follow fails here rather than in somebody's PR.
#
# Usage: bash tests/test_check_pr_template.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

GATE="$REPO_ROOT/bin/ci/check_pr_template.sh"
int_failures=0

# A body that satisfies every mandatory element, with the conditional ones left out.
good_body() {
    cat <<'EOF'
## Description
**What**: Adds a layout gate for PR bodies.
**Why**: Only five headings were checked.
**How**: bin/ci/check_pr_template.sh derives its contract from the template.

---

## Changes Made
**Added**:
- bin/ci/check_pr_template.sh.

---

## Testing
### Manual Testing
- Ran it against this body.

### Automated Testing
- tests/test_check_pr_template.sh.

---

## Documentation
- CONTRIBUTING.md: states which fields are mandatory.

---

## Additional Notes
**Reviewer Focus**:
- The mandatory/conditional split.
EOF
}

expect_gate() {
    # $1 = description, $2 = body text, $3 = pass|fail, $4 = optional needle for fail,
    # $5 = optional author. ⚠️ The needle is what makes a failing case mean anything: a
    # non-zero exit alone does not prove the intended rule fired.
    local str_desc="$1" str_body="$2" str_want="$3" str_needle="${4:-}" str_author="${5:-}"
    local str_got="pass" str_out path_body
    path_body="$(mktemp)"
    printf '%s\n' "$str_body" >"$path_body"
    str_out="$(bash "$GATE" --body-file "$path_body" ${str_author:+--author "$str_author"} 2>&1)" || str_got="fail"
    rm -f "$path_body"
    if [ "$str_got" != "$str_want" ]; then
        print_status "error" "$str_desc -> $str_got (expected $str_want)"
        int_failures=$((int_failures + 1))
        return
    fi
    if [ -n "$str_needle" ] && ! printf '%s' "$str_out" | grep -qF -- "$str_needle"; then
        print_status "error" "$str_desc -> failed, but never said '$str_needle'"
        int_failures=$((int_failures + 1))
    fi
}

without() {
    # Prints good_body minus every line from the one matching $1 up to (not including) the
    # next line matching $2.
    good_body | awk -v from="$1" -v to="$2" '
        $0 ~ from { skipping = 1; next }
        skipping && $0 ~ to { skipping = 0 }
        !skipping { print }'
}

with_not_applicable() {
    # stdin: a body. Adds **Not Applicable**: (+ optional $1 line) right after the Automated
    # Testing content, where the template puts it: fields are keyed by section, so placement
    # matters.
    awk -v txt="$1" '
        { print }
        /^- tests\/test_check_pr_template.sh/ {
            print ""; print "**Not Applicable**:"; if (txt != "") print txt
        }'
}

test_complete_body_passes() {
    expect_gate "complete body, conditional fields omitted" "$(good_body)" pass
}

test_unfilled_template_fails() {
    expect_gate "the template itself, unfilled" \
        "$(cat "$REPO_ROOT/.github/PULL_REQUEST_TEMPLATE.md")" fail "still the template text"
}

test_missing_heading_fails_naming_it() {
    expect_gate "no ## Documentation" "$(without '^## Documentation' '^## Additional')" fail \
        '`## Documentation` heading: missing'
}

test_heading_only_in_prose_does_not_count() {
    local str_body
    str_body="$(without '^## Testing' '^## Documentation')"
    expect_gate "Testing mentioned in prose, no heading" \
        "$str_body"$'\n'"I did some Testing by hand." fail '`## Testing` heading: missing'
}

test_heading_text_mid_line_does_not_count() {
    local str_body
    str_body="$(without '^## Testing' '^## Documentation')"
    expect_gate "'## Testing' typed mid-sentence, no heading line" \
        "$str_body"$'\nSee the ## Testing section of the old PR.' fail '`## Testing` heading: missing'
}

test_heading_inside_code_fence_does_not_count() {
    local str_body
    str_body="$(without '^## Documentation' '^## Additional')"
    expect_gate "heading only inside a fenced block" \
        "$str_body"$'\n```\n## Documentation\n- fake\n```' fail '`## Documentation` heading: missing'
}

test_heading_inside_html_comment_does_not_count() {
    local str_body
    str_body="$(without '^## Documentation' '^## Additional')"
    expect_gate "heading only inside an HTML comment" \
        "$str_body"$'\n<!--\n## Documentation\n- fake\n-->' fail '`## Documentation` heading: missing'
}

test_empty_section_fails() {
    local str_body
    str_body="$(good_body | awk '/^- CONTRIBUTING.md/ { next } { print }')"
    expect_gate "## Documentation with nothing under it" "$str_body" fail \
        '`## Documentation` heading: present but empty'
}

test_empty_field_fails() {
    local str_body
    str_body="$(good_body | sed 's/^\*\*Why\*\*:.*/**Why**:/')"
    expect_gate "**Why**: with no text" "$str_body" fail '`**Why**:` field: present but empty'
}

test_missing_testing_subsection_needs_not_applicable() {
    local str_body
    str_body="$(without '^### Manual Testing' '^### Automated')"
    expect_gate "no Manual Testing, no Not Applicable" "$str_body" fail \
        '`### Manual Testing` heading: missing'
}

test_not_applicable_excuses_a_missing_testing_subsection() {
    local str_body
    str_body="$(without '^### Manual Testing' '^### Automated' | with_not_applicable '- Documentation-only change.')"
    expect_gate "no Manual Testing, but Not Applicable explains it" "$str_body" pass
}

test_empty_not_applicable_does_not_excuse() {
    local str_body
    str_body="$(without '^### Manual Testing' '^### Automated' | with_not_applicable '')"
    expect_gate "Not Applicable present but empty" "$str_body" fail '`### Manual Testing` heading'
}

test_change_group_needs_one_filled_member() {
    local str_body
    str_body="$(without '^\*\*Added\*\*' '^---')"
    expect_gate "Changes Made with none of Added/Updated/Fixed" "$str_body" fail \
        'none of Added, Updated or Fixed is filled in'
}

test_a_lone_fixed_satisfies_the_change_group() {
    local str_body
    str_body="$(good_body | sed 's/^\*\*Added\*\*:/**Fixed**:/')"
    expect_gate "only Fixed under Changes Made" "$str_body" pass
}

test_optional_fields_may_be_present_and_filled() {
    local str_body
    str_body="$(good_body)"$'\n**Dependencies**:\n- Depends on #12.\n\n**Follow-up**:\n- Wire it as required.'
    expect_gate "Dependencies and Follow-up filled" "$str_body" pass
}

test_optional_field_left_as_template_text_fails() {
    local str_body
    str_body="$(good_body)"$'\n**Follow-up**:\n- Tech debt: [Brief note].'
    expect_gate "Follow-up left as the template placeholder" "$str_body" fail \
        '`**Follow-up**:` field: still the template text'
}

test_automated_testing_left_as_template_text_fails() {
    # blueprintx#672: the old parser credited **Not Applicable** text to the open ### too, so
    # an Automated Testing left verbatim stopped matching the template and counted as filled.
    local str_body str_tpl
    str_tpl="$(awk '/^### Automated Testing/ { f = 1; next } /^\*\*Not Applicable/ { f = 0 } f' \
        "$REPO_ROOT/.github/PULL_REQUEST_TEMPLATE.md")"
    str_body="$(good_body | awk -v tpl="$str_tpl" '
        /^- tests\/test_check_pr_template.sh/ { print tpl; next } { print }')"
    expect_gate "Automated Testing left exactly as the template, no Not Applicable" "$str_body" fail \
        '`### Automated Testing` heading: still the template text'
}

test_structural_label_kept_with_real_bullets_passes() {
    # The template expects `- **CI (this PR)**:` to stay, followed by real content; a label
    # line is structure, not filler, so keeping it verbatim must not read as a placeholder.
    local str_body
    str_body="$(good_body | sed 's/^- tests\/test_check_pr_template.sh\./- **CI (this PR)**:\n    - `pr-template`: passes on this body./')"
    expect_gate "Automated Testing keeps the CI (this PR) label above real bullets" "$str_body" pass
}

test_structural_label_alone_is_empty_not_filled() {
    local str_body
    str_body="$(good_body | sed 's/^- tests\/test_check_pr_template.sh\./- **CI (this PR)**:/')"
    expect_gate "Automated Testing with only the label" "$str_body" fail \
        '`### Automated Testing` heading: present but empty'
}

test_optional_label_kept_with_nothing_under_it_fails() {
    local str_body
    str_body="$(good_body)"$'\n**Dependencies**:'
    expect_gate "Dependencies label kept, no content" "$str_body" fail \
        '`**Dependencies**:` field: present but empty'
}

test_longer_fence_is_not_closed_by_a_shorter_one() {
    local str_body
    str_body="$(without '^## Documentation' '^## Additional')"
    expect_gate "heading inside a 4-backtick fence holding a 3-backtick line" \
        "$str_body"$'\n````\n```\n## Documentation\n- fake\n```\n````' fail \
        '`## Documentation` heading: missing'
}

test_added_under_the_wrong_section_does_not_count() {
    local str_body
    str_body="$(good_body | sed 's/^\*\*Added\*\*:/Prose only, no field./')"
    str_body="$str_body"$'\n**Added**:\n- misplaced under Additional Notes.'
    expect_gate "**Added** only under Additional Notes" "$str_body" fail \
        'none of Added, Updated or Fixed is filled in'
}

test_one_leftover_placeholder_line_fails() {
    local str_body
    str_body="$(good_body | sed 's/^- bin\/ci\/check_pr_template.sh\./&\n- New template file: [Path]./')"
    expect_gate "Added with a real line and one placeholder line left" "$str_body" fail \
        '`**Added**:` field: still the template text'
}

test_optional_field_with_placeholder_plus_real_line_fails() {
    local str_body
    str_body="$(good_body)"$'\n**Follow-up**:\n- Tech debt: [Brief note].\n- Wire it as required.'
    expect_gate "Follow-up: placeholder kept beside a real line" "$str_body" fail \
        '`**Follow-up**:` field: still the template text'
}

test_bold_label_variants_are_accepted() {
    local str_body
    str_body="$(good_body | sed -e 's/^\*\*What\*\*:/**What:**/' -e 's/^\*\*Why\*\*:/**Why** :/')"
    expect_gate "**What:** and **Why** : render like **What**:" "$str_body" pass
}

test_tilde_fence_hides_headings() {
    local str_body
    str_body="$(without '^## Documentation' '^## Additional')"
    expect_gate "heading only inside a ~~~ fence" \
        "$str_body"$'\n~~~\n## Documentation\n- fake\n~~~' fail '`## Documentation` heading: missing'
}

test_comment_opener_inside_a_fence_does_not_swallow_the_body() {
    local str_body
    str_body="$(good_body | sed 's/^\*\*How\*\*:.*/&\n```html\n<!-- a snippet\n```/')"
    expect_gate "a literal <!-- inside a fenced block" "$str_body" pass
}

test_thematic_break_inside_a_field_keeps_its_content() {
    local str_body
    str_body="$(good_body | sed 's/^\*\*Added\*\*:/&\n---/')"
    expect_gate "--- between **Added**: and its list" "$str_body" pass
}

test_indented_heading_is_reported_as_placement() {
    local str_body
    str_body="$(good_body | sed 's/^## Documentation/  ## Documentation/')"
    expect_gate "## Documentation indented" "$str_body" fail 'not found at the start of a line'
}

test_empty_body_fails_for_a_human() {
    expect_gate "empty body, human author" "" fail '`## Description` heading: missing' someone
}

test_bot_author_is_exempt() {
    expect_gate "empty body, dependabot" "" pass "skipped" 'dependabot[bot]'
}

test_unreadable_body_is_not_a_pass() {
    local str_got="pass"
    bash "$GATE" --body-file /nonexistent/body.md >/dev/null 2>&1 || str_got="fail"
    if [ "$str_got" != "fail" ]; then
        print_status "error" "unreadable body file -> pass (expected fail)"
        int_failures=$((int_failures + 1))
    fi
}

test_stale_registry_is_reported() {
    local path_tpl path_body str_out str_got="pass"
    path_tpl="$(mktemp)"
    path_body="$(mktemp)"
    grep -v 'Dependencies' "$REPO_ROOT/.github/PULL_REQUEST_TEMPLATE.md" >"$path_tpl"
    good_body >"$path_body"
    str_out="$(bash "$GATE" --template "$path_tpl" --body-file "$path_body" 2>&1)" || str_got="fail"
    rm -f "$path_tpl" "$path_body"
    if [ "$str_got" != "fail" ] || ! printf '%s' "$str_out" | grep -qF "registry is stale"; then
        print_status "error" "template without Dependencies -> $str_got, or never said 'registry is stale'"
        int_failures=$((int_failures + 1))
    fi
}

main() {
    local str_test
    for str_test in $(declare -F | awk '$3 ~ /^test_/ { print $3 }'); do
        "$str_test"
    done
    if [ "$int_failures" -gt 0 ]; then
        print_status "error" "$int_failures check_pr_template case(s) failed"
        exit 1
    fi
    print_status "success" "check_pr_template should-fail cases all behaved"
}

main "$@"
