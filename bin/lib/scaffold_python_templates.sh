#!/usr/bin/env bash

# shellcheck source=bin/lib/scaffold_provenance.sh
source "$(dirname "${BASH_SOURCE[0]}")/scaffold_provenance.sh"

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

scaffold_prune_optin_dependency() {
	local str_project_path="$1" str_flag_value="$2" str_sed_pattern="$3"

	[[ "$str_flag_value" == "true" ]] && return
	sed_inplace "$str_sed_pattern" "$str_project_path/pyproject.toml"
}

scaffold_copy_tooling_configs() {
	local str_project_path="$1"

	cp "$COMMON_TEMPLATE_ROOT/.pre-commit-config.yaml" "$str_project_path/.pre-commit-config.yaml"
	cp "$COMMON_TEMPLATE_ROOT/.pydocstyle" "$str_project_path/.pydocstyle"
	cp "$COMMON_TEMPLATE_ROOT/requirements.txt" "$str_project_path/requirements.txt"
	cp "$COMMON_TEMPLATE_ROOT/.codespellrc" "$str_project_path/.codespellrc"
	if [[ "${INCLUDE_REVIEW_BOT_ROSTER:-true}" == "true" ]]; then
		cp "$COMMON_TEMPLATE_ROOT/.review-bots.yaml" "$str_project_path/.review-bots.yaml"
	fi
	cp "$COMMON_TEMPLATE_ROOT/mypy.ini" "$str_project_path/mypy.ini"
	cp "$COMMON_TEMPLATE_ROOT/.sqlfluff" "$str_project_path/.sqlfluff"
	cp "$COMMON_TEMPLATE_ROOT/.sqlfluffignore" "$str_project_path/.sqlfluffignore"
	cp "$COMMON_TEMPLATE_ROOT/.hadolint.yaml" "$str_project_path/.hadolint.yaml"
	cp "$COMMON_TEMPLATE_ROOT/.yamllint" "$str_project_path/.yamllint"
	cp "$COMMON_TEMPLATE_ROOT/.shellcheckrc" "$str_project_path/.shellcheckrc"
	cp "$COMMON_TEMPLATE_ROOT/CONTRIBUTING.md" "$str_project_path/CONTRIBUTING.md"
	cp "$COMMON_TEMPLATE_ROOT/poe_tasks.toml" "$str_project_path/poe_tasks.toml"
	cp "$COMMON_TEMPLATE_ROOT/pytest.ini" "$str_project_path/pytest.ini"
	cp "$COMMON_TEMPLATE_ROOT/ruff.toml" "$str_project_path/ruff.toml"
	cp "$COMMON_TEMPLATE_ROOT/CHANGELOG.md" "$str_project_path/CHANGELOG.md"
	cp "$COMMON_TEMPLATE_ROOT/poetry.toml" "$str_project_path/poetry.toml"
	cp "$COMMON_TEMPLATE_ROOT/.gitlint" "$str_project_path/.gitlint"
	cp "$COMMON_TEMPLATE_ROOT/.coveragerc" "$str_project_path/.coveragerc"
	cp "$SHARED_TEMPLATE_ROOT/PRINCIPLES.md" "$str_project_path/PRINCIPLES.md"
	cp "$COMMON_TEMPLATE_ROOT/.cz.toml" "$str_project_path/.cz.toml"
}

scaffold_copy_shared_tests() {
	local str_project_path="$1"

	mkdir -p "$str_project_path/tests/integration"
	cp "$COMMON_TEMPLATE_ROOT/tests/integration/test_bin_scripts.py" \
		"$str_project_path/tests/integration/test_bin_scripts.py"
	rm -f "$str_project_path/tests/integration/.keep"

	mkdir -p "$str_project_path/tests/unit"
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

scaffold_copy_shared_test_gates() {
	local str_project_path="$1"

	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_coverage_floor_gate.py" \
		"$str_project_path/tests/unit/test_coverage_floor_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_pip_requirements.py" \
		"$str_project_path/tests/unit/test_pip_requirements.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_verify_venv_imports.py" \
		"$str_project_path/tests/unit/test_verify_venv_imports.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_startup_fragility_order.py" \
		"$str_project_path/tests/unit/test_startup_fragility_order.py"
	scaffold_copy_gate_tests "$str_project_path"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_contract_oracle_example.py" \
		"$str_project_path/tests/unit/test_contract_oracle_example.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_family_convention_example.py" \
		"$str_project_path/tests/unit/test_family_convention_example.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_contract_drift.py" \
		"$str_project_path/tests/unit/test_contract_drift.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_template_drift_gate.py" \
		"$str_project_path/tests/unit/test_template_drift_gate.py"

	mkdir -p "$str_project_path/tests/fixtures"
	cp "$COMMON_TEMPLATE_ROOT/tests/fixtures/example_source__header.csv" \
		"$str_project_path/tests/fixtures/example_source__header.csv"
}

scaffold_copy_gate_tests() {
	local str_project_path="$1"

	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_function_length_gate.py" \
		"$str_project_path/tests/unit/test_function_length_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_comment_budget_gate.py" \
		"$str_project_path/tests/unit/test_comment_budget_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_env_docs_sync_gate.py" \
		"$str_project_path/tests/unit/test_env_docs_sync_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_wheelhouse_select.py" \
		"$str_project_path/tests/unit/test_wheelhouse_select.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_gate_integrity_gate.py" \
		"$str_project_path/tests/unit/test_gate_integrity_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_review_threads_gate.py" \
		"$str_project_path/tests/unit/test_review_threads_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_review_retry.py" \
		"$str_project_path/tests/unit/test_review_retry.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_docs_code_refs_gate.py" \
		"$str_project_path/tests/unit/test_docs_code_refs_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_assertion_weakening_gate.py" \
		"$str_project_path/tests/unit/test_assertion_weakening_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_rmw_race_gate.py" \
		"$str_project_path/tests/unit/test_rmw_race_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_sql_guards_gate.py" \
		"$str_project_path/tests/unit/test_sql_guards_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_identifier_masking_gate.py" \
		"$str_project_path/tests/unit/test_identifier_masking_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_orm_model_guards_gate.py" \
		"$str_project_path/tests/unit/test_orm_model_guards_gate.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_ruff_ret_rule.py" \
		"$str_project_path/tests/unit/test_ruff_ret_rule.py"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_migration_slug_gate.py" \
		"$str_project_path/tests/unit/test_migration_slug_gate.py"
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
	cp "$SHARED_TEMPLATE_ROOT/bin/check_review_threads.py" \
		"$str_project_path/bin/check_review_threads.py"
	cp -r "$SHARED_TEMPLATE_ROOT/.specs" "$str_project_path/.specs"
	mkdir -p "$str_project_path/.specs/backlog"
	touch "$str_project_path/.specs/backlog/.gitkeep"
	cp "$BLUEPRINTX_ROOT/bin/ci/check_specs_structure.sh" \
		"$str_project_path/bin/check_specs_structure.sh"
	chmod +x "$str_project_path/bin/check_specs_structure.sh"
	cp "$BLUEPRINTX_ROOT/bin/ci/check_docs_boundary.sh" "$str_project_path/bin/check_docs_boundary.sh"
	chmod +x "$str_project_path/bin/check_docs_boundary.sh"

	mkdir -p "$str_project_path/dist"
	cp "$SHARED_TEMPLATE_ROOT/dist/.keep" "$str_project_path/dist/.keep"

	mkdir -p "$str_project_path/.vscode"
	cp "$COMMON_TEMPLATE_ROOT/.vscode/settings.json" "$str_project_path/.vscode/settings.json"
	cp "$COMMON_TEMPLATE_ROOT/.vscode/extensions.json" \
		"$str_project_path/.vscode/extensions.json"
	cp "$COMMON_TEMPLATE_ROOT/.vscode/tasks.json" \
		"$str_project_path/.vscode/tasks.json"
}

scaffold_copy_docs_extras() {
	local str_project_path="$1"

	cp "$COMMON_TEMPLATE_ROOT/docs/incidents.md" "$str_project_path/docs/incidents.md"
}

scaffold_copy_leaf_docs() {
	local str_project_path="$1"

	mkdir -p "$str_project_path/src/config/contracts" "$str_project_path/src/utils"
	cp "$COMMON_TEMPLATE_ROOT/src/config/contracts/CLAUDE.md" \
		"$str_project_path/src/config/contracts/CLAUDE.md"
	cp "$COMMON_TEMPLATE_ROOT/src/utils/CLAUDE.md" "$str_project_path/src/utils/CLAUDE.md"
}

scaffold_copy_agents_md() {
	local str_tier="$1"
	local str_project_path="$2"

	cp "$BLUEPRINTX_ROOT/templates/$str_tier/AGENTS.md" "$str_project_path/AGENTS.md"
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
	scaffold_stamp_provenance "$str_tier" "$str_project_path"
	scaffold_copy_docs_extras "$str_project_path"
	scaffold_copy_leaf_docs "$str_project_path"
	scaffold_copy_agents_md "$str_tier" "$str_project_path"
	mkdir -p "$str_project_path/.claude"
	cp "$SHARED_TEMPLATE_ROOT/CLAUDE.md" "$str_project_path/.claude/CLAUDE.md"
	print_status "success" "Common templates applied"
}

scaffold_dry_cp() {
	local str_project_path="$1"
	shift
	while [[ "${1:-}" == -* ]]; do shift; done
	local str_dst="${!#}" str_src str_kind str_rel_dst
	for str_src in "${@:1:$#-1}"; do
		str_rel_dst="${str_dst#"$str_project_path"}"
		if [[ $# -gt 2 || "$str_dst" == */ ]]; then
			str_rel_dst="${str_rel_dst%/}/${str_src##*/}"
		fi
		str_kind="file"
		[[ -d "$str_src" ]] && str_kind=dir
		str_src="${str_src%/.}"
		printf 'COPY\t%s\t%s\t%s\n' "$str_kind" "${str_src#"$BLUEPRINTX_ROOT"/}" "${str_rel_dst#/}"
	done
}

scaffold_dry_rm() {
	local str_project_path="$1" str_arg
	shift
	for str_arg in "$@"; do
		[[ "$str_arg" == -* ]] && continue
		printf 'RM\t%s\n' "${str_arg#"$str_project_path"/}"
	done
}

scaffold_list_copies() {
	local str_tier="$1" str_roster="$2" str_project_path int_status
	str_project_path="$(mktemp -d)"
	(
		set -e
		print_status() { :; }
		envsubst() { :; }
		mkdir() { :; }
		touch() { :; }
		chmod() { :; }
		cp() { scaffold_dry_cp "$str_project_path" "$@"; }
		rm() { scaffold_dry_rm "$str_project_path" "$@"; }
		INCLUDE_REVIEW_BOT_ROSTER="$str_roster" scaffold_copy_common_templates "$str_tier" "$str_project_path"
	)
	int_status=$?
	rm -rf "$str_project_path"
	return "$int_status"
}

scaffold_list_copies_main() {
	local str_tier="" str_roster=true
	if [[ "${1:-}" != "--list-copies" ]]; then
		print_status "error" "meant to be sourced; run directly only as: --list-copies --tier <tier> [--roster true|false]"
		return 1
	fi
	shift
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--tier) str_tier="${2:?--tier needs a value}" ;;
		--roster) str_roster="${2:?--roster needs a value}" ;;
		*)
			print_status "error" "unknown argument: $1"
			return 2
			;;
		esac
		shift 2
	done
	if [[ -z "$str_tier" ]]; then
		print_status "error" "--tier is required"
		return 2
	fi
	BLUEPRINTX_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
	COMMON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/python-common"
	SHARED_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/common"
	LICENSES_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/licenses"
	LICENSE_CHOICE=MIT
	scaffold_list_copies "$str_tier" "$str_roster"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
	scaffold_list_copies_main "$@"
	exit $?
fi
