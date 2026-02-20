#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/logging.sh"

PROJECT_ROOT="$1"
PROJECT_NAME="$2"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ============================================================================
# FUNCTIONS
# ============================================================================

validate_inputs() {
    if [ -z "$PROJECT_ROOT" ] || [ -z "$PROJECT_NAME" ]; then
        exit_error "Usage: $0 <project_root_dir> <project_name>"
    fi
    print_status "success" "Input validation passed"
}

create_directory_structure() {
    local project_path="$1"
    
    print_status "info" "Creating directory structure..."
    
    mkdir -p "$project_path"/src/core/domain
    mkdir -p "$project_path"/src/core/infrastructure
    mkdir -p "$project_path"/src/core/services
    mkdir -p "$project_path"/src/modules
    mkdir -p "$project_path"/src/utils
    mkdir -p "$project_path"/src/config
    mkdir -p "$project_path"/tests
    mkdir -p "$project_path"/public
    mkdir -p "$project_path"/scripts
    mkdir -p "$project_path"/docs
    
    print_status "success" "Directory structure created"
}

create_python_files() {
    local project_path="$1"
    
    print_status "info" "Creating Python files..."
    
    touch "$project_path"/src/__init__.py
    touch "$project_path"/src/core/__init__.py
    touch "$project_path"/src/modules/__init__.py
    touch "$project_path"/src/utils/__init__.py
    touch "$project_path"/src/config/__init__.py
    
    cp "$BLUEPRINTX_ROOT/templates/hex-service/main.py" "$project_path/src/main.py"
    
    print_status "success" "Python files created"
}

copy_templates() {
    local project_path="$1"
    
    print_status "info" "Copying templates..."
    
    sed "s/\${PROJECT_NAME}/$PROJECT_NAME/g" "$BLUEPRINTX_ROOT/templates/hex-service/pyproject.toml" > "$project_path/pyproject.toml"
    cp "$BLUEPRINTX_ROOT/templates/hex-service/.gitignore" "$project_path/.gitignore"
    cp "$BLUEPRINTX_ROOT/templates/hex-service/.env" "$project_path/.env"
    cp "$BLUEPRINTX_ROOT/templates/hex-service/.python-version" "$project_path/.python-version"
    sed "s/\${PROJECT_NAME}/$PROJECT_NAME/g" "$BLUEPRINTX_ROOT/templates/hex-service/README.md" > "$project_path/README.md"
    
    print_status "success" "Templates copied and configured"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    PROJECT_PATH="$PROJECT_ROOT/$PROJECT_NAME"
    
    print_section "Python hex-service scaffold"
    print_status "config" "Target: $PROJECT_PATH"
    
    validate_inputs
    create_directory_structure "$PROJECT_PATH"
    create_python_files "$PROJECT_PATH"
    copy_templates "$PROJECT_PATH"
    
    print_status "success" "Hex-service scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
}

main
