#!/usr/bin/env bash

set -e

# Fallback version for installs WITHOUT a .git tree (packaged installs + `make install` stamp the
# real value here at build/install time). A git checkout ignores this and derives the version from
# the tag via `git describe` — see print_version. Do not hand-bump: the release tag is the single
# source of truth.
BLUEPRINTX_VERSION="0.0.0"

DEV_MODE=0
DRY_RUN=0
CLEAN_TEMP=0
TEMP_ROOT=""
SUBCOMMAND=""

SPEC_FILE=""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATES_ROOT="$BLUEPRINTX_ROOT/templates"
# shellcheck source=bin/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=bin/lib/spec.sh
source "$SCRIPT_DIR/lib/spec.sh"


print_usage() {
    echo "Usage: blueprintx [subcommand] [options]"
    echo
    echo "Subcommands:"
    echo "  new        Create a new project interactively"
    echo "  preview    Show available skeleton structures"
    echo "  help       Show this help message"
    echo
    echo "Options:"
    echo "  --dev        Scaffold into a temp directory (preserved on exit)"
    echo "  --dry-run    Preview structure without creating files"
    echo "  --clean      Delete temp dir on exit (use with --dev)"
    echo "  --spec FILE  Answer every prompt by NAME from a KEY=value spec file"
    echo "               instead of interactively (see docs/spec-answers.md)."
    echo "               Combine with --dry-run to print the resolved answers"
    echo "               without scaffolding anything."
    echo "  -V, --version  Print version and exit"
    echo "  -h, --help     Show this help"
    echo
    echo "Examples:"
    echo "  blueprintx new"
    echo "  blueprintx new --dev"
    echo "  blueprintx new --dry-run"
    echo "  blueprintx new --spec my-project.spec"
    echo "  blueprintx new --spec my-project.spec --dry-run"
    echo "  blueprintx preview"
}

print_version() {
    # Prefer the git tag (the single source of truth) when run from a checkout; fall back to the
    # stamped BLUEPRINTX_VERSION literal for packaged installs / source archives without a .git.
    local str_version
    if str_version=$(git -C "$BLUEPRINTX_ROOT" describe --tags --always 2>/dev/null) \
        && [ -n "$str_version" ]; then
        echo "blueprintx ${str_version#v}"
    else
        echo "blueprintx $BLUEPRINTX_VERSION"
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        new|preview|help)
            SUBCOMMAND="$1"
            shift
            ;;
        --dev)
            DEV_MODE=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --clean)
            CLEAN_TEMP=1
            shift
            ;;
        --spec)
            [ -n "${2:-}" ] || { echo "--spec requires a file path" >&2; exit 1; }
            SPEC_FILE="$2"
            [ -f "$SPEC_FILE" ] || { echo "--spec: file not found: $SPEC_FILE" >&2; exit 1; }
            shift 2
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        -V|--version)
            print_version
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            print_usage >&2
            exit 1
            ;;
    esac
done


show_banner() {
    # Column 72 is the exact BLUEPRINT/X glyph boundary on every one of the six
    # rows below (blueprintx#256, verified against assets/logo.png): it always
    # falls inside the T glyph or a blank inset column, and the X glyph never
    # starts before column 73 — one split index works for every row, no
    # per-row offset needed.
    local -a rows=(
        " ██████╗ ██╗     ██╗   ██╗███████╗██████╗ ██████╗ ██╗███╗   ██╗████████╗██╗  ██╗ "
        " ██╔══██╗██║     ██║   ██║██╔════╝██╔══██╗██╔══██╗██║████╗  ██║╚══██╔══╝╚██╗██╔╝ "
        " ██████╔╝██║     ██║   ██║█████╗  ██████╔╝██████╔╝██║██╔██╗ ██║   ██║    ╚███╔╝  "
        " ██╔══██╗██║     ██║   ██║██╔══╝  ██╔═══╝ ██╔══██╗██║██║╚██╗██║   ██║    ██╔██╗  "
        " ██████╔╝███████╗╚██████╔╝███████╗██║     ██║  ██║██║██║ ╚████║   ██║   ██╔╝ ██╗ "
        " ╚═════╝ ╚══════╝ ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ "
    )
    local row
    echo
    for row in "${rows[@]}"; do
        printf "${BRAND_TEAL}%s${BRAND_PINK}%s${BRAND_NC}\n" "${row:0:72}" "${row:72}"
    done
    echo
    printf "  ${BRAND_TEAL}Blueprints.${BRAND_NC} ${BRAND_PINK}Expansible.${BRAND_NC}\n"
    echo
}

show_main_menu() {
    show_banner
    echo
    printf "${BLUE}What would you like to do?${NC}\n"
    printf "  ${GREEN}1) ➜${NC}  Create a project\n"
    printf "  ${YELLOW}2) ?${NC}  Help (what can BlueprintX do?)\n"
    printf "  ${BLUE}3) ▦${NC}  Show scaffolding structures and examples\n"
    printf "  ${CANCEL}4) ✕${NC}  Cancel\n"
    echo
}

show_help() {
    echo
    print_status "info" "Blueprintx is a lightweight scaffolding tool based on Make + bash."
    print_status "info" "It can currently:"
    print_status "info" "  - Create Python projects with different folder structures (skeletons)"
    print_status "info" "  - Ask interactively for language, project name, target directory, and structure"
    print_status "info" "  - Generate Python-ready projects that use pyenv + poetry (inside the generated project)"
    echo
    print_status "info" "To create a project, run:"
    print_status "config" "  blueprintx new"
    echo
    print_status "info" "You can also run in dev/preview modes:"
    print_status "config" "  blueprintx new --dev      # scaffold into a temp dir"
    print_status "config" "  blueprintx new --dry-run  # preview only, no files created"
    print_status "config" "  blueprintx preview        # browse available skeletons"
}

show_hex_service() {
        echo
        print_section "ddd-service-native-db skeleton"
        print_status "info" "Description:"
        print_status "config" "Backend/service-oriented structure with chassis/capabilities separation,"
        print_status "config" "suitable for APIs and services using clean/hexagonal-ish design."
        echo
        print_status "info" "Example structure:"
        cat << 'EOF'
    project/
        src/
            chassis/
                db_schema/
                    domain/
                    infrastructure/
                    application/
            capabilities/
                example_feature/
                    domain/
                    application/
                    infrastructure/
            utils/
            config/
            main.py
        tests/
            integration/
            performance/
            unit/
        container/
        bin/
        assets/
        docs/
        .github/
            workflows/
                tests.yaml
            CODEOWNERS
            PULL_REQUEST_TEMPLATE.md
        .env
        .gitignore
        .pre-commit-config.yaml
        .vscode/
        README.md
        requirements.txt
        pyproject.toml
EOF
}

show_orm_service() {
        echo
        print_section "ddd-service-orm-db skeleton"
        print_status "info" "Description:"
        print_status "config" "Same DDD/hexagonal structure as native-db, but uses SQLAlchemy ORM"
        print_status "config" "for database operations. Supports PostgreSQL, MySQL, SQLite, Oracle, MSSQL."
        echo
        print_status "info" "Key differences from native-db:"
        print_status "config" "  - Uses SQLAlchemy ORM models instead of raw SQL"
        print_status "config" "  - Single repository pattern works with any SQLAlchemy-supported DB"
        print_status "config" "  - Built-in session management and connection pooling"
        echo
        print_status "info" "Example structure:"
        cat << 'EOF'
    project/
        src/
            chassis/
                db_schema/
                    domain/
                    infrastructure/
                        base.py         # SQLAlchemy base, session manager
                        models.py       # ORM models
                        repository.py   # Generic SQLAlchemy repository
                    application/
            capabilities/
                example_feature/
                    domain/
                    application/
                    infrastructure/
            utils/
            config/
            main.py
        tests/
            integration/
            performance/
            unit/
        container/
        bin/
        assets/
        docs/
        .github/
            workflows/
                tests.yaml
            CODEOWNERS
            PULL_REQUEST_TEMPLATE.md
        .env
        .gitignore
        .pre-commit-config.yaml
        .vscode/
        README.md
        requirements.txt
        pyproject.toml
EOF
}

show_lib_minimal() {
        echo
        print_section "lib-minimal skeleton"
        print_status "info" "Description:"
        print_status "config" "Minimal library-style project, good for small libs, tools, or"
        print_status "config" "starting points for simple CLIs or packages."
        echo
        print_status "info" "Example structure:"
        cat << 'EOF'
    project/
        src/
            project_name/
                __init__.py
                main.py
        tests/
            integration/
            performance/
            unit/
                test_main.py
        container/
        bin/
        docs/
            index.md
        .github/
            workflows/
                tests.yaml
            CODEOWNERS
            PULL_REQUEST_TEMPLATE.md
        pyproject.toml
        .env
        .gitignore
        .pre-commit-config.yaml
        .vscode/
        requirements.txt
        README.md
EOF
}

prompt_project_name() {
    printf "${CYAN}Project name${NC} (folder name): " >&2
    read -r PROJECT_NAME
    if [ -z "$PROJECT_NAME" ]; then
        exit_error "Project name cannot be empty."
    fi
    # The name has to serve TWO identities: the distribution name (hyphens legal) and
    # the import package derived from it (hyphens illegal). `to_import_package_name`
    # rescues a hyphen; nothing rescues a leading digit, a dot or a space, so those are
    # refused here rather than shipped as a package that cannot be imported.
    if ! is_valid_project_name "$PROJECT_NAME"; then
        exit_error "Invalid project name '$PROJECT_NAME'. Use a letter or underscore first, then letters, digits, '-' or '_'."
    fi
    echo "$PROJECT_NAME"
}

prompt_project_description() {
    printf "${CYAN}Project description${NC} (optional, press Enter to skip): " >&2
    read -r PROJECT_DESCRIPTION
    echo "$PROJECT_DESCRIPTION"
}

prompt_project_root() {
    printf "${CYAN}Select directory${NC}\n" >&2
    printf "  1) Current directory ($PWD)\n" >&2
    printf "  2) Another directory\n" >&2
    printf "${CYAN}Choice${NC} [1-2]: " >&2
    read -r choice
    printf "\n" >&2

    case "$choice" in
        1)
            echo "$PWD"
            return 0
            ;;
        2)
            read -r -p "$(prompt_sub "Enter target path: ")" TARGET_DIR
            if [ -z "$TARGET_DIR" ]; then
                exit_error "Target directory cannot be empty."
            fi
            TARGET_DIR="${TARGET_DIR/#\~/$HOME}"
            mkdir -p "$TARGET_DIR"
            echo "$TARGET_DIR"
            return 0
            ;;
        *)
            print_status "warning" "Invalid option. Try again." >&2
            prompt_project_root
            return
            ;;
    esac
}

show_skeleton_structure() {
    local skeleton="$1"
    case "$skeleton" in
        "ddd-service-native-db")
            show_hex_service
            ;;
        "ddd-service-orm-db")
            show_orm_service
            ;;
        "lib-minimal")
            show_lib_minimal
            ;;
        *)
            # Fall back to description from skeleton.meta
            local meta="$TEMPLATES_ROOT/$skeleton/skeleton.meta"
            if [ -f "$meta" ]; then
                local description=""
                description=$(grep '^description=' "$meta" | cut -d= -f2-)
                print_status "info" "$skeleton: $description"
            else
                print_status "warning" "No preview available for skeleton '$skeleton'"
            fi
            ;;
    esac
}

_discover_languages() {
    local seen=""
    for meta in "$TEMPLATES_ROOT"/*/skeleton.meta; do
        [ -f "$meta" ] || continue
        local lang
        lang=$(grep '^language=' "$meta" | cut -d= -f2-)
        [ -z "$lang" ] && continue
        case " $seen " in
            *" $lang "*) ;;
            *) seen="$seen $lang" ;;
        esac
    done
    echo "$seen"
}

_discover_skeletons_for_lang() {
    local target_lang="$1"
    for meta in "$TEMPLATES_ROOT"/*/skeleton.meta; do
        [ -f "$meta" ] || continue
        local lang
        lang=$(grep '^language=' "$meta" | cut -d= -f2-)
        [ "$lang" = "$target_lang" ] || continue
        local dir
        dir=$(basename "$(dirname "$meta")")
        echo "$dir"
    done
}

prompt_language() {
    local languages
    languages=$(_discover_languages)

    local idx=1
    local lang_list=()
    printf "${CYAN}Select language${NC}\n" >&2
    for lang in $languages; do
        printf "  ${GREEN}%d) %s${NC}\n" "$idx" "$lang" >&2
        lang_list+=("$lang")
        idx=$((idx + 1))
    done
    local cancel_idx="$idx"
    printf "  ${CANCEL}%d) Cancel${NC}\n" "$cancel_idx" >&2
    printf "${CYAN}Choice${NC} [1-%d]: " "$cancel_idx" >&2
    read -r choice
    printf "\n" >&2

    if [ "$choice" = "$cancel_idx" ]; then
        print_status "warning" "Aborting..."
        exit 0
    fi

    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -lt "$cancel_idx" ]; then
        echo "${lang_list[$((choice - 1))]}"
        return 0
    fi

    print_status "warning" "Invalid option. Try again." >&2
    prompt_language
}

prompt_skeleton() {
    local lang="$1"
    local skeletons=()
    while IFS= read -r s; do
        skeletons+=("$s")
    done < <(_discover_skeletons_for_lang "$lang")

    if [ "${#skeletons[@]}" -eq 0 ]; then
        exit_error "No skeletons found for language '$lang'."
    fi

    printf "${CYAN}Select project skeleton${NC}\n" >&2
    local idx=1
    for skeleton in "${skeletons[@]}"; do
        local meta="$TEMPLATES_ROOT/$skeleton/skeleton.meta"
        local display_name="$skeleton"
        [ -f "$meta" ] && display_name=$(grep '^display_name=' "$meta" | cut -d= -f2-)
        printf "  ${BLUE}%d) %s${NC}\n" "$idx" "$display_name" >&2
        idx=$((idx + 1))
    done
    printf "${CYAN}Choice${NC} [1-%d]: " "$((idx - 1))" >&2
    read -r choice
    printf "\n" >&2

    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -lt "$idx" ]; then
        echo "${skeletons[$((choice - 1))]}"
        return 0
    fi

    print_status "warning" "Invalid option. Try again." >&2
    prompt_skeleton "$lang"
}

prompt_license() {
    printf "${CYAN}Select license${NC}\n" >&2
    printf "  ${BLUE} 1) MIT${NC}          — Do whatever you want; keep the copyright notice. (default)\n" >&2
    printf "  ${BLUE} 2) Apache-2.0${NC}   — Like MIT, adds an explicit patent grant.\n" >&2
    printf "  ${BLUE} 3) GPL-3.0${NC}      — Copyleft; modifications must stay GPL-3.0.\n" >&2
    printf "  ${BLUE} 4) AGPL-3.0${NC}     — Strongest copyleft; closes the SaaS loophole.\n" >&2
    printf "               Ideal for dual-licensing: open for all, commercial users\n" >&2
    printf "               must obtain a separate proprietary license.\n" >&2
    printf "  ${BLUE} 5) LGPL-2.1${NC}     — Weak copyleft; allows linking from proprietary code.\n" >&2
    printf "  ${BLUE} 6) MPL-2.0${NC}      — File-level copyleft; compatible with proprietary projects.\n" >&2
    printf "  ${BLUE} 7) BSD-2-Clause${NC} — Permissive; minimal restrictions on redistribution.\n" >&2
    printf "  ${BLUE} 8) BSD-3-Clause${NC} — Like BSD-2, adds a non-endorsement clause.\n" >&2
    printf "  ${BLUE} 9) BSL-1.0${NC}      — Very permissive; no warranty, no restrictions.\n" >&2
    printf "  ${BLUE}10) CC0-1.0${NC}      — Public domain dedication; waives all rights.\n" >&2
    printf "  ${BLUE}11) Unlicense${NC}    — Public domain; maximally free, no conditions.\n" >&2
    printf "${CYAN}Choice${NC} [1-11, default 1]: " >&2
    read -r choice
    printf "\n" >&2

    case "$choice" in
        1|"") echo "MIT" ;;
        2)    echo "Apache-2.0" ;;
        3)    echo "GPL-3.0" ;;
        4)    echo "AGPL-3.0" ;;
        5)    echo "LGPL-2.1" ;;
        6)    echo "MPL-2.0" ;;
        7)    echo "BSD-2-Clause" ;;
        8)    echo "BSD-3-Clause" ;;
        9)    echo "BSL-1.0" ;;
        10)   echo "CC0-1.0" ;;
        11)   echo "Unlicense" ;;
        *)
            print_status "warning" "Invalid option. Try again." >&2
            prompt_license
            return
            ;;
    esac
}

# The locale of the GENERATED project's published pages only. It says nothing about
# BlueprintX's own prose, which is en-US with no exceptions (root CLAUDE.md), and nothing
# about code: comments and docstrings stay English in every locale, enforced in the
# generated project by bin/check_comment_language.py. See docs/cli-reference.md, "Documentation locale".
prompt_docs_locale() {
    printf "${CYAN}Select documentation locale${NC} (language the new project's README.md and docs/ are meant to be written in; shipped text is English)\n" >&2
    printf "  ${BLUE}1) en${NC}    — English (default)\n" >&2
    printf "  ${BLUE}2) pt-BR${NC} — Brazilian Portuguese\n" >&2
    printf "        Code comments and docstrings stay English either way.\n" >&2
    printf "${CYAN}Choice${NC} [1-2, default 1]: " >&2
    read -r choice
    printf "\n" >&2

    case "$choice" in
        1|"") echo "en" ;;
        2)    echo "pt-BR" ;;
        *)
            print_status "warning" "Invalid option. Try again." >&2
            prompt_docs_locale
            return
            ;;
    esac
}

# The locales prompt_docs_locale offers; the --spec flow validates against the same two.
is_valid_docs_locale() {
    case "$1" in
        en|pt-BR) return 0 ;;
        *) return 1 ;;
    esac
}

create_project() {
    local project_root="$1"
    local project_name="$2"
    local project_description="$3"
    local lang="$4"
    local skeleton="$5"
    local license_choice="$6"
    local docs_locale="$7"

    local full_path="$project_root/$project_name"

    print_status "info" "Creating project '$project_name' under '$project_root'"
    print_status "config" "Full path: $full_path"

    local meta="$TEMPLATES_ROOT/$skeleton/skeleton.meta"
    if [ ! -f "$meta" ]; then
        exit_error "No skeleton.meta found for '$skeleton'."
    fi

    local scaffold_rel
    scaffold_rel=$(grep '^scaffold=' "$meta" | cut -d= -f2-)
    local scaffold_script="$BLUEPRINTX_ROOT/$scaffold_rel"

    if [ ! -f "$scaffold_script" ]; then
        exit_error "Scaffold script not found: $scaffold_script"
    fi

    LICENSE_CHOICE="$license_choice" DOCS_LOCALE="$docs_locale" \
        bash "$scaffold_script" "$project_root" "$project_name" "$project_description"
}


# Validate spec values against the chosen skeleton before any file is written: a bad value would
# otherwise reach the scaffold, which reads a nonexistent license template after the project
# dir already exists. Reads LANG_CHOICE, SKELETON_CHOICE, LICENSE_CHOICE and DOCS_LOCALE.
validate_spec_answers() {
    local skeleton_language
    skeleton_language=$(grep '^language=' "$TEMPLATES_ROOT/$SKELETON_CHOICE/skeleton.meta" | cut -d= -f2-)
    [ "$LANG_CHOICE" = "$skeleton_language" ] \
        || exit_error "--spec: skeleton '$SKELETON_CHOICE' is a '$skeleton_language' skeleton, not '$LANG_CHOICE'."
    [ -f "$TEMPLATES_ROOT/licenses/$LICENSE_CHOICE" ] \
        || exit_error "--spec: unknown license '$LICENSE_CHOICE' (no templates/licenses/$LICENSE_CHOICE)."
    is_valid_docs_locale "$DOCS_LOCALE" \
        || exit_error "--spec: 'docs_locale' must be en or pt-BR, got '$DOCS_LOCALE'."
    # A bad y/n value must stop the run here, in the main shell: spec_yn used to turn it into "n".
    if spec_skeleton_supported "$SKELETON_CHOICE"; then
        spec_validate_answers "$SKELETON_CHOICE" "$SPEC_FILE" \
            || exit_error "--spec: fix the y/n value(s) above before scaffolding."
    fi
}

# --dev: scaffold into a fresh temp root instead of the working directory; with --clean the
# root is removed on exit. Shared by the interactive flow and the --spec flow.
select_dev_project_root() {
    TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/BlueprintX.XXXXXX")
    PROJECT_ROOT="$TEMP_ROOT"
    print_status "config" "Dev mode: using temp root $PROJECT_ROOT"
    if [ "$CLEAN_TEMP" -eq 1 ]; then
        trap 'rm -rf "$TEMP_ROOT"' EXIT
        print_status "info" "Temp directory will be cleaned on exit"
    fi
}

print_dev_mode_notice() {
    [ "$DEV_MODE" -eq 1 ] || return 0
    print_status "warning" "Dev mode: project scaffolded in temp directory"
    if [ "$CLEAN_TEMP" -ne 1 ]; then
        print_status "info" "Temp directory preserved at: $TEMP_ROOT"
    fi
}

# Pipe the named-key answers into the skeleton's scaffold. Reads the globals the spec flow set.
scaffold_from_spec() {
    print_status "info" "Creating project '$PROJECT_NAME' under '$PROJECT_ROOT' from spec '$SPEC_FILE'"

    local meta="$TEMPLATES_ROOT/$SKELETON_CHOICE/skeleton.meta"
    local scaffold_rel scaffold_script
    scaffold_rel=$(grep '^scaffold=' "$meta" | cut -d= -f2-)
    scaffold_script="$BLUEPRINTX_ROOT/$scaffold_rel"
    [ -f "$scaffold_script" ] || exit_error "Scaffold script not found: $scaffold_script"

    spec_stdin_for_skeleton "$SKELETON_CHOICE" "$SPEC_FILE" \
        | GITHUB_USERNAME="$(spec_get "$SPEC_FILE" github_username "${GITHUB_USERNAME:-}")" \
            LICENSE_CHOICE="$LICENSE_CHOICE" DOCS_LOCALE="$DOCS_LOCALE" \
            bash "$scaffold_script" "$PROJECT_ROOT" "$PROJECT_NAME" "$PROJECT_DESCRIPTION"
}

#
# --spec: answer blueprintx's own top-level prompts (project_name, ...,
# skeleton, license) plus every scaffold-internal prompt by NAME instead of
# interactively — the fix for #481 (positional stdin breaks the moment a
# prompt is added anywhere). See docs/spec-answers.md for the full key
# catalog.
#
run_create_flow_from_spec() {
    PROJECT_NAME=$(spec_get "$SPEC_FILE" project_name)
    [ -n "$PROJECT_NAME" ] || exit_error "--spec: 'project_name' key is required."
    if ! is_valid_project_name "$PROJECT_NAME"; then
        exit_error "Invalid project name '$PROJECT_NAME'. Use a letter or underscore first, then letters, digits, '-' or '_'."
    fi
    PROJECT_DESCRIPTION=$(spec_get "$SPEC_FILE" project_description)
    LANG_CHOICE=$(spec_get "$SPEC_FILE" language)
    [ -n "$LANG_CHOICE" ] || exit_error "--spec: 'language' key is required."
    SKELETON_CHOICE=$(spec_get "$SPEC_FILE" skeleton)
    [ -n "$SKELETON_CHOICE" ] || exit_error "--spec: 'skeleton' key is required."
    [ -f "$TEMPLATES_ROOT/$SKELETON_CHOICE/skeleton.meta" ] \
        || exit_error "--spec: unknown skeleton '$SKELETON_CHOICE'."
    LICENSE_CHOICE=$(spec_get "$SPEC_FILE" license MIT)
    DOCS_LOCALE=$(spec_get "$SPEC_FILE" docs_locale en)

    validate_spec_answers

    if [ "$DRY_RUN" -eq 1 ]; then
        print_status "info" "Dry-run (--spec): resolved answers for '$SKELETON_CHOICE'"
        print_status "config" "project_name=$PROJECT_NAME"
        print_status "config" "project_description=$PROJECT_DESCRIPTION"
        print_status "config" "language=$LANG_CHOICE"
        print_status "config" "skeleton=$SKELETON_CHOICE"
        print_status "config" "license=$LICENSE_CHOICE"
        print_status "config" "docs_locale=$DOCS_LOCALE"
        if spec_skeleton_supported "$SKELETON_CHOICE"; then
            spec_describe_skeleton "$SKELETON_CHOICE" "$SPEC_FILE" \
                | while IFS= read -r line; do print_status "config" "$line"; done
        else
            print_status "warning" "No named-key prompt map for '$SKELETON_CHOICE' yet — its internal prompts would stay interactive."
        fi
        show_skeleton_structure "$SKELETON_CHOICE"
        exit 0
    fi

    # Refuse before anything is created: a skeleton with no prompt map would otherwise run its
    # scaffold with interactive prompts, hanging an unattended run.
    spec_skeleton_supported "$SKELETON_CHOICE" \
        || exit_error "--spec: '$SKELETON_CHOICE' has no named-key prompt map, so it cannot run unattended. Use the interactive flow, or one of: $(spec_supported_skeletons)."

    if [ "$DEV_MODE" -eq 1 ]; then
        select_dev_project_root
    else
        PROJECT_ROOT=$(spec_get "$SPEC_FILE" project_root "$PWD")
        mkdir -p "$PROJECT_ROOT"
    fi

    scaffold_from_spec

    echo
    print_status "success" "Project created from spec: $PROJECT_ROOT/$PROJECT_NAME"
    print_dev_mode_notice
}

run_create_flow() {
    if [ -n "$SPEC_FILE" ]; then
        run_create_flow_from_spec
        return
    fi

    PROJECT_NAME=$(prompt_project_name)
    PROJECT_DESCRIPTION=$(prompt_project_description)

    if [ "$DRY_RUN" -eq 1 ]; then
        PROJECT_ROOT="(dry-run)"
    elif [ "$DEV_MODE" -eq 1 ]; then
        select_dev_project_root
    else
        PROJECT_ROOT=$(prompt_project_root)
    fi

    LANG_CHOICE=$(prompt_language)
    SKELETON_CHOICE=$(prompt_skeleton "$LANG_CHOICE")
    LICENSE_CHOICE=$(prompt_license)
    DOCS_LOCALE=$(prompt_docs_locale)

    if [ "$DRY_RUN" -eq 1 ]; then
        print_status "info" "Dry-run: showing structure for '$SKELETON_CHOICE'"
        show_skeleton_structure "$SKELETON_CHOICE"
        exit 0
    fi

    create_project "$PROJECT_ROOT" "$PROJECT_NAME" "$PROJECT_DESCRIPTION" "$LANG_CHOICE" "$SKELETON_CHOICE" "$LICENSE_CHOICE" "$DOCS_LOCALE"

    echo
    printf "${GREEN}╔════════════════════════════════════════╗${NC}\n"
    printf "${GREEN}║   ✓ Project created successfully!      ║${NC}\n"
    printf "${GREEN}╚════════════════════════════════════════╝${NC}\n"
    echo
    print_status "config" "Project: $PROJECT_NAME"
    print_status "config" "Location: $PROJECT_ROOT/$PROJECT_NAME"
    print_status "config" "Skeleton: $SKELETON_CHOICE"
    print_status "config" "License: $LICENSE_CHOICE"
    print_status "config" "Docs locale: $DOCS_LOCALE (MkDocs skeletons only)"
    print_dev_mode_notice
    print_status "info" "Log file: $LOG_FILE"
}

main() {
    case "$SUBCOMMAND" in
        new)
            show_banner
            run_create_flow
            return
            ;;
        preview)
            bash "$SCRIPT_DIR/preview.sh"
            exit 0
            ;;
        help)
            print_usage
            exit 0
            ;;
    esac

    show_main_menu

    read -r -p "$(prompt_main "Choose an option [1-4]: ")" choice

    case "$choice" in
        1)
            MAIN_ACTION="create"
            ;;
        2)
            show_help
            exit 0
            ;;
        3)
            bash "$SCRIPT_DIR/preview.sh"
            echo
            read -r -p "$(prompt_main "Do you want to proceed to create a project now? [Y/n] ")" go_create
            case "$go_create" in
                n|N|no|NO)
                    print_status "info" "Ok, not creating a project now."
                    exit 0
                    ;;
                *)
                    MAIN_ACTION="create"
                    ;;
            esac
            ;;
        4)
            print_status "warning" "Aborting. Bye."
            exit 0
            ;;
        *)
            print_status "warning" "Invalid option. Try again."
            main
            return
            ;;
    esac

    if [ "$MAIN_ACTION" != "create" ]; then
        exit_error "No creation action selected."
    fi

    run_create_flow
}

# Sourced by tests/test_docs_locale_prompt.sh to reach the prompt helpers without the menu.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main
fi
