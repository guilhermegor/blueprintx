#!/usr/bin/env bash
#
# lint_sql.sh — sqlfluff over the project's SQL query files.
#
# Single source of truth for SQL linting: called by both `make lint` / `./tasks.sh lint`
# and the pre-commit `lint-sql` hook. Lints every `.sql` under src/config/queries with the
# default dialect from .sqlfluff (sqlfluff honours .sqlfluffignore for runtime-templated
# queries). sqlfluff is a poetry dev-dep, so this is GUARDED on `command -v poetry` and
# SKIPPED gracefully (exit 0) when absent — a constrained box never hard-fails.
#
# Mixing engines? Encode the db in each query's filename prefix and run one sqlfluff pass
# per --dialect here (see the .sqlfluff header comment).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

cd "$SCRIPT_DIR/.."

str_queries="src/config/queries"

if ! command -v poetry >/dev/null 2>&1; then
	print_status warning "skip: poetry/sqlfluff unavailable for SQL lint"
	exit 0
fi

if [[ ! -d "$str_queries" ]] || [[ -z "$(find "$str_queries" -name '*.sql' -type f -print -quit)" ]]; then
	print_status info "no .sql files under $str_queries — skipping"
	exit 0
fi

print_status info "sqlfluff lint $str_queries"
poetry run sqlfluff lint "$str_queries"
print_status success "sqlfluff OK"
