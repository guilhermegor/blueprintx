#!/usr/bin/env bash
#
# lint_yaml.sh — yamllint over the repo's YAML files.
#
# Single source of truth for YAML style linting: called by both `make lint` / `./tasks.sh
# lint` and the pre-commit `yamllint` hook. yamllint is a poetry dev-dep, so this is GUARDED
# on `command -v poetry` and SKIPPED gracefully (exit 0) when poetry is absent — a constrained
# box never hard-fails. When poetry IS present, yamllint's real exit status propagates (a true
# style failure fails the gate; it is never masked).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

cd "$SCRIPT_DIR/.."

if ! command -v poetry >/dev/null 2>&1; then
	print_status warning "skip: poetry/yamllint unavailable for YAML lint"
	exit 0
fi

print_status info "yamllint ."
poetry run yamllint .
print_status success "yamllint OK"
