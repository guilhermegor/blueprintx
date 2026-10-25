#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
# shellcheck source=bin/lib/scaffold_readme.sh
source "$REPO_ROOT/bin/lib/scaffold_readme.sh"

GATE="$REPO_ROOT/templates/common/bin/check_readme_structure.sh"
int_failures=0

good_readme() {
    good_readme_head
    good_readme_tail
}

good_readme_head() {
    cat <<'EOF'
<!-- readme-archetype: library -->
# acme-dates

<p align="center"><img src="docs/assets/logo.png" alt="acme-dates logo" width="160"></p>

![CI](https://github.com/guilhermegor/acme-dates/actions/workflows/tests.yaml/badge.svg)

<!-- slug: overview -->
## Overview

Business-day arithmetic.

<!-- slug: features -->
## Features

- Business-day arithmetic.

<!-- slug: documentation -->
## Documentation

Docs at https://guilhermegor.github.io/acme-dates/; run `poe docs_serve`.

<!-- slug: getting-started -->
## Getting Started

<!-- slug: install -->
### Install

```bash
pip install acme-dates
```

<!-- slug: usage -->
### Usage

Call `add_business_days`.

<!-- slug: project-structure -->
## Estrutura do projeto

`src/` holds the package.

<!-- slug: development -->
## Development

`poetry run pytest`.
EOF
}

good_readme_tail() {
    cat <<'EOF'

<!-- slug: public-api -->
## Public API

`add_business_days`.

<!-- slug: publishing -->
## Publishing

Cut a release from the Release action.

<!-- slug: contributing -->
## Contributing

See CONTRIBUTING.md.

<!-- slug: license -->
## License

MIT.

<!-- slug: authors -->
## Authors

- Guilherme Rodrigues — [GitHub](https://github.com/guilhermegor) · [LinkedIn](https://www.linkedin.com/in/guilhermegor)

<!-- slug: useful-links -->
## Useful Links

- [Issue tracker](https://github.com/guilhermegor/acme-dates/issues)

---

<sub>Generated from the lib-minimal template via BlueprintX.</sub>
EOF
}

expect_gate() {
    local str_desc="$1" str_body="$2" str_want="$3" str_needle="${4:-}" str_flag="${5:-}"
    local str_got="pass" str_out path_body
    path_body="$(mktemp)"
    printf '%s\n' "$str_body" >"$path_body"
    str_out="$(bash "$GATE" ${str_flag:+"$str_flag"} "$path_body" 2>&1)" || str_got="fail"
    rm -f "$path_body"
    if [ "$str_got" != "$str_want" ]; then
        print_status "error" "$str_desc -> $str_got (expected $str_want): $str_out"
        int_failures=$((int_failures + 1))
        return
    fi
    if [ -n "$str_needle" ] && ! printf '%s' "$str_out" | grep -qF -- "$str_needle"; then
        print_status "error" "$str_desc -> failed, but never said '$str_needle': $str_out"
        int_failures=$((int_failures + 1))
    fi
}

without_slug() {
    good_readme | grep -vF "<!-- slug: $1 -->"
}

test_complete_readme_passes() {
    expect_gate "complete README, translated heading, logo under the H1" "$(good_readme)" pass
}

test_missing_archetype_marker_fails() {
    expect_gate "no archetype marker" "$(good_readme | sed 1d)" fail "no '<!-- readme-archetype"
}

test_unknown_archetype_fails() {
    expect_gate "archetype outside the list" \
        "$(good_readme | sed '1s/library/monolith/')" fail "unknown archetype 'monolith'"
}

test_missing_core_slug_fails_naming_it() {
    local str_slug
    for str_slug in overview getting-started install usage project-structure development \
        contributing license authors useful-links; do
        expect_gate "no '$str_slug' slug" "$(without_slug "$str_slug")" fail "missing section '$str_slug'"
    done
}

test_missing_archetype_slug_fails() {
    expect_gate "library without public-api" "$(without_slug public-api)" fail "missing section 'public-api'"
    expect_gate "library without publishing" "$(without_slug publishing)" fail "missing section 'publishing'"
}

test_library_requires_documentation() {
    expect_gate "library without documentation" "$(without_slug documentation)" fail "missing section 'documentation'"
}

test_documentation_must_follow_overview() {
    local str_body
    str_body="$(good_readme | sed 's/slug: documentation/slug: TMP/; s/slug: development/slug: documentation/; s/slug: TMP/slug: development/')"
    expect_gate "documentation after development" "$str_body" fail "is out of order"
}

test_features_is_optional_but_ordered() {
    local str_body
    expect_gate "README without features" "$(without_slug features)" pass
    str_body="$(good_readme | sed 's/slug: features/slug: TMP/; s/slug: documentation/slug: features/; s/slug: TMP/slug: documentation/')"
    expect_gate "features after documentation" "$str_body" fail "is out of order"
    str_body="$(good_readme | sed 's/slug: features/slug: TMP/; s/slug: development/slug: features/; s/slug: TMP/slug: development/')"
    expect_gate "features after development" "$str_body" fail "is out of order"
}

test_footer_without_heading_is_optional() {
    expect_gate "README with no footer" "$(good_readme | sed '/^---$/,$d')" pass
}

test_other_archetype_slug_is_required() {
    expect_gate "cli README with library sections but no releasing" \
        "$(good_readme | sed '1s/library/cli/')" fail "missing section 'releasing'"
}

test_out_of_order_fails() {
    local str_body
    str_body="$(good_readme | sed 's/slug: license/slug: TMP/; s/slug: contributing/slug: license/; s/slug: TMP/slug: contributing/')"
    expect_gate "license before contributing" "$str_body" fail "is out of order"
}

test_slug_marker_without_heading_text_match_passes() {
    expect_gate "Portuguese heading keeps its slug" \
        "$(good_readme | sed 's/^## Development/## Desenvolvimento/')" pass
}

test_emoji_heading_fails() {
    expect_gate "rocket emoji in an H2" "$(good_readme | sed 's/^## Overview/## 🚀 Overview/')" fail \
        "heading carries an emoji or icon"
    expect_gate "variation-selector emoji in an H3" "$(good_readme | sed 's/^### Usage/### ⚙️ Usage/')" fail \
        "heading carries an emoji or icon"
    expect_gate "sparkles in the H1" "$(good_readme | sed 's/^# acme-dates/# ✨ acme-dates/')" fail \
        "heading carries an emoji or icon"
}

test_image_in_heading_fails() {
    local str_img='<img src="logo.png" align="right" width="200">'
    expect_gate "<img> inside the H1" "$(good_readme | sed "s|^# acme-dates|# acme-dates $str_img|")" fail \
        "heading carries an image"
    expect_gate "markdown image inside an H2" \
        "$(good_readme | sed 's|^## Overview|## Overview ![x](a.png)|')" fail "heading carries an image"
    expect_gate "<picture> inside an H2" \
        "$(good_readme | sed 's|^## Overview|## Overview <picture>|')" fail "heading carries an image"
}

test_emoji_outside_headings_is_allowed() {
    expect_gate "emoji in a paragraph" "$(good_readme | sed 's/^Business-day arithmetic./Business-day arithmetic 🚀/')" pass
}

test_heading_inside_code_fence_is_ignored() {
    expect_gate "emoji heading only inside a fenced block" \
        "$(good_readme)"$'\n```\n## 🚀 not a heading\n```' pass
}

test_author_without_linkedin_fails() {
    expect_gate "author with GitHub only" \
        "$(good_readme | sed 's# · \[LinkedIn\](https://www.linkedin.com/in/guilhermegor)##')" fail \
        "author without a linkedin.com/in/<handle> link"
}

test_author_without_github_fails() {
    expect_gate "author with LinkedIn only" \
        "$(good_readme | sed 's#\[GitHub\](https://github.com/guilhermegor) · ##')" fail \
        "author without a github.com/<user> link"
}

test_every_author_needs_both_links() {
    expect_gate "second author lacks LinkedIn" \
        "$(good_readme | sed 's#^- Guilherme.*#&\n- Ada — [GitHub](https://github.com/ada)#')" fail \
        "author without a linkedin.com/in/<handle> link"
}

test_empty_authors_fails() {
    expect_gate "Authors lists no one" "$(good_readme | sed '/^- Guilherme/d')" fail "lists no one"
}

test_linkedin_placeholder_fails() {
    expect_gate "scaffold placeholder left in place" \
        "$(good_readme | sed 's#linkedin.com/in/guilhermegor#linkedin.com/in/your-linkedin-handle#')" fail \
        "LinkedIn link is the scaffold placeholder"
}

test_unrendered_placeholder_fails_outside_template_mode() {
    expect_gate "\${PROJECT_NAME} left in a generated README" \
        "$(good_readme | sed 's/^# acme-dates/# ${PROJECT_NAME}/')" fail "unfilled placeholder"
    expect_gate "same README under --template" \
        "$(good_readme | sed 's/^# acme-dates/# ${PROJECT_NAME}/')" pass "" --template
}

test_linkedin_placeholder_var_only_in_template_mode() {
    local str_body
    str_body="$(good_readme | sed 's#https://www.linkedin.com/in/guilhermegor#${LINKEDIN_URL}#')"
    expect_gate "\${LINKEDIN_URL} outside --template" "$str_body" fail "author without a linkedin.com/in/<handle> link"
    expect_gate "\${LINKEDIN_URL} under --template" "$str_body" pass "" --template
}

test_canonical_template_passes_for_every_archetype() {
    local str_archetype path_rendered str_out str_got
    for str_archetype in $(bash "$GATE" --list-archetypes); do
        path_rendered="$(mktemp)"
        scaffold_filter_archetype_blocks "$str_archetype" <"$REPO_ROOT/templates/common/README.template.md" \
            | sed "s/\${README_ARCHETYPE}/$str_archetype/" >"$path_rendered"
        str_got="pass"
        str_out="$(bash "$GATE" --template "$path_rendered" 2>&1)" || str_got="fail"
        rm -f "$path_rendered"
        if [ "$str_got" != "pass" ]; then
            print_status "error" "canonical template, archetype $str_archetype -> $str_out"
            int_failures=$((int_failures + 1))
        fi
    done
}

test_lookalike_author_hosts_fail() {
    expect_gate "notgithub.com / notlinkedin.com author links" \
        "$(good_readme | sed 's#https://github.com/#https://notgithub.com/#; s#https://www.linkedin.com/#https://notlinkedin.com/#')" \
        fail "author without a github.com/<user> link"
    expect_gate "country-subdomain LinkedIn link is a real host" \
        "$(good_readme | sed 's#https://www.linkedin.com/#https://br.linkedin.com/#')" pass
}

test_indented_heading_is_recognised() {
    expect_gate "heading indented by three spaces" \
        "$(good_readme | sed 's/^### Usage/   ### Usage/')" pass
}

main() {
    local str_test
    for str_test in $(declare -F | awk '$3 ~ /^test_/ { print $3 }'); do
        "$str_test"
    done
    if [ "$int_failures" -gt 0 ]; then
        print_status "error" "$int_failures check_readme_structure case(s) failed"
        exit 1
    fi
    print_status "success" "check_readme_structure should-fail cases all behaved"
}

main "$@"
