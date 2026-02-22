
.PHONY: init preview dev dev-clean dry-run init_venv init-venv update_venv update-venv mkdocs-serve help

WIKI_REPO ?= https://github.com/guilhermegor/BlueprintX.wiki.git

# -------------------
# BLUEPRINTX SCRIPTS
# -------------------

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

# -------------------
# DEV ENVIRONMENT
# -------------------
init-venv:
	@bash scripts/init_venv.sh

update-venv:
	@poetry update
	@echo "Poetry project updated"

mkdocs-serve:
	@poetry install --with docs
	@poetry run mkdocs serve -a 0.0.0.0:8000 --livereload

help:
	@bash scripts/help.sh