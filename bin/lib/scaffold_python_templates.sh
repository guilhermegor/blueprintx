#!/usr/bin/env bash
# Shared "copy the common Python templates" step for the four service scaffolds.
#
# WHY THIS FILE EXISTS. `copy_common_templates` was 95 lines duplicated across
# python_ddd_service.sh, python_ddd_service_orm.sh, python_mvc_service.sh and
# python_mvc_service_orm.sh. Measured with `diff`, the four copies differed by
# EXACTLY ONE TOKEN each -- the tier directory name, in two lines out of 95:
#
#   envsubst < "$BLUEPRINTX_ROOT/templates/<TIER>/pyproject.toml" > ...
#   cp        "$BLUEPRINTX_ROOT/templates/<TIER>/.vscode/tasks.json" ...
#
# So 285 lines existed to vary one word. That is the copy-list drift this repo keeps
# paying for: a file added to python-common reaches a tier only if someone remembers to
# add a `cp` line in each of four places, and the tier that gets forgotten fails nowhere.
#
# WHY IT IS SPLIT INTO FOUR. Merging the copies would still leave one 95-line function,
# which the 60-line gate rejects for the same reason a reader would: a flat wall of `cp`
# has no seams to navigate by. The split is by DESTINATION CONCERN -- project identity,
# tooling config, shared tests, executables -- so a new asset has an obvious home.
#
# ⚠️ CONTRACT WITH bin/ci/check_test_copy_lists.py. That gate asserts every shared unit
# test is reachable from each scaffold's copy list, and it reads the SCAFFOLD SCRIPTS.
# Moving the test `cp` lines here would have blinded it -- it would have found empty
# lists and reported every shared test as missing. It now follows the `source` line into
# this file, so the reachable set it computes is the real union. If you move these lines
# again, that gate moves with them.
#
# ⚠️ This is a sourced lib: define-only, no work on source. It reads globals the caller
# has already set (BLUEPRINTX_ROOT, COMMON_TEMPLATE_ROOT, SHARED_TEMPLATE_ROOT,
# LICENSES_TEMPLATE_ROOT, LICENSE_CHOICE, PROJECT_* and GITHUB_USERNAME).

scaffold_render_pyproject() {
	local str_tier="$1"
	local str_project_path="$2"

	HOMEPAGE="${HOMEPAGE:-https://example.com/${PROJECT_NAME}}"
	REPOSITORY="${REPOSITORY:-https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}}"
	BUG_REPORTS_URL="${BUG_REPORTS_URL:-${REPOSITORY}/issues}"
	SOURCE_URL="${SOURCE_URL:-${REPOSITORY}}"

	COPYRIGHT_YEAR="$(date +%Y)"
	AUTHOR_NAME="${GITHUB_USERNAME}"
	PROJECT_LICENSE="${LICENSE_CHOICE}"

	export PROJECT_NAME PROJECT_VERSION PROJECT_DESCRIPTION \
		PROJECT_DISPLAY_NAME HOMEPAGE REPOSITORY BUG_REPORTS_URL SOURCE_URL GITHUB_USERNAME \
		COPYRIGHT_YEAR AUTHOR_NAME PROJECT_LICENSE

	envsubst <"$BLUEPRINTX_ROOT/templates/$str_tier/pyproject.toml" \
		>"$str_project_path/pyproject.toml"
	envsubst <"$LICENSES_TEMPLATE_ROOT/${LICENSE_CHOICE}" >"$str_project_path/LICENSE"
}

scaffold_copy_tooling_configs() {
	local str_project_path="$1"

	cp "$COMMON_TEMPLATE_ROOT/.pre-commit-config.yaml" "$str_project_path/.pre-commit-config.yaml"
	cp "$COMMON_TEMPLATE_ROOT/.pydocstyle" "$str_project_path/.pydocstyle"
	cp "$COMMON_TEMPLATE_ROOT/requirements.txt" "$str_project_path/requirements.txt"
	cp "$COMMON_TEMPLATE_ROOT/.codespellrc" "$str_project_path/.codespellrc"
	# Reviewer roster for bin/check_review_threads.py — data, not logic, so swapping
	# review tools is a row here rather than an edit to the gate.
	cp "$COMMON_TEMPLATE_ROOT/.review-bots.yaml" "$str_project_path/.review-bots.yaml"
	cp "$COMMON_TEMPLATE_ROOT/mypy.ini" "$str_project_path/mypy.ini"
	cp "$COMMON_TEMPLATE_ROOT/.sqlfluff" "$str_project_path/.sqlfluff"
	cp "$COMMON_TEMPLATE_ROOT/.sqlfluffignore" "$str_project_path/.sqlfluffignore"
	cp "$COMMON_TEMPLATE_ROOT/.hadolint.yaml" "$str_project_path/.hadolint.yaml"
	cp "$COMMON_TEMPLATE_ROOT/.yamllint" "$str_project_path/.yamllint"
	cp "$COMMON_TEMPLATE_ROOT/.shellcheckrc" "$str_project_path/.shellcheckrc"
	cp "$COMMON_TEMPLATE_ROOT/CONTRIBUTING.md" "$str_project_path/CONTRIBUTING.md"
	# The command interface: poe_tasks.toml replaces the Makefile + tasks.sh pair.
	cp "$COMMON_TEMPLATE_ROOT/poe_tasks.toml" "$str_project_path/poe_tasks.toml"
	cp "$COMMON_TEMPLATE_ROOT/pytest.ini" "$str_project_path/pytest.ini"
	cp "$COMMON_TEMPLATE_ROOT/ruff.toml" "$str_project_path/ruff.toml"
	# Seed CHANGELOG.md so the docs Changelog page (--8<-- include) builds before the first
	# release; cz changelog regenerates it from tags at release/docs-build time.
	cp "$COMMON_TEMPLATE_ROOT/CHANGELOG.md" "$str_project_path/CHANGELOG.md"
	cp "$COMMON_TEMPLATE_ROOT/poetry.toml" "$str_project_path/poetry.toml"
	cp "$COMMON_TEMPLATE_ROOT/.gitlint" "$str_project_path/.gitlint"
	cp "$COMMON_TEMPLATE_ROOT/.coveragerc" "$str_project_path/.coveragerc"
	# Commitizen config, out of pyproject.toml since blueprintx#233. Losing this copy does
	# NOT error — cz falls back to defaults and exits 0 — so scaffold_lint_test.sh asserts it.
	cp "$COMMON_TEMPLATE_ROOT/.cz.toml" "$str_project_path/.cz.toml"
}

scaffold_copy_shared_tests() {
	local str_project_path="$1"

	# Reference integration test for the shared bin/ shell seams (poetry_exec.sh,
	# precommit.sh). Ships from python-common — the per-tier `cp -r tests/.` does not
	# reach python-common/tests/. See bin/CLAUDE.md "Testing shell scripts".
	mkdir -p "$str_project_path/tests/integration"
	cp "$COMMON_TEMPLATE_ROOT/tests/integration/test_bin_scripts.py" \
		"$str_project_path/tests/integration/test_bin_scripts.py"
	rm -f "$str_project_path/tests/integration/.keep"

	# Network-block guard + introspective-convention example — ship from python-common to
	# every tier (the per-tier `cp -r tests/.` does not reach python-common/tests/). The
	# conftest makes a real network call impossible in any test; the example demonstrates
	# enforcing a family convention via __all__.
	mkdir -p "$str_project_path/tests/unit"
	# The tests/ leaf doc — ONE source for all six tiers (blueprintx#124, #152). It used to
	# exist only in the two MVC tiers, byte-identical, and shipping it per-tier would have
	# made six copies of one file: exactly the drift check_codespell_sync.sh exists to
	# police. Layout-specific guidance lives in a table INSIDE the doc, not in six forks.
	cp "$COMMON_TEMPLATE_ROOT/tests/CLAUDE.md" "$str_project_path/tests/CLAUDE.md"
	cp "$COMMON_TEMPLATE_ROOT/tests/conftest.py" "$str_project_path/tests/conftest.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_pr_gate.py" \
		"$str_project_path/tests/unit/test_pr_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_backlog_ledger.py" \
		"$str_project_path/tests/unit/test_backlog_ledger.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_layer_imports_gate.py" \
		"$str_project_path/tests/unit/test_layer_imports_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_all_exports_gate.py" \
		"$str_project_path/tests/unit/test_all_exports_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_contract_family_conventions.py" \
		"$str_project_path/tests/unit/test_contract_family_conventions.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_comment_language_gate.py" \
		"$str_project_path/tests/unit/test_comment_language_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_function_length_gate.py" \
		"$str_project_path/tests/unit/test_function_length_gate.py"
}

# Split from scaffold_copy_shared_tests (blueprintx#127): the gate/example tests plus
# fixtures, kept separate so neither half nears the 60-line function-length ceiling.
scaffold_copy_shared_test_gates() {
	local str_project_path="$1"

	# Covers the PEP 621 layouts no tier ships, which is the only place the pip-fallback
	# selector could be wrong without any tier noticing (blueprintx#211).
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_pip_requirements.py" \
		"$str_project_path/tests/unit/test_pip_requirements.py"
	# The should-fail witness for the pip-fallback import verification (blueprintx#127).
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_verify_venv_imports.py" \
		"$str_project_path/tests/unit/test_verify_venv_imports.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_startup_fragility_order.py" \
		"$str_project_path/tests/unit/test_startup_fragility_order.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_review_threads_gate.py" \
		"$str_project_path/tests/unit/test_review_threads_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_review_retry.py" \
		"$str_project_path/tests/unit/test_review_retry.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_contract_oracle_example.py" \
		"$str_project_path/tests/unit/test_contract_oracle_example.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_family_convention_example.py" \
		"$str_project_path/tests/unit/test_family_convention_example.py"
	# Ships to all five tiers; self-skips at module level in lib-minimal, which carries no
	# contract registry and therefore no drift driver.
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_contract_drift.py" \
		"$str_project_path/tests/unit/test_contract_drift.py"

	mkdir -p "$str_project_path/tests/fixtures"
	cp "$COMMON_TEMPLATE_ROOT/tests/fixtures/example_source__header.csv" \
		"$str_project_path/tests/fixtures/example_source__header.csv"
}

scaffold_copy_executables_and_vscode() {
	local str_tier="$1"
	local str_project_path="$2"

	cp -r "$COMMON_TEMPLATE_ROOT/bin/." "$str_project_path/bin"
	cp "$SHARED_TEMPLATE_ROOT/bin/export_repo_content.sh" \
		"$str_project_path/bin/export_repo_content.sh"
	cp "$SHARED_TEMPLATE_ROOT/bin/ship.sh" "$str_project_path/bin/ship.sh"
	cp "$SHARED_TEMPLATE_ROOT/bin/commit.sh" "$str_project_path/bin/commit.sh"
	chmod +x "$str_project_path/bin/export_repo_content.sh" \
		"$str_project_path/bin/ship.sh" "$str_project_path/bin/commit.sh"
	# check_review_threads.py moved out of python-common/bin/ into the language-agnostic
	# templates/common/bin/ (blueprintx#175 follow-up) — the wholesale COMMON_TEMPLATE_ROOT
	# copy above no longer reaches it, so it is copied explicitly from SHARED_TEMPLATE_ROOT,
	# same destination as before (project bin/), so review_threads.yaml's
	# `python bin/check_review_threads.py` needs no change.
	cp "$SHARED_TEMPLATE_ROOT/bin/check_review_threads.py" \
		"$str_project_path/bin/check_review_threads.py"

	mkdir -p "$str_project_path/dist"
	cp "$SHARED_TEMPLATE_ROOT/dist/.keep" "$str_project_path/dist/.keep"

	# VS Code: shared settings (python-common) + per-tier tasks (commands differ).
	mkdir -p "$str_project_path/.vscode"
	cp "$COMMON_TEMPLATE_ROOT/.vscode/settings.json" "$str_project_path/.vscode/settings.json"
	cp "$COMMON_TEMPLATE_ROOT/.vscode/extensions.json" \
		"$str_project_path/.vscode/extensions.json"
	# Single source for the four service tiers. They each carried their own copy until the
	# poe migration and all four were byte-identical (md5 09515a32) — four copies of one
	# file, which is the drift check_codespell_sync.sh exists to police. lib-minimal keeps
	# its own (its task set genuinely differs) and copies it in its own scaffold.
	cp "$COMMON_TEMPLATE_ROOT/.vscode/tasks.json" \
		"$str_project_path/.vscode/tasks.json"
}

scaffold_copy_common_templates() {
	local str_tier="$1"
	local str_project_path="$2"

	print_status "info" "Applying common Python templates..."
	scaffold_render_pyproject "$str_tier" "$str_project_path"
	scaffold_copy_tooling_configs "$str_project_path"
	scaffold_copy_shared_tests "$str_project_path"
	scaffold_copy_shared_test_gates "$str_project_path"
	scaffold_copy_executables_and_vscode "$str_tier" "$str_project_path"
	print_status "success" "Common templates applied"
}
