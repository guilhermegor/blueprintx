# -------------------
# BLUEPRINTX SCRIPTS
# -------------------
.PHONY: new install preview dev dev-clean dry-run

new:
	@bash bin/blueprintx.sh

# Install from this clone into /usr/share/blueprintx. That path has no .git, so the installed
# `blueprintx --version` can't derive the tag at runtime — stamp the clone's current
# `git describe` version into the installed script (mirroring what the package-manager jobs do),
# so every install path reports the same tag-derived version with no hand-bump.
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

dev-clean:
	@bash bin/blueprintx.sh --dev --clean

dry-run:
	@bash bin/blueprintx.sh --dry-run

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
.PHONY: lint check_function_length verify_tiers

lint:
	@poetry run pre-commit run --all-files

# The real verification for template work: scaffold every Python tier and run THAT project's
# own lint + tests. Runs the tiers in parallel, each in its own sandbox — pass JOBS=1 to
# serialise while debugging. `make lint` does NOT cover this; a template defect is only visible
# from inside a generated project (blueprintx#276).
verify_tiers:
	@bash bin/ci/scaffold_lint_test_all.sh $(if $(JOBS),--jobs $(JOBS),)

# Also reachable on its own, so a contributor can check the one rule without paying for the
# whole hook set. `make lint` covers it via the pre-commit hook.
check_function_length:
	@python3 templates/python-common/bin/check_function_length.py --root .

# -------------------
# DOCS
# -------------------
.PHONY: mkdocs_server changelog

mkdocs_server:
	@poetry install --with docs
	@poetry run mkdocs serve -a 0.0.0.0:8000 --livereload

# Regenerate the root CHANGELOG.md from the conventional-commit / git-tag history. The docs
# Changelog page single-sources this file via a snippets include; CI regenerates it fresh on
# every docs build (never committed back). Run this to preview locally. Do not hand-edit CHANGELOG.md.
changelog:
	@poetry run cz changelog
	@echo "Regenerated CHANGELOG.md"

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
