
.PHONY: new preview dev dev-clean dry-run bump_version init_venv init_venv update_venv update_venv mkdocs_server update_licenses help install

WIKI_REPO ?= https://github.com/guilhermegor/BlueprintX.wiki.git

# -------------------
# BLUEPRINTX SCRIPTS
# -------------------

new:
	@bash bin/blueprintx.sh

install:
	@sudo rsync -a bin/ /usr/share/blueprintx/bin/
	@sudo rsync -a templates/ /usr/share/blueprintx/templates/
	@echo "Installed to /usr/share/blueprintx"

preview:
	@bash bin/preview.sh

dev:
	@bash bin/blueprintx.sh --dev

dev-clean:
	@bash bin/blueprintx.sh --dev --clean

dry-run:
	@bash bin/blueprintx.sh --dry-run

bump_version:
	@bash bin/bump_version.sh

# -------------------
# DEV ENVIRONMENT
# -------------------
init_venv:
	@bash bin/init_venv.sh

update_venv:
	@poetry update
	@echo "Poetry project updated"

mkdocs_server:
	@poetry install --with docs
	@poetry run mkdocs serve -a 0.0.0.0:8000 --livereload

update_licenses:
	@bash bin/update_licenses.sh

help:
	@bash bin/help.sh