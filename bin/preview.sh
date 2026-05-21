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
    print_status "config" "  * mvc-service-native-db (layered MVC, native DB libraries)"
    print_status "config" "  * mvc-service-orm-db (layered MVC, SQLAlchemy ORM)"
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
    ... (same common files as native-db)
EOF
}

show_mvc_native() {
    echo
    print_section "mvc-service-native-db skeleton"

    print_status "info" "Description:"
    print_status "config" "Layered Model-View-Controller structure for script/pipeline projects,"
    print_status "config" "using native DB drivers. Flatter than DDD; model returns pandas DataFrames."
    echo
    print_status "info" "Example structure:"
    cat << 'EOF'
  project/
    src/
      controller/
        main.py           # script-style: config -> model -> view
      model/
        conexao_db.py     # build_connection() — native DB-API factory
        example_entity.py # SQL in, pandas DataFrame out
      view/
        report_renderer.py  # RenderToExcel — DataFrame -> .xlsx
      utils/
      config/             # startup.py singletons + YAML (shared with DDD)
    tests/
      integration/
      performance/
      unit/
    bin/
    data/
    assets/
    docs/
    ... (same common files as the other Python skeletons)
EOF
}

show_mvc_orm() {
    echo
    print_section "mvc-service-orm-db skeleton"

    print_status "info" "Description:"
    print_status "config" "Same layered MVC structure as native-db, but the model uses the"
    print_status "config" "SQLAlchemy ORM. Supports PostgreSQL, MySQL, SQLite, Oracle, MSSQL."
    echo
    print_status "info" "Key differences from mvc native-db:"
    print_status "config" "  - build_engine() / build_session_factory() instead of raw connection"
    print_status "config" "  - DeclarativeBase + ORM models; reads via pd.read_sql"
    echo
    print_status "info" "Example structure:"
    cat << 'EOF'
  project/
    src/
      controller/
        main.py
      model/
        conexao_db.py     # build_engine() / build_session_factory()
        example_entity.py # DeclarativeBase + ORM model + service class
      view/
        report_renderer.py
      utils/
      config/
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

main() {
    show_languages
    show_hex_service
    show_orm_service
    show_mvc_native
    show_mvc_orm
    show_lib_minimal
    echo
    print_status "success" "Preview complete."
}

main
