#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/logging.sh"

# ============================================================================
# FUNCTIONS
# ============================================================================

show_languages() {
    print_section "available languages"
    
    print_status "info" "1) python"
    print_status "config" "Status: supported"
    print_status "config" "Skeletons:"
    print_status "config" "  * hex-service (default)"
    print_status "config" "  * lib-minimal"
    echo
    print_status "info" "2) cancel"
    print_status "config" "Exit without creating a project"
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
      utils/
      config/
      main.py
    tests/
    public/
    scripts/
    docs/
    .env
    .gitignore
    README.md
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
      test_main.py
    docs/
      index.md
    pyproject.toml
    .env
    .gitignore
    README.md
EOF
}

main() {
    show_languages
    show_hex_service
    show_lib_minimal
    echo
    print_status "success" "Preview complete."
}

main
