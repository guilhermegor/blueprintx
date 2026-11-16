#!/usr/bin/env bash

scaffold_docs_pages() {
    local project_path="$1" str_gate="$1/bin/check_docs_language.py" str_pages str_err
    if [ ! -f "$str_gate" ]; then
        [ -d "$project_path/docs" ] || [ -f "$project_path/README.md" ] \
            && echo "warning: $str_gate is missing; marking every docs/*.md, README.md and CONTRIBUTING.md instead" >&2
    elif str_err="$(mktemp)" \
        && str_pages="$(PYTHONDONTWRITEBYTECODE=1 python3 "$str_gate" --root "$project_path" --list-pages 2>"$str_err")"; then
        rm -f "$str_err"
        printf '%s\n' "$str_pages"
        return 0
    else
        echo "warning: could not list the docs pages with the gate ($(printf '%s %s' "$str_pages" "$(cat "${str_err:-/dev/null}")" | tr '\n' ' ' | tail -c 160)); marking every docs/*.md, README.md and CONTRIBUTING.md instead" >&2
        rm -f "$str_err"
    fi
    [ -d "$project_path/docs" ] && find "$project_path/docs" -type f -name '*.md'
    [ -f "$project_path/README.md" ] && echo "$project_path/README.md"
    [ -f "$project_path/CONTRIBUTING.md" ] && echo "$project_path/CONTRIBUTING.md"
    return 0
}

scaffold_localize_contributing() {
    local project_path="$1" str_src="$COMMON_TEMPLATE_ROOT/CONTRIBUTING.${DOCS_LOCALE:-en}.md"
    [ "${DOCS_LOCALE:-en}" != "en" ] && [ -f "$str_src" ] || return 1
    cp "$str_src" "$project_path/CONTRIBUTING.md"
}

scaffold_render_security() {
    local project_path="$1" str_line path_tmp
    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' \
        <"$SHARED_TEMPLATE_ROOT/SECURITY.md" >"$project_path/SECURITY.md"
    case "${DOCS_LOCALE:-en}" in
        pt-BR) str_line='> Para reportar uma vulnerabilidade, use o relato privado do GitHub: aba **Security** do repositório, **Report a vulnerability**. Não abra uma issue pública. O restante desta política está em inglês de propósito.' ;;
        *) return 0 ;;
    esac
    path_tmp="$(mktemp)"
    awk -v str_line="$str_line" 'NR == 1 { print; print ""; print str_line; next } { print }' \
        "$project_path/SECURITY.md" >"$path_tmp"
    cat "$path_tmp" >"$project_path/SECURITY.md"
    rm -f "$path_tmp"
}

scaffold_mark_untranslated() {
    local project_path="$1" str_page str_marker='<!-- docs-lang:untranslated -->' str_localized=""
    [ "${DOCS_LOCALE:-en}" != "en" ] || return 0
    scaffold_localize_contributing "$project_path" && str_localized="$project_path/CONTRIBUTING.md"
    while IFS= read -r str_page; do
        [ -f "$str_page" ] || continue
        [ -n "$str_localized" ] && [ "$str_page" -ef "$str_localized" ] && continue
        grep -qxF "$str_marker" "$str_page" || printf '\n%s\n' "$str_marker" >>"$str_page"
    done < <(scaffold_docs_pages "$project_path")
}
