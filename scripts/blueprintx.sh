#!/usr/bin/env bash

set -e

DEV_MODE=0
DRY_RUN=0
CLEAN_TEMP=0
TEMP_ROOT=""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/logging.sh"

# =========================================================================
# ARG PARSING
# =========================================================================

print_usage() {
    echo "Usage: $0 [--dev] [--dry-run] [--clean]"
    echo
    echo "Options:"
    echo "  --dev        Create project in a temporary directory"
    echo "  --dry-run    Only preview structure; do not scaffold"
    echo "  --clean      When combined with --dev, delete the temp directory on exit"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
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
        *)
            echo "Unknown option: $1" >&2
            print_usage
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
    printf "  ${YELLOW}2) ?${NC}  Help (what can blueprintx do?)\n"
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
    print_status "info" "  make init"
    echo
    print_status "info" "Then choose 'Create a project' in the menu."
    echo
    print_status "info" "You can also run in dev/preview modes:"
    print_status "config" "  scripts/blueprintx.sh --dev      # scaffold into a temp dir"
    print_status "config" "  scripts/blueprintx.sh --dry-run  # preview only, no files created"
}

show_hex_service() {
        echo
        print_section "hex-service skeleton"
        print_status "info" "Description:"
        print_status "config" "Backend/service-oriented structure with core/modules separation,"
        print_status "config" "suitable for APIs and services using clean/hexagonal-ish design."
        echo
        print_status "info" "Example structure:"
        cat << 'EOF'
    project/
        src/
            core/
                domain/
                infrastructure/
                services/
            modules/
                example_feature/
                    domain/
                    services/
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
        public/
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
            settings.json
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
            settings.json
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
    local repo_root
    repo_root="$(cd "$SCRIPT_DIR/.." && pwd)"
    local default_parent
    default_parent="$(cd "$repo_root/.." && pwd)"

    printf "${CYAN}Select directory${NC}\n" >&2
    printf "  1) Parent of repo ($default_parent)\n" >&2
    printf "  2) Another directory\n" >&2
    printf "${CYAN}Choice${NC} [1-2]: " >&2
    read -r choice
    printf "\n" >&2
    
    case "$choice" in
        1)
            echo "$default_parent"
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
        "hex-service")
            show_hex_service
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
    printf "  ${BLUE}1) hex-service${NC} (default)\n" >&2
    printf "  ${BLUE}2) lib-minimal${NC}\n" >&2
    printf "${CYAN}Choice${NC} [1-2]: " >&2
    read -r choice
    printf "\n" >&2
    
    case "$choice" in
        1)
            echo "hex-service"
            return 0
            ;;
        2)
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

create_project() {
    local project_root="$1"
    local project_name="$2"
    local project_description="$3"
    local lang="$4"
    local skeleton="$5"
    
    local full_path="$project_root/$project_name"
    
    print_status "info" "Creating project '$project_name' under '$project_root'"
    print_status "config" "Full path: $full_path"
    
    if [ "$lang" != "python" ]; then
        exit_error "Language '$lang' not supported yet."
    fi
    
    case "$skeleton" in
        "hex-service")
            bash "$SCRIPT_DIR/scaffold/python_hex_service.sh" "$project_root" "$project_name" "$project_description"
            ;;
        "lib-minimal")
            bash "$SCRIPT_DIR/scaffold/python_lib_minimal.sh" "$project_root" "$project_name" "$project_description"
            ;;
        *)
            exit_error "Unknown skeleton '$skeleton'."
            ;;
    esac
}

# ============================================================================
# MAIN
# ============================================================================

main() {
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
    
    PROJECT_NAME=$(prompt_project_name)
    PROJECT_DESCRIPTION=$(prompt_project_description)

    if [ "$DRY_RUN" -eq 1 ]; then
        PROJECT_ROOT="(dry-run)"
    elif [ "$DEV_MODE" -eq 1 ]; then
        TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/blueprintx.XXXXXX")
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

    if [ "$DRY_RUN" -eq 1 ]; then
        print_status "info" "Dry-run: showing structure for '$SKELETON_CHOICE'"
        show_skeleton_structure "$SKELETON_CHOICE"
        exit 0
    fi

    create_project "$PROJECT_ROOT" "$PROJECT_NAME" "$PROJECT_DESCRIPTION" "$LANG_CHOICE" "$SKELETON_CHOICE"
    
    echo
    printf "${GREEN}╔════════════════════════════════════════╗${NC}\n"
    printf "${GREEN}║   ✓ Project created successfully!      ║${NC}\n"
    printf "${GREEN}╚════════════════════════════════════════╝${NC}\n"
    echo
    print_status "config" "Project: $PROJECT_NAME"
    print_status "config" "Location: $PROJECT_ROOT/$PROJECT_NAME"
    print_status "config" "Skeleton: $SKELETON_CHOICE"
    if [ "$DEV_MODE" -eq 1 ]; then
        print_status "warning" "Dev mode: project scaffolded in temp directory"
        if [ "$CLEAN_TEMP" -ne 1 ]; then
            print_status "info" "Temp directory preserved at: $TEMP_ROOT"
        fi
    fi
    print_status "info" "Log file: $LOG_FILE"
}

main
