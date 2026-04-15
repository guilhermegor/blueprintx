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
    print_status "config" "  * ddd-service-native-db (native DB libraries)"
    print_status "config" "  * ddd-service-orm-db (SQLAlchemy ORM)"
    print_status "config" "  * lib-minimal"
    print_status "info" "Common Python assets applied to all skeletons:"
    print_status "config" "  * pyproject.toml (name from prompt, version 0.0.1 default, optional description)"
    print_status "config" "  * .pre-commit-config.yaml, requirements.txt"
    print_status "config" "  * .github/workflows (PR + tests), CODEOWNERS, PULL_REQUEST_TEMPLATE"
    print_status "config" "  * tests/{integration,performance,unit}"
    echo
    print_status "info" "2) cancel"
    print_status "config" "Exit without creating a project"
}

show_hex_service() {
    echo
    print_section "ddd-service-native-db skeleton"
    
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
        application/
      modules/
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
    scripts/
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
      core/
        domain/
        infrastructure/
          database/
            base.py         # SQLAlchemy base, session manager
            models.py       # ORM models
            repository.py   # Generic SQLAlchemy repository
        application/
      modules/
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
    ... (same common files as native-db)
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
    scripts/
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

main() {
    show_languages
    show_hex_service
    show_orm_service
    show_lib_minimal
    echo
    print_status "success" "Preview complete."
}

main
