#!/usr/bin/env bash

scaffold_mark_untranslated() {
    local project_path="$1" str_page str_marker='<!-- docs-lang:untranslated -->'
    [ "${DOCS_LOCALE:-en}" != "en" ] || return 0
    [ -d "$project_path/docs" ] || return 0
    while IFS= read -r str_page; do
        grep -qxF "$str_marker" "$str_page" || printf '\n%s\n' "$str_marker" >>"$str_page"
    done < <(find "$project_path/docs" -type f -name '*.md'; [ -f "$project_path/README.md" ] && echo "$project_path/README.md")
}
