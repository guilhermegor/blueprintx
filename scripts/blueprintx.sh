#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/logging.sh"

# ============================================================================
# FUNCTIONS
# ============================================================================

show_banner() {
    echo
    printf "${MAGENTA}    ╔══════════════════════════════════════════════╗${NC}\n"
    printf "${MAGENTA}    ║${NC}                                              ${MAGENTA}║${NC}\n"
    printf "${MAGENTA}    ║${NC}  ${CYAN}██████╗ ██╗     ██╗   ██╗███████╗           ${MAGENTA}║${NC}\n"
    printf "${MAGENTA}    ║${NC}  ${CYAN}██╔══██╗██║     ██║   ██║██╔════╝           ${MAGENTA}║${NC}\n"
    printf "${MAGENTA}    ║${NC}  ${CYAN}██████╔╝██║     ██║   ██║█████╗             ${MAGENTA}║${NC}\n"
    printf "${MAGENTA}    ║${NC}  ${CYAN}██╔══██╗██║     ██║   ██║██╔══╝             ${MAGENTA}║${NC}\n"
    printf "${MAGENTA}    ║${NC}  ${CYAN}██████╔╝███████╗╚██████╔╝███████╗           ${MAGENTA}║${NC}\n"
    printf "${MAGENTA}    ║${NC}  ${CYAN}╚═════╝ ╚══════╝ ╚═════╝ ╚══════╝           ${MAGENTA}║${NC}\n"
    printf "${MAGENTA}    ║${NC}                                              ${MAGENTA}║${NC}\n"
    printf "${MAGENTA}    ║${NC}      ${GREEN}Blueprints. Expansible.${MAGENTA}                 ║${NC}\n"
    printf "${MAGENTA}    ║${NC}                                              ${MAGENTA}║${NC}\n"
    printf "${MAGENTA}    ╚══════════════════════════════════════════════╝${NC}\n"
    echo
}

show_main_menu() {
    show_banner
    echo
    printf "${MAGENTA}    ┌──────────────────────────────────────────────────────────┐${NC}\n"
    printf "${MAGENTA}    │${NC} ${BLUE}What would you like to do?${MAGENTA}${NC}                                       ${MAGENTA}│${NC}\n"
    printf "${MAGENTA}    ├──────────────────────────────────────────────────────────┤${NC}\n"
    printf "${MAGENTA}    │${NC}                                                          ${MAGENTA}│${NC}\n"
    printf "${MAGENTA}    │${NC}    ${GREEN}1) ➜${NC}  Create a project                              ${MAGENTA}│${NC}\n"
    printf "${MAGENTA}    │${NC}    ${YELLOW}2) ?${NC}  Help (what can blueprintx do?)              ${MAGENTA}│${NC}\n"
    printf "${MAGENTA}    │${NC}    ${BLUE}3) ▦${NC}  Show scaffolding structures and examples    ${MAGENTA}│${NC}\n"
    printf "${MAGENTA}    │${NC}    ${RED}4) ✕${NC}  Cancel                                       ${MAGENTA}│${NC}\n"
    printf "${MAGENTA}    │${NC}                                                          ${MAGENTA}│${NC}\n"
    printf "${MAGENTA}    └──────────────────────────────────────────────────────────┘${NC}\n"
    echo
}

show_help() {
    echo
    print_status "info" "Blueprintx is a lightweight scaffolding tool based on Make + bash."
    print_status "info" "It can currently:"
    print_status "info" "  - Create Python projects with different folder structures (skeletons)"
    print_status "info" "  - Ask interactively for language, project name, target directory, and structure"
    print_status "info" "  - Generate Python-ready projects that use pyenv + uv (inside the generated project)"
    echo
    print_status "info" "To create a project, run:"
    print_status "info" "  make init"
    echo
    print_status "info" "Then choose 'Create a project' in the menu."
}

prompt_project_name() {
    printf "${CYAN}Project name${NC} (folder name): " >&2
    read -r PROJECT_NAME
    if [ -z "$PROJECT_NAME" ]; then
        exit_error "Project name cannot be empty."
    fi
    echo "$PROJECT_NAME"
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
    local lang="$3"
    local skeleton="$4"
    
    local full_path="$project_root/$project_name"
    
    print_status "info" "Creating project '$project_name' under '$project_root'"
    print_status "config" "Full path: $full_path"
    
    if [ "$lang" != "python" ]; then
        exit_error "Language '$lang' not supported yet."
    fi
    
    case "$skeleton" in
        "hex-service")
            bash "$SCRIPT_DIR/scaffold/python_hex_service.sh" "$project_root" "$project_name"
            ;;
        "lib-minimal")
            bash "$SCRIPT_DIR/scaffold/python_lib_minimal.sh" "$project_root" "$project_name"
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
    PROJECT_ROOT=$(prompt_project_root)
    LANG_CHOICE=$(prompt_language)
    SKELETON_CHOICE=$(prompt_skeleton)
    
    create_project "$PROJECT_ROOT" "$PROJECT_NAME" "$LANG_CHOICE" "$SKELETON_CHOICE"
    
    echo
    printf "${GREEN}╔════════════════════════════════════════╗${NC}\n"
    printf "${GREEN}║   ✓ Project created successfully!     ║${NC}\n"
    printf "${GREEN}╚════════════════════════════════════════╝${NC}\n"
    echo
    print_status "config" "Project: $PROJECT_NAME"
    print_status "config" "Location: $PROJECT_ROOT/$PROJECT_NAME"
    print_status "config" "Skeleton: $SKELETON_CHOICE"
    print_status "info" "Log file: $LOG_FILE"
}

main
