#!/usr/bin/env bash

scaffold_docs_pages() {
    local project_path="$1" str_gate="$1/bin/check_docs_language.py" str_pages
    if [ -f "$str_gate" ] && str_pages="$(PYTHONDONTWRITEBYTECODE=1 python3 "$str_gate" --root "$project_path" --list-pages 2>/dev/null)"; then
        printf '%s\n' "$str_pages"
        return 0
    fi
    [ -d "$project_path/docs" ] && find "$project_path/docs" -type f -name '*.md'
    [ -f "$project_path/README.md" ] && echo "$project_path/README.md"
    return 0
}

scaffold_mark_untranslated() {
    local project_path="$1" str_page str_marker='<!-- docs-lang:untranslated -->'
    [ "${DOCS_LOCALE:-en}" != "en" ] || return 0
    while IFS= read -r str_page; do
        grep -qxF "$str_marker" "$str_page" || printf '\n%s\n' "$str_marker" >>"$str_page"
    done < <(scaffold_docs_pages "$project_path")
}
