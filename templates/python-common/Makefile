# -------------------
# VIRTUAL ENVIRONMENT
# -------------------
.PHONY: init venv update_venv precommit

init: venv precommit

venv:
	@PY_VERSION=$$(cat .python-version 2>/dev/null || echo "3.11.12"); \
	pyenv install $$PY_VERSION -s; \
	pyenv local $$PY_VERSION; \
	python -m pip install --upgrade pip; \
	python -m pip install -r requirements.txt; \
	poetry config virtualenvs.in-project true --local; \
	poetry install; \
	echo "Virtual environment created in ./.venv"; \
	echo "Poetry project installed"; \
	poetry run playwright install; \
	echo "Playwright installed"

update_venv:
	@poetry update
	@echo "Poetry project updated"

precommit:
	@poetry run pre-commit install
	@poetry run pre-commit install --hook-type commit-msg

# -------------------
# TESTING
# -------------------
.PHONY: unit_tests integration_tests test_cov test_slowest test_feat test_urls_docstrings fix_playwright

unit_tests:
	@poetry run pytest tests/unit/

integration_tests:
	@poetry run pytest tests/integration/

test_cov:
	@poetry run pytest tests/unit/ --cov=src
	@poetry run coverage report -m
	@poetry run coverage-badge -o coverage.svg -f

test_slowest:
	@echo "Running tests to identify the 20 slowest tests..."
	@poetry run pytest tests/unit/ --durations=20 --tb=short

test_feat:
	@poetry run pytest tests/unit/ -k "$(FEAT)"

test_urls_docstrings:
	@bash bin/test_urls_docstrings.sh

fix_playwright:
	@bash bin/fix_playwright.sh

# -------------------
# LINTING
# -------------------
.PHONY: lint check_consistency

lint:
	@poetry run ruff check --fix .
	@poetry run ruff format .
	@poetry run codespell .
	@poetry run pydocstyle .
	@poetry run python bin/check_consistency.py

check_consistency:
	@poetry run python bin/check_consistency.py

# -------------------
# RUN
# -------------------
.PHONY: start

start:
	@bash bin/start.sh

# -------------------
# DOCS
# -------------------
.PHONY: docs_server

docs_server:
	@poetry install --with docs
	@poetry run mkdocs serve -a 0.0.0.0:8000 --livereload

# -------------------
# HELP
# -------------------
.PHONY: help

help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Virtual Environment"
	@echo "  init                 Bootstrap venv + install pre-commit hooks"
	@echo "  venv                 Create Poetry venv and install Playwright"
	@echo "  update_venv          Update all Poetry dependencies"
	@echo "  precommit            Install pre-commit hooks (push + commit-msg)"
	@echo ""
	@echo "Testing"
	@echo "  unit_tests           Run unit tests with pytest"
	@echo "  integration_tests    Run integration tests with pytest"
	@echo "  test_cov             Run unit tests with coverage report and badge"
	@echo "  test_slowest         Report the 20 slowest unit tests"
	@echo "  test_feat FEAT=<kw>  Run unit tests matching keyword <kw>"
	@echo "  test_urls_docstrings Check all URLs inside docstrings"
	@echo "  fix_playwright       Reinstall Playwright browsers"
	@echo ""
	@echo "Linting"
	@echo "  lint                 Run ruff, codespell, pydocstyle, check_consistency"
	@echo "  check_consistency    Check docstring type/raises consistency"
	@echo ""
	@echo "Docs"
	@echo "  docs_server          Serve MkDocs site locally at http://0.0.0.0:8000"
	@echo ""
	@echo "Run"
	@echo "  start                Run src/main.py (auto-installs Poetry if missing)"
	@echo ""
