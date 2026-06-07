WIKI_REPO ?= https://github.com/guilhermegor/BlueprintX.wiki.git

# -------------------
# BLUEPRINTX SCRIPTS
# -------------------
.PHONY: new install preview dev dev-clean dry-run bump_version

new:
	@bash bin/blueprintx.sh

install:
	@sudo rsync -a --delete bin/ /usr/share/blueprintx/bin/
	@sudo rsync -a --delete templates/ /usr/share/blueprintx/templates/
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
# VIRTUAL ENVIRONMENT
# -------------------
.PHONY: init venv update_venv precommit

init: venv precommit

venv:
	@bash bin/venv.sh

update_venv:
	@poetry update
	@echo "Poetry project updated"

precommit:
	@poetry run pre-commit install
	@poetry run pre-commit install --hook-type commit-msg

# -------------------
# LINTING
# -------------------
.PHONY: lint

lint:
	@poetry run pre-commit run --all-files

# -------------------
# DOCS
# -------------------
.PHONY: mkdocs_server

mkdocs_server:
	@poetry install --with docs
	@poetry run mkdocs serve -a 0.0.0.0:8000 --livereload

# -------------------
# LICENSES
# -------------------
.PHONY: update_licenses

update_licenses:
	@bash bin/update_licenses.sh

# -------------------
# HELP
# -------------------
.PHONY: help

help:
	@bash bin/help.sh
