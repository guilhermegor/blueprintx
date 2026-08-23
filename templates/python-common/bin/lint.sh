#!/usr/bin/env bash
#
# lint.sh — the full lint set, in one place.
#
# Single source of truth for "run every gate": called by `poe lint`, the
# generated project's CI, and bin/ci/scaffold_lint_test.sh (which runs a scaffolded project's
# `poe lint` — the real verification for template work). It was 14 inline recipe lines
# duplicated between the Makefile and tasks.sh; two copies of a 14-step sequence is precisely
# the drift the house rule ("logic goes in bin/<name>.sh, recipes just call it") exists to
# prevent, and the copies had already diverged elsewhere in the pair (blueprintx#189).
#
# ⚠️ ORDER IS LOAD-BEARING, in one specific way: the two ruff steps come FIRST and they
# MUTATE the tree (`--fix`, then `format`). Every gate after them therefore reads the
# formatted tree, which is what CI checks — running them later would have the gates judge a
# tree that is about to change. This is also why `poe lint` must leave the tree unchanged on
# a clean checkout: a diff after a lint run means a gate and the formatter disagree.
#
# Failure semantics: `set -e` plus no masking, so the FIRST failing gate ends the run with its
# own exit status. Do not add `|| true` to a step — a gate whose failure cannot fail the run
# is a gate that reports its own blindness as OK.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

cd "$SCRIPT_DIR/.."

POETRY="bash $SCRIPT_DIR/poetry_exec.sh"

print_status info "ruff check --fix"
$POETRY run ruff check --fix .

print_status info "ruff format"
$POETRY run ruff format .

# mypy runs FROM src/ so that `src` is the single package base — matching how the app
# actually imports (`config.x`, `utils.x`), not `src.config.x`. The config path is relative
# to that cwd, hence ../mypy.ini.
print_status info "mypy (from src/)"
(cd src && bash "$SCRIPT_DIR/poetry_exec.sh" run mypy --config-file ../mypy.ini .)

print_status info "codespell"
$POETRY run codespell .

print_status info "pydocstyle"
$POETRY run pydocstyle .

print_status info "docstring/signature agreement"
$POETRY run python bin/check_docstrings.py

print_status info "layer import policy"
$POETRY run python bin/check_layer_imports.py

print_status info "comment language boundary"
$POETRY run python bin/check_comment_language.py

print_status info "function length"
$POETRY run python bin/check_function_length.py

print_status info "cyclomatic complexity"
bash bin/check_complexity.sh

# ⚠️ DELIBERATELY ABSENT: check_typing.py. It belongs in this list and is NOT here yet, which is
# a tracked gap, not an oversight — see blueprintx#244.
#
# Adding it was attempted here and reverted with the reason measured: on a fresh scaffold it
# reports 28 functions in the shipped src/utils/ that lack @type_checker. Those are real
# omissions (the same files decorate their other private helpers), so the gate is right and the
# template is wrong — but 7 of the 28 are @functools.singledispatch handlers documented as
# taking "one cell from a decimal-typed column". Decorating those changes per-cell runtime cost
# in every generated project and stacks a wrapper under `.register`, which reads the annotation
# it dispatches on. That is a runtime-behaviour change, and it does not belong in a commit whose
# subject is gate parity.
#
# ⚠️ Do not re-add this line before #244 closes: `poe lint` would be red on every fresh scaffold.

print_status info "__all__ export completeness"
$POETRY run python bin/check_all_exports.py

print_status info "numeric dtype policy"
$POETRY run python bin/check_dtypes.py

# ⚠️ THE ONE THAT MADE THIS ISSUE WORTH FILING. check_provenance runs as a pre-commit hook AND
# as a CI job, and until now had no `poe lint` equivalent — so "green locally, red in CI" was a
# reachable state on the gate whose entire purpose is stopping an ingested row from shipping
# without its url/updated_at columns. It is the only gate in the set that CI ran and this
# script did not.
print_status info "ingestion provenance stamp"
$POETRY run python bin/check_provenance.py

print_status info "docs skeleton (slug + nav)"
$POETRY run python bin/check_docs_sections.py

print_status info "unix filename validity"
bash bin/check_unix_filenames.sh

print_status info "shell"
bash bin/lint_shell.sh

print_status info "sql"
bash bin/lint_sql.sh

print_status info "yaml"
bash bin/lint_yaml.sh

print_status info "github actions"
bash bin/lint_actions.sh

print_status info "dockerfiles"
bash bin/lint_docker.sh

print_status success "lint OK — every gate passed"
