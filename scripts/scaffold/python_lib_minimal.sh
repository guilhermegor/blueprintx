#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/logging.sh"

PROJECT_ROOT="$1"
PROJECT_NAME="$2"
PROJECT_DESCRIPTION="${3:-}"
PROJECT_VERSION="${4:-0.0.1}"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMMON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/python-common"

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
    mkdir -p "$project_path"/tests/integration
    mkdir -p "$project_path"/tests/performance
    mkdir -p "$project_path"/tests/unit
    mkdir -p "$project_path"/container
    mkdir -p "$project_path"/bin
    mkdir -p "$project_path"/docs
    mkdir -p "$project_path"/.github/workflows
    mkdir -p "$project_path"/.vscode
    
    print_status "success" "Directory structure created"
}

create_python_files() {
    local project_path="$1"
    
    print_status "info" "Creating Python files..."
    
    touch "$project_path"/src/"$PROJECT_NAME"/__init__.py
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/main.py" "$project_path/src/$PROJECT_NAME/main.py"
    
    # Create test file with project name substitution
    mkdir -p "$project_path/tests/unit"
    sed "s/\${PROJECT_NAME}/$PROJECT_NAME/g" << 'EOF' > "$project_path/tests/unit/test_main.py"
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
    
    cp "$COMMON_TEMPLATE_ROOT/.gitignore" "$project_path/.gitignore"
    cp "$COMMON_TEMPLATE_ROOT/.python-version" "$project_path/.python-version"
    cp "$COMMON_TEMPLATE_ROOT/README.md" "$project_path/README.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.env" "$project_path/.env"
    
    # Create docs/index.md with project name
    sed "s/\${PROJECT_NAME}/$PROJECT_NAME/g" << 'EOF' > "$project_path/docs/index.md"
# ${PROJECT_NAME}

Minimal library generated with blueprintx (lib-minimal).
EOF
    
    print_status "success" "Templates copied and configured"
}

copy_common_templates() {
    local project_path="$1"

    print_status "info" "Applying common Python templates..."

    export PROJECT_NAME PROJECT_VERSION PROJECT_DESCRIPTION
    envsubst < "$COMMON_TEMPLATE_ROOT/pyproject.toml" > "$project_path/pyproject.toml"

    cp "$COMMON_TEMPLATE_ROOT/.pre-commit-config.yaml" "$project_path/.pre-commit-config.yaml"
    cp "$COMMON_TEMPLATE_ROOT/requirements.txt" "$project_path/requirements.txt"
    cp "$COMMON_TEMPLATE_ROOT/.vscode/settings.json" "$project_path/.vscode/settings.json"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/tests.yaml" "$project_path/.github/workflows/tests.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/CODEOWNERS" "$project_path/.github/CODEOWNERS"
    cp "$COMMON_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
    
    print_status "success" "Common templates applied"
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
    copy_common_templates "$PROJECT_PATH"
    
    print_status "success" "Lib-minimal scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
}

main
