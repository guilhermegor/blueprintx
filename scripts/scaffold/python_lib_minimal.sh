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
    
    mkdir -p "$project_path"/src/"$PROJECT_NAME"
    mkdir -p "$project_path"/tests
    mkdir -p "$project_path"/docs
    
    print_status "success" "Directory structure created"
}

create_python_files() {
    local project_path="$1"
    
    print_status "info" "Creating Python files..."
    
    touch "$project_path"/src/"$PROJECT_NAME"/__init__.py
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/main.py" "$project_path/src/$PROJECT_NAME/main.py"
    
    # Create test file with project name substitution
    sed "s/\${PROJECT_NAME}/$PROJECT_NAME/g" << 'EOF' > "$project_path/tests/test_main.py"
from ${PROJECT_NAME}.main import main

def test_main(capsys):
    main()
    captured = capsys.readouterr()
    assert "Hello from lib-minimal!" in captured.out
EOF
    
    print_status "success" "Python files created"
}

copy_templates() {
    local project_path="$1"
    
    print_status "info" "Copying templates..."
    
    sed "s/\${PROJECT_NAME}/$PROJECT_NAME/g" "$BLUEPRINTX_ROOT/templates/lib-minimal/pyproject.toml" > "$project_path/pyproject.toml"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.gitignore" "$project_path/.gitignore"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.env" "$project_path/.env"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.python-version" "$project_path/.python-version"
    sed "s/\${PROJECT_NAME}/$PROJECT_NAME/g" "$BLUEPRINTX_ROOT/templates/lib-minimal/README.md" > "$project_path/README.md"
    
    # Create docs/index.md with project name
    sed "s/\${PROJECT_NAME}/$PROJECT_NAME/g" << 'EOF' > "$project_path/docs/index.md"
# ${PROJECT_NAME}

Minimal library generated with blueprintx (lib-minimal).
EOF
    
    print_status "success" "Templates copied and configured"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    PROJECT_PATH="$PROJECT_ROOT/$PROJECT_NAME"
    
    print_section "Python lib-minimal scaffold"
    print_status "config" "Target: $PROJECT_PATH"
    
    validate_inputs
    create_directory_structure "$PROJECT_PATH"
    create_python_files "$PROJECT_PATH"
    copy_templates "$PROJECT_PATH"
    
    print_status "success" "Lib-minimal scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
}

main
