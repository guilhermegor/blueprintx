
.PHONY: new preview dev dev-clean dry-run init_venv init-venv update_venv update_venv mkdocs-serve help

WIKI_REPO ?= https://github.com/guilhermegor/BlueprintX.wiki.git

# -------------------
# BLUEPRINTX SCRIPTS
# -------------------

new:
	@bash bin/blueprintx.sh

preview:
	@bash bin/preview.sh

dev:
	@bash bin/blueprintx.sh --dev

dev-clean:
	@bash bin/blueprintx.sh --dev --clean

dry-run:
	@bash bin/blueprintx.sh --dry-run

# -------------------
# DEV ENVIRONMENT
# -------------------
init-venv:
	@bash bin/init_venv.sh

update_venv:
	@poetry update
	@echo "Poetry project updated"

mkdocs-serve:
	@poetry install --with docs
	@poetry run mkdocs serve -a 0.0.0.0:8000 --livereload

help:
	@bash bin/help.sh