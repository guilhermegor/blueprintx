.PHONY: init preview dev dev-clean dry-run

init:
	@bash scripts/blueprintx.sh

preview:
	@bash scripts/preview.sh

dev:
	@bash scripts/blueprintx.sh --dev

dev-clean:
	@bash scripts/blueprintx.sh --dev --clean

dry-run:
	@bash scripts/blueprintx.sh --dry-run
