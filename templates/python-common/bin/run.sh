#!/usr/bin/env bash
# Run src/main.py via Poetry (installing the pinned version if absent, falling
# back to direct Python). Sources lib/bootstrap.sh for cross-platform interpreter
# resolution and optional corporate-CA wiring.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=bin/lib/bootstrap.sh
source "$SCRIPT_DIR/lib/bootstrap.sh"

main() {
	bootstrap_init
	wire_corporate_ca

	export PYTHONPATH=".:src"

	if ensure_poetry; then
		run_poetry run python -m src.main
	else
		print_status "warning" "Poetry unavailable — running directly with $PYTHON"
		"$PYTHON" -m src.main
	fi
}

main "$@"
