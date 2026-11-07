#!/usr/bin/env bash

scaffold_mark_untranslated() {
    local project_path="$1" str_page
    [ "${DOCS_LOCALE:-en}" != "en" ] || return 0
    while IFS= read -r str_page; do
        printf '\n<!-- docs-lang:untranslated -->\n' >>"$str_page"
    done < <(find "$project_path/docs" -type f -name '*.md'; ls "$project_path/README.md")
}
