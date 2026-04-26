#!/usr/bin/env bash

set -e

BLUEPRINTX_VERSION="0.1.6"

DEV_MODE=0
DRY_RUN=0
CLEAN_TEMP=0
TEMP_ROOT=""
SUBCOMMAND=""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/logging.sh"

# =========================================================================
# ARG PARSING
# =========================================================================

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
    echo "  -V, --version  Print version and exit"
    echo "  -h, --help     Show this help"
    echo
    echo "Examples:"
    echo "  blueprintx new"
    echo "  blueprintx new --dev"
    echo "  blueprintx new --dry-run"
    echo "  blueprintx preview"
}

print_version() {
    echo "blueprintx $BLUEPRINTX_VERSION"
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

# ============================================================================
# FUNCTIONS
# ============================================================================

show_banner() {
    echo
printf "${CYAN} ██████╗ ██╗     ██╗   ██╗███████╗██████╗ ██████╗ ██╗███╗   ██╗████████╗██╗  ██╗ ${NC}\n"
printf "${CYAN} ██╔══██╗██║     ██║   ██║██╔════╝██╔══██╗██╔══██╗██║████╗  ██║╚══██╔══╝╚██╗██╔╝ ${NC}\n"
printf "${CYAN} ██████╔╝██║     ██║   ██║█████╗  ██████╔╝██████╔╝██║██╔██╗ ██║   ██║    ╚███╔╝  ${NC}\n"
printf "${CYAN} ██╔══██╗██║     ██║   ██║██╔══╝  ██╔═══╝ ██╔══██╗██║██║╚██╗██║   ██║    ██╔██╗  ${NC}\n"
printf "${CYAN} ██████╔╝███████╗╚██████╔╝███████╗██║     ██║  ██║██║██║ ╚████║   ██║   ██╔╝ ██╗ ${NC}\n"
printf "${CYAN} ╚═════╝ ╚══════╝ ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ ${NC}\n"    echo
    printf "${MAGENTA}  Blueprints. Expansible.${NC}\n"
    echo
}

show_main_menu() {
    show_banner
    echo
    printf "${BLUE}What would you like to do?${NC}\n"
    printf "  ${GREEN}1) ➜${NC}  Create a project\n"
    printf "  ${YELLOW}2) ?${NC}  Help (what can BlueprintX do?)\n"
    printf "  ${BLUE}3) ▦${NC}  Show scaffolding structures and examples\n"
    printf "  ${RED}4) ✕${NC}  Cancel\n"
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
            read -r -p "$(printf "${CYAN}Enter target path${NC}: ")" TARGET_DIR
            if [ -z "$TARGET_DIR" ]; then
                exit_error "Target directory cannot be empty."
            fi
            TARGET_DIR="${TARGET_DIR/#\~/$HOME}"
            mkdir -p "$TARGET_DIR"
            echo "$TARGET_DIR"
            return 0
            ;;
        *)
            print_status "warning" "Invalid option. Try again."
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
            print_status "warning" "No preview available for skeleton '$skeleton'"
            ;;
    esac
}

prompt_language() {
    printf "${CYAN}Select language${NC}\n" >&2
    printf "  ${GREEN}1) Python${NC}\n" >&2
    printf "  ${RED}2) Cancel${NC}\n" >&2
    printf "${CYAN}Choice${NC} [1-2]: " >&2
    read -r choice
    printf "\n" >&2
    
    case "$choice" in
        1)
            echo "python"
            return 0
            ;;
        2)
            print_status "warning" "Aborting..."
            exit 0
            ;;
        *)
            print_status "warning" "Invalid option. Try again."
            prompt_language
            return
            ;;
    esac
}

prompt_skeleton() {
    printf "${CYAN}Select project skeleton${NC}\n" >&2
    printf "  ${BLUE}1) ddd-service-native-db${NC} (native DB libraries)\n" >&2
    printf "  ${BLUE}2) ddd-service-orm-db${NC} (SQLAlchemy ORM)\n" >&2
    printf "  ${BLUE}3) lib-minimal${NC}\n" >&2
    printf "${CYAN}Choice${NC} [1-3]: " >&2
    read -r choice
    printf "\n" >&2
    
    case "$choice" in
        1)
            echo "ddd-service-native-db"
            return 0
            ;;
        2)
            echo "ddd-service-orm-db"
            return 0
            ;;
        3)
            echo "lib-minimal"
            return 0
            ;;
        *)
            print_status "warning" "Invalid option. Try again."
            prompt_skeleton
            return
            ;;
    esac
}

prompt_license() {
    local licenses_dir
    licenses_dir="$(cd "$SCRIPT_DIR/.." && pwd)/templates/licenses"

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
            print_status "warning" "Invalid option. Try again."
            prompt_license
            return
            ;;
    esac
}

create_project() {
    local project_root="$1"
    local project_name="$2"
    local project_description="$3"
    local lang="$4"
    local skeleton="$5"
    local license_choice="$6"

    local full_path="$project_root/$project_name"

    print_status "info" "Creating project '$project_name' under '$project_root'"
    print_status "config" "Full path: $full_path"

    if [ "$lang" != "python" ]; then
        exit_error "Language '$lang' not supported yet."
    fi

    case "$skeleton" in
        "ddd-service-native-db")
            LICENSE_CHOICE="$license_choice" bash "$SCRIPT_DIR/scaffold/python_ddd_service.sh" "$project_root" "$project_name" "$project_description"
            ;;
        "ddd-service-orm-db")
            LICENSE_CHOICE="$license_choice" bash "$SCRIPT_DIR/scaffold/python_ddd_service_orm.sh" "$project_root" "$project_name" "$project_description"
            ;;
        "lib-minimal")
            LICENSE_CHOICE="$license_choice" bash "$SCRIPT_DIR/scaffold/python_lib_minimal.sh" "$project_root" "$project_name" "$project_description"
            ;;
        *)
            exit_error "Unknown skeleton '$skeleton'."
            ;;
    esac
}

# ============================================================================
# MAIN
# ============================================================================

run_create_flow() {
    PROJECT_NAME=$(prompt_project_name)
    PROJECT_DESCRIPTION=$(prompt_project_description)

    if [ "$DRY_RUN" -eq 1 ]; then
        PROJECT_ROOT="(dry-run)"
    elif [ "$DEV_MODE" -eq 1 ]; then
        TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/BlueprintX.XXXXXX")
        PROJECT_ROOT="$TEMP_ROOT"
        print_status "config" "Dev mode: using temp root $PROJECT_ROOT"
        if [ "$CLEAN_TEMP" -eq 1 ]; then
            trap "rm -rf '$TEMP_ROOT'" EXIT
            print_status "info" "Temp directory will be cleaned on exit"
        fi
    else
        PROJECT_ROOT=$(prompt_project_root)
    fi

    LANG_CHOICE=$(prompt_language)
    SKELETON_CHOICE=$(prompt_skeleton)
    LICENSE_CHOICE=$(prompt_license)

    if [ "$DRY_RUN" -eq 1 ]; then
        print_status "info" "Dry-run: showing structure for '$SKELETON_CHOICE'"
        show_skeleton_structure "$SKELETON_CHOICE"
        exit 0
    fi

    create_project "$PROJECT_ROOT" "$PROJECT_NAME" "$PROJECT_DESCRIPTION" "$LANG_CHOICE" "$SKELETON_CHOICE" "$LICENSE_CHOICE"

    echo
    printf "${GREEN}╔════════════════════════════════════════╗${NC}\n"
    printf "${GREEN}║   ✓ Project created successfully!      ║${NC}\n"
    printf "${GREEN}╚════════════════════════════════════════╝${NC}\n"
    echo
    print_status "config" "Project: $PROJECT_NAME"
    print_status "config" "Location: $PROJECT_ROOT/$PROJECT_NAME"
    print_status "config" "Skeleton: $SKELETON_CHOICE"
    print_status "config" "License: $LICENSE_CHOICE"
    if [ "$DEV_MODE" -eq 1 ]; then
        print_status "warning" "Dev mode: project scaffolded in temp directory"
        if [ "$CLEAN_TEMP" -ne 1 ]; then
            print_status "info" "Temp directory preserved at: $TEMP_ROOT"
        fi
    fi
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

    read -r -p "$(printf "    ${CYAN}Choose an option [1-4]: ${NC}")" choice

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
            read -r -p "Do you want to proceed to create a project now? [Y/n] " go_create
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

main
