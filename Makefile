.PHONY: new install preview dev dev_clean dry_run dev-clean dry-run

new:
	@bash bin/blueprintx.sh

install:
	$(eval VERSION := $(shell git describe --tags --always 2>/dev/null | sed 's/^v//'))
	@sudo rsync -a --delete bin/ /usr/share/blueprintx/bin/
	@sudo rsync -a --delete templates/ /usr/share/blueprintx/templates/
	@sudo sed -i "s/^BLUEPRINTX_VERSION=\".*\"/BLUEPRINTX_VERSION=\"$(VERSION)\"/" /usr/share/blueprintx/bin/blueprintx.sh
	@echo "Installed blueprintx $(VERSION) to /usr/share/blueprintx"

preview:
	@bash bin/preview.sh

dev:
	@bash bin/blueprintx.sh --dev

dev_clean:
	@bash bin/blueprintx.sh --dev --clean

dry_run:
	@bash bin/blueprintx.sh --dry-run

dev-clean: dev_clean
dry-run: dry_run

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

.PHONY: lint check_function_length verify_tiers

lint:
	@poetry run pre-commit run --all-files

verify_tiers:
	@bash bin/ci/scaffold_lint_test_all.sh $(if $(JOBS),--jobs $(JOBS),)

check_function_length:
	@python3 templates/python-common/bin/check_function_length.py --root .

.PHONY: mkdocs_serve mkdocs_server changelog

mkdocs_serve:
	@poetry install --with docs
	@poetry run mkdocs serve -a 0.0.0.0:8000 --livereload

# pairing:internal
mkdocs_server: mkdocs_serve

changelog:
	@poetry run cz changelog
	@echo "Regenerated CHANGELOG.md"

.PHONY: update_licenses

update_licenses:
	@bash bin/update_licenses.sh

.PHONY: help

help:
	@bash bin/help.sh
