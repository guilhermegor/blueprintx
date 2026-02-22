
.PHONY: init preview dev dev-clean dry-run init_venv update_venv mkdocs-serve mkdocs-build

PY_VERSION := $(shell cat .python-version 2>/dev/null || echo 3.12.0)
WIKI_REPO ?= https://github.com/guilhermegor/BlueprintX.wiki.git

# -------------------
# BLUEPRINTX SCRIPTS
# -------------------

init:
	@bash scripts/BlueprintX.sh

preview:
	@bash scripts/preview.sh

dev:
	@bash scripts/BlueprintX.sh --dev

dev-clean:
	@bash scripts/BlueprintX.sh --dev --clean

dry-run:
	@bash scripts/BlueprintX.sh --dry-run

# -------------------
# DEV ENVIRONMENT
# -------------------
init-venv:
	@if [ -z "$(PY_VERSION)" ]; then echo "PY_VERSION is empty; set .python-version"; exit 1; fi
	@if command -v pyenv >/dev/null 2>&1; then \
		if ! pyenv versions --bare | grep -Fx "$(PY_VERSION)" >/dev/null 2>&1; then \
			pyenv install "$(PY_VERSION)"; \
		fi; \
		pyenv local "$(PY_VERSION)"; \
	else \
		echo "pyenv not found; using current Python"; \
	fi
	@python -m pip install --upgrade pip
	@[ ! -f requirements.txt ] || python -m pip install -r requirements.txt
	@poetry config virtualenvs.in-project true --local
	@poetry install
	@echo "Virtual environment created in ./.venv"
	@echo "Poetry project installed"

update-venv:
	@poetry update
	@echo "Poetry project updated"

mkdocs-serve:
	@poetry install --with docs
	@poetry run mkdocs serve -a 0.0.0.0:8000 --livereload

mkdocs-build:
	@poetry run mkdocs build