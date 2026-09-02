#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=bin/lib/scaffold_git_remote.sh
source "$SCRIPT_DIR/../lib/scaffold_git_remote.sh"

PROJECT_ROOT="$1"
PROJECT_NAME="$2"
# The DISTRIBUTION name (hyphens legal on PyPI) and the IMPORT package derived from it
# (a hyphen in an import is a parse-time SyntaxError). See to_import_package_name in
# bin/lib/common.sh — blueprintx#113.
PROJECT_PKG_NAME="$(to_import_package_name "$PROJECT_NAME")"
PROJECT_DESCRIPTION="${3:-}"
PROJECT_VERSION="${4:-0.0.1}"
LICENSE_CHOICE="${LICENSE_CHOICE:-MIT}"
BLUEPRINTX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMMON_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/python-common"
# Language-agnostic assets shared by every skeleton (CODEOWNERS, PR template)
SHARED_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/common"
LICENSES_TEMPLATE_ROOT="$BLUEPRINTX_ROOT/templates/licenses"
DEFAULT_GITHUB_USERNAME="${GITHUB_USERNAME:-your-github-username}"
PROJECT_DISPLAY_NAME=""
INCLUDE_DOCKER_COMPOSE=false
DB_COMPOSE_BACKEND="postgresql"
INCLUDE_LOGS=false
# Publish/consume wiring (scaffold-publish-target-selection). Python resolution of the
# ecosystem-neutral questions: official public registry = PyPI, staging/sandbox = Test PyPI,
# private/non-official source = a PEP 503 index or git source. Defaults keep the prior behaviour
# (both release workflows shipped) so non-interactive --dev runs are unchanged.
PUBLISH_PYPI=true
PUBLISH_TEST_PYPI=true
CONSUME_PRIVATE=false

# ============================================================================
# FUNCTIONS
# ============================================================================

validate_inputs() {
    if [ -z "$PROJECT_ROOT" ] || [ -z "$PROJECT_NAME" ]; then
        exit_error "Usage: $0 <project_root_dir> <project_name>"
    fi
    # The prompt validates too, but the scaffolds are also callable DIRECTLY
    # (bin/ci/scaffold_lint_test.sh does exactly that), so a guard living only in
    # prompt_project_name protects one of the two entry points. blueprintx#113.
    if ! is_valid_project_name "$PROJECT_NAME"; then
        exit_error "Invalid project name '$PROJECT_NAME'. Use a letter or underscore first, then letters, digits, '-' or '_'."
    fi
    print_status "success" "Input validation passed"
}

format_display_name() {
    # Identity: the docs/README title IS the distribution name (lowercase,
    # hyphenated), mirroring filings-cvm/filings-b3 — not a title-cased variant.
    # Set PROJECT_DISPLAY_NAME explicitly before scaffolding to override.
    echo "$1"
}

resolve_github_username() {
    # 1) GH_USERNAME env override
    if [ -n "$GITHUB_USERNAME" ]; then
        print_status "config" "GitHub username (env): $GITHUB_USERNAME"
        return
    fi

    # 2) gh CLI (authenticated)
    if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
        local gh_user
        gh_user=$(gh api user -q .login 2>/dev/null || true)
        if [ -n "$gh_user" ]; then
            GITHUB_USERNAME="$gh_user"
            print_status "config" "GitHub username (gh): $GITHUB_USERNAME"
            return
        fi
    fi

    # 3) Fallback prompt
    local input
    read -r -p "$(prompt_main "GitHub username (default: $DEFAULT_GITHUB_USERNAME): ")" input || true
    if [ -n "$input" ]; then
        GITHUB_USERNAME="$input"
    else
        GITHUB_USERNAME="$DEFAULT_GITHUB_USERNAME"
    fi
    print_status "config" "GitHub username (prompt): $GITHUB_USERNAME"
}

create_directory_structure() {
    local project_path="$1"

    print_status "info" "Creating directory structure..."

    mkdir -p "$project_path"/src/"$PROJECT_PKG_NAME"/_internal/utils/typing
    mkdir -p "$project_path"/src/"$PROJECT_PKG_NAME"/_internal/config/contracts
    # ports live UNDER config/ — config/ is the home of all private structural declarations
    # (contracts + ports + schemas), not a top-level sibling. See _internal/config/CLAUDE.md.
    mkdir -p "$project_path"/src/"$PROJECT_PKG_NAME"/_internal/config/ports
    mkdir -p "$project_path"/tests/integration
    mkdir -p "$project_path"/tests/performance
    mkdir -p "$project_path"/tests/unit
    mkdir -p "$project_path"/container
    mkdir -p "$project_path"/bin
    mkdir -p "$project_path"/docs
    mkdir -p "$project_path"/assets
    mkdir -p "$project_path"/.github/workflows
    mkdir -p "$project_path"/.vscode

    print_status "success" "Directory structure created"
}

create_python_files() {
    local project_path="$1"

    print_status "info" "Creating Python files..."

    # Public package init. Exposes __version__ (resolved from the installed distribution's
    # metadata), which install_dist_locally's wheel smoke-test asserts. Tab-indented so a fresh
    # scaffold passes `make lint`.
    # ⚠️ The render variable must be exported ON THIS COMMAND: envsubst reads the
    # ENVIRONMENT, not the shell's variables, and it is not exported until
    # lib_minimal_render_pyproject runs later. Without it the substitution silently
    # yields the EMPTY STRING — `version("")` and `from .main import main` — a broken
    # package that still scaffolds without error. The heredoc this replaced used shell
    # interpolation, which sees unexported variables; envsubst does not.
    PROJECT_NAME="$PROJECT_NAME" envsubst '${PROJECT_NAME}' \
        < "$BLUEPRINTX_ROOT/templates/lib-minimal/rendered/package__init__.py.tmpl" \
        > "$project_path/src/$PROJECT_PKG_NAME/__init__.py"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/main.py" "$project_path/src/$PROJECT_PKG_NAME/main.py"

    # Create test file with project name substitution. Tab-indented and fully
    # annotated/docstringed so a freshly scaffolded project passes `make lint`.
    mkdir -p "$project_path/tests/unit"
    # ⚠️ The render variable must be exported ON THIS COMMAND: envsubst reads the
    # ENVIRONMENT, not the shell's variables, and it is not exported until
    # lib_minimal_render_pyproject runs later. Without it the substitution silently
    # yields the EMPTY STRING — `version("")` and `from .main import main` — a broken
    # package that still scaffolds without error. The heredoc this replaced used shell
    # interpolation, which sees unexported variables; envsubst does not.
    PROJECT_PKG_NAME="$PROJECT_PKG_NAME" envsubst '${PROJECT_PKG_NAME}' \
        < "$BLUEPRINTX_ROOT/templates/lib-minimal/rendered/test_main.py.tmpl" \
        > "$project_path/tests/unit/test_main.py"

    # Smoke-test the runtime type-checking engine in the wheel layout. lib-minimal is the only
    # tier that rewrites the engine's own imports to `<pkg>._internal.utils.typing`; a broken
    # rewrite would fail here and nowhere else, so this guards that path (the full behavioural
    # matrix is covered by the service tiers' test_typing.py).
    # ⚠️ The render variable must be exported ON THIS COMMAND: envsubst reads the
    # ENVIRONMENT, not the shell's variables, and it is not exported until
    # lib_minimal_render_pyproject runs later. Without it the substitution silently
    # yields the EMPTY STRING — `version("")` and `from .main import main` — a broken
    # package that still scaffolds without error. The heredoc this replaced used shell
    # interpolation, which sees unexported variables; envsubst does not.
    PROJECT_PKG_NAME="$PROJECT_PKG_NAME" envsubst '${PROJECT_PKG_NAME}' \
        < "$BLUEPRINTX_ROOT/templates/lib-minimal/rendered/test_typing.py.tmpl" \
        > "$project_path/tests/unit/test_typing.py"

    print_status "success" "Python files created"
}

# Rewrite the bare `utils.`/`config.` import prefixes (and the `chassis.typing` runtime
# fallback) to the package-qualified private path `<pkg>._internal.*`, on import lines only.
# The curated helpers are copied verbatim from python-common (DRY single source); this is the
# one adaptation that makes them resolve when nested inside the distributed package.
rewrite_internal_imports() {
    local internal_dir="$1"
    local pkg_prefix="${PROJECT_PKG_NAME}._internal"
    local file
    while IFS= read -r file; do
        sed -i -E \
            -e "s@^([[:space:]]*)(from|import) utils\.@\1\2 ${pkg_prefix}.utils.@" \
            -e "s@^([[:space:]]*)(from|import) config\.@\1\2 ${pkg_prefix}.config.@" \
            -e "s@^([[:space:]]*)(from|import) ports\.@\1\2 ${pkg_prefix}.config.ports.@" \
            -e "s@^([[:space:]]*)(from|import) chassis\.typing@\1\2 ${pkg_prefix}.utils.typing@" \
            "$file"
    done < <(grep -rlE "^[[:space:]]*(from|import) (utils|config|ports|chassis)\." "$internal_dir" 2>/dev/null)
}

# The curated internal helper set for a distributable library — copied from python-common
# into a PRIVATE `_internal/utils` package (leading underscore keeps it off the consumer's
# public import surface, yet it ships inside the wheel). `logs.py` is intentionally absent:
# `retry.py` is decoupled from it via an injectable `LogEmitter`.
copy_internal_utils() {
    local project_path="$1"
    local internal_dir="$project_path/src/$PROJECT_PKG_NAME/_internal"
    local utils_src="$COMMON_TEMPLATE_ROOT/src/utils"
    local -a modules=(
        __init__.py dtypes.py br_identifiers.py http_downloader.py
        tabular_reader.py xml_reader.py provenance.py sidecar_metadata.py text.py
        zip_extractor.py raw_workspace.py daily_cache.py
    )
    # retry/ is a PACKAGE, not a module (blueprintx#116) — it needs cp -r, and it is listed
    # apart from `modules` so the loop below stays a plain file copy. rewrite_internal_imports
    # recurses, so its intra-package `from utils.retry.x` imports are rewritten like any other.
    local -a packages=(retry)
    # logs.py is opt-in (prompt_logs): the convention is to inject a logger, not import one
    # (see the shipped utils/CLAUDE.md), so a lib only carries it when explicitly requested.
    if [[ "$INCLUDE_LOGS" == "true" ]]; then
        # logs_emitter (rich default sink) delegates to logs.py's CreateLog, so it ships only
        # alongside logs.py (the opt-in logging helper), never on its own.
        modules+=(logs.py logs_emitter.py)
    fi
    local module

    printf '"""Private internals of the %s package (not a public API)."""\n' "$PROJECT_PKG_NAME" \
        > "$internal_dir/__init__.py"
    for module in "${modules[@]}"; do
        cp "$utils_src/$module" "$internal_dir/utils/$module"
    done
    local package
    for package in "${packages[@]}"; do
        # Contents, not the directory: `cp -r src dst` nests when dst exists.
        mkdir -p "$internal_dir/utils/$package"
        cp -r "$utils_src/$package/." "$internal_dir/utils/$package/"
    done
    # Runtime type-checking engine — single source in python-common/optional/typing.
    cp -r "$COMMON_TEMPLATE_ROOT/optional/typing/." "$internal_dir/utils/typing"
    # Convention guide for the utils layer (logging → dependency injection). Kept out of the
    # wheel by the `exclude` in pyproject.toml.
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/utils_CLAUDE.md" "$internal_dir/utils/CLAUDE.md"

    rewrite_internal_imports "$internal_dir"
    print_status "success" "Private internal utils (_internal/utils) applied"
}

# The config-layer data contracts (declarations only), mirroring the MVC tiers — nested in
# the same private `_internal/config` package so the library author gets the contract seam
# without exposing it to consumers.
copy_internal_config() {
    local project_path="$1"
    local internal_dir="$project_path/src/$PROJECT_PKG_NAME/_internal"
    local config_src="$COMMON_TEMPLATE_ROOT/src/config"

    printf '"""Private configuration internals (data contracts) of %s."""\n' "$PROJECT_PKG_NAME" \
        > "$internal_dir/config/__init__.py"
    cp "$config_src/contracts/__init__.py" "$internal_dir/config/contracts/__init__.py"
    cp "$config_src/contracts/example_source.py" "$internal_dir/config/contracts/example_source.py"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/config_CLAUDE.md" "$internal_dir/config/CLAUDE.md"

    rewrite_internal_imports "$internal_dir"
    print_status "success" "Private internal config (_internal/config/contracts) applied"
}

# Behavioural ports (private ABCs) — the ports of hexagonal ports-and-adapters, one operation
# per file with `ABCTypeCheckerMeta`. Nested under `_internal/config/ports` (config/ is the home
# of every private structural declaration — contracts + ports + schemas — not a top-level
# sibling), so the library author gets the port/adapter seam without exposing it to consumers.
# The whole config/ layer is documented by one _internal/config/CLAUDE.md (copied by
# copy_internal_config); ports has no separate CLAUDE.md. Source is a generic reference
# (`ExamplePort`), mirroring `config/contracts/example_source.py`.
copy_internal_ports() {
    local project_path="$1"
    local internal_dir="$project_path/src/$PROJECT_PKG_NAME/_internal"
    local ports_src="$COMMON_TEMPLATE_ROOT/optional/ports"

    cp "$ports_src/__init__.py" "$internal_dir/config/ports/__init__.py"
    cp "$ports_src/example_port.py" "$internal_dir/config/ports/example_port.py"

    rewrite_internal_imports "$internal_dir"
    print_status "success" "Private internal ports (_internal/config/ports) applied"
}

# Add the PyPI/Snyk library badges (package identity + security) to the copied README, right
# after the Python Version badge. Library-only — service tiers are not published to PyPI, so these
# badges would be misleading there. Kept in the same ${...}-placeholder style as the existing
# README badges, so they render/fill together (PYPI_NAME = the PyPI distribution name;
# PROJECT_SLUG = the GitHub repo). Idempotent.
add_library_badges() {
    local project_path="$1"
    local readme="$project_path/README.md"
    [ -f "$readme" ] || return 0
    python3 - "$readme" <<'PY'
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    lines = fh.readlines()

if any("PyPI Version" in ln for ln in lines):
    sys.exit(0)  # already added — idempotent

badges = [
    "![PyPI Version](https://img.shields.io/pypi/v/${PYPI_NAME})\n",
    "[![Snyk Vulnerabilities](https://snyk.io/test/github/${GITHUB_USERNAME}/${PROJECT_SLUG}/badge.svg)]"
    "(https://snyk.io/test/github/${GITHUB_USERNAME}/${PROJECT_SLUG})\n",
    "[![Snyk License](https://snyk.io/advisor/python/${PYPI_NAME}/badge.svg)]"
    "(https://snyk.io/advisor/python/${PYPI_NAME})\n",
    "![PyPI Downloads](https://static.pepy.tech/badge/${PYPI_NAME})\n",
]

out: list[str] = []
inserted = False
for ln in lines:
    out.append(ln)
    if not inserted and "Python Version" in ln and "img.shields.io" in ln:
        out.extend(badges)
        inserted = True
if not inserted:  # no anchor found: prepend after the first badge line instead
    for i, ln in enumerate(out):
        if "img.shields.io" in ln or "repostatus.org" in ln:
            out[i + 1 : i + 1] = badges
            break

with open(path, "w", encoding="utf-8") as fh:
    fh.writelines(out)
PY
    print_status "success" "Library PyPI/Snyk badges added to README"
}

copy_templates() {
    local project_path="$1"

    print_status "info" "Copying templates..."

    cp "$COMMON_TEMPLATE_ROOT/.gitignore" "$project_path/.gitignore"
    cp "$COMMON_TEMPLATE_ROOT/.python-version" "$project_path/.python-version"
    cp "$SHARED_TEMPLATE_ROOT/.editorconfig" "$project_path/.editorconfig"
    cp "$SHARED_TEMPLATE_ROOT/.gitattributes" "$project_path/.gitattributes"
    PROJECT_DISPLAY_NAME="${PROJECT_DISPLAY_NAME:-$(format_display_name "$PROJECT_NAME")}"
    PROJECT_DISPLAY_NAME="$PROJECT_DISPLAY_NAME" envsubst '${PROJECT_DISPLAY_NAME}' < "$COMMON_TEMPLATE_ROOT/README.md" > "$project_path/README.md"
    # Ship an initial coverage.svg so the README ![Test Coverage](./coverage.svg) badge
    # resolves on the first push instead of 404-ing; regenerated by the coverage-badge hook.
    cp "$COMMON_TEMPLATE_ROOT/coverage.svg" "$project_path/coverage.svg"
    add_library_badges "$project_path"
    cp "$COMMON_TEMPLATE_ROOT/assets/logo_lorem_ipsum.png" "$project_path/assets/logo_lorem_ipsum.png"
    # No .env / .env.example: a distributable library has no runtime env to seed (unlike the
    # service tiers). Removing them keeps the published package free of service-only cruft.
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/CLAUDE.md" "$project_path/CLAUDE.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.coveragerc" "$project_path/.coveragerc"
    # Seed CHANGELOG.md so the docs Changelog page (--8<-- include) builds before the first
    # release; cz changelog regenerates it from tags at release/docs-build time. Single-sourced
    # from python-common (same seed every Python tier ships) — no per-tier duplicate.
    cp "$COMMON_TEMPLATE_ROOT/CHANGELOG.md" "$project_path/CHANGELOG.md"

    print_status "success" "Templates copied and configured"
}

# lib-minimal's own template copy step. It is NOT the four service tiers' shared
# scaffold_copy_common_templates: this tier renders a different pyproject (PyPI Trove
# classifier, library.mk) and installs the GitHub assets inline, where the service
# scaffolds have a separate copy_github_assets. Split by DESTINATION CONCERN, the same
# way the shared lib is, so a new asset has an obvious home.
lib_minimal_render_pyproject() {
    local project_path="$1"


    print_status "info" "Applying common Python templates..."

    HOMEPAGE="${HOMEPAGE:-https://example.com/${PROJECT_NAME}}"
    REPOSITORY="${REPOSITORY:-https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}}"
    BUG_REPORTS_URL="${BUG_REPORTS_URL:-${REPOSITORY}/issues}"
    SOURCE_URL="${SOURCE_URL:-${REPOSITORY}}"

    COPYRIGHT_YEAR="$(date +%Y)"
    AUTHOR_NAME="${GITHUB_USERNAME}"
    PROJECT_LICENSE="${LICENSE_CHOICE}"
    # Map the license choice to its PyPI Trove classifier (generic OSI fallback otherwise).
    case "$PROJECT_LICENSE" in
        MIT) PROJECT_LICENSE_CLASSIFIER="License :: OSI Approved :: MIT License" ;;
        Apache-2.0) PROJECT_LICENSE_CLASSIFIER="License :: OSI Approved :: Apache Software License" ;;
        GPL-3.0) PROJECT_LICENSE_CLASSIFIER="License :: OSI Approved :: GNU General Public License v3 (GPLv3)" ;;
        *) PROJECT_LICENSE_CLASSIFIER="License :: OSI Approved" ;;
    esac

    export PROJECT_NAME PROJECT_PKG_NAME PROJECT_VERSION PROJECT_DESCRIPTION \
        PROJECT_DISPLAY_NAME HOMEPAGE REPOSITORY BUG_REPORTS_URL SOURCE_URL GITHUB_USERNAME \
        COPYRIGHT_YEAR AUTHOR_NAME PROJECT_LICENSE PROJECT_LICENSE_CLASSIFIER
    envsubst < "$BLUEPRINTX_ROOT/templates/lib-minimal/pyproject.toml" > "$project_path/pyproject.toml"
}

lib_minimal_copy_tooling_configs() {
    local project_path="$1"

    cp "$COMMON_TEMPLATE_ROOT/.pre-commit-config.yaml" "$project_path/.pre-commit-config.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.pydocstyle" "$project_path/.pydocstyle"
    cp "$COMMON_TEMPLATE_ROOT/requirements.txt" "$project_path/requirements.txt"
    # Per-layer import policy read by bin/check_layer_imports.py (pre-commit + CI).
    # ⚠️ Per-tier, never shared: the layer NAMES differ, and lib-minimal nests them
    # inside the distributable package (hence its src_prefix_depth). Without this file
    # the gate used to self-skip in silence, so this tier shipped with no import
    # boundary while its CI stayed green; it now FAILS instead.
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.layer-policy.yaml" "$project_path/.layer-policy.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.codespellrc" "$project_path/.codespellrc"
    # Reviewer roster for bin/check_review_threads.py — data, not logic, so swapping
    # review tools is a row here rather than an edit to the gate.
    cp "$COMMON_TEMPLATE_ROOT/.review-bots.yaml" "$project_path/.review-bots.yaml"
    cp "$COMMON_TEMPLATE_ROOT/mypy.ini" "$project_path/mypy.ini"
    cp "$COMMON_TEMPLATE_ROOT/.sqlfluff" "$project_path/.sqlfluff"
    cp "$COMMON_TEMPLATE_ROOT/.sqlfluffignore" "$project_path/.sqlfluffignore"
    cp "$COMMON_TEMPLATE_ROOT/.hadolint.yaml" "$project_path/.hadolint.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.yamllint" "$project_path/.yamllint"
    cp "$COMMON_TEMPLATE_ROOT/.shellcheckrc" "$project_path/.shellcheckrc"
    cp "$COMMON_TEMPLATE_ROOT/CONTRIBUTING.md" "$project_path/CONTRIBUTING.md"
    envsubst < "$LICENSES_TEMPLATE_ROOT/${LICENSE_CHOICE}" > "$project_path/LICENSE"
    # The command interface: poe_tasks.toml replaces the Makefile + tasks.sh pair.
    cp "$COMMON_TEMPLATE_ROOT/poe_tasks.toml" "$project_path/poe_tasks.toml"
    # Library-only task (install_dist_locally). add_poe_include wires it into
    # poe_tasks.toml — an unconditional include would warn on every run in tiers
    # that do not ship the file.
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/poe_tasks.library.toml" \
        "$project_path/poe_tasks.library.toml"
    add_poe_include "$project_path" "poe_tasks.library.toml"
    cp "$COMMON_TEMPLATE_ROOT/pytest.ini" "$project_path/pytest.ini"
    cp "$COMMON_TEMPLATE_ROOT/ruff.toml" "$project_path/ruff.toml"
    cp "$COMMON_TEMPLATE_ROOT/poetry.toml" "$project_path/poetry.toml"
    # Commitizen config, out of pyproject.toml since blueprintx#233. Losing this copy does
    # NOT error — cz falls back to defaults and exits 0 — so scaffold_lint_test.sh asserts it.
    cp "$COMMON_TEMPLATE_ROOT/.cz.toml" "$project_path/.cz.toml"
}

# GitHub-platform assets only. apply_offline_mode drops all of .github/, so everything
# here is reachable exactly when the project has a remote.
lib_minimal_copy_github_assets() {
    local project_path="$1"

    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/tests.yaml" "$project_path/.github/workflows/tests.yaml"
    # Re-evaluates on pull_request_review / pull_request_review_comment, so a thread opened
    # after the last push is still checked — a push-only trigger goes stale exactly then.
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/review_threads.yaml" "$project_path/.github/workflows/review_threads.yaml"
    # Its other half: the gate above fails a PR nobody reviewed, and this asks for the review.
    # A new repo has 0 stars, so CodeRabbit declines to review it automatically BY CONSTRUCTION
    # — ship the gate without the trigger and every PR blocks; ship the trigger without the
    # gate and nothing notices when it stops working. GitHub-only, hence here.
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/coderabbit_trigger.yaml" "$project_path/.github/workflows/coderabbit_trigger.yaml"
    # Its THIRD half, and the reason the pair above is survivable: a rate-limited reviewer
    # declines the trigger, the gate then correctly blocks, and nothing re-asks. This retries on
    # a schedule (the only trigger that fires while a PR merely WAITS). It relaxes no verdict —
    # measured upstream, 19 rate-limited PRs and 18 reviewed in the end, so it is a delay to
    # automate rather than an unavailability to forgive. GitHub-only.
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/review_retry.yaml" "$project_path/.github/workflows/review_retry.yaml"
    # PR quality gate (classify by path, sticky comment, native auto-merge) + the reconciler
    # that closes linked issues of BOT-merged PRs (a bot merge suppresses both the issue close
    # and delete_branch_on_merge). GitHub-only, like tests.yaml.
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/pr-gate.yaml" "$project_path/.github/workflows/pr-gate.yaml"
    cp "$COMMON_TEMPLATE_ROOT/.github/workflows/pr-reconcile.yaml" "$project_path/.github/workflows/pr-reconcile.yaml"
    # PyPI + Test-PyPI release workflows (GitHub-remote-only, like tests.yaml). Restricted
    # envsubst substitutes ONLY PACKAGE_NAME/OWNER — GitHub's own `${{ … }}` expressions and
    # the `$SHELL_VARS` inside run: blocks are left untouched.
    # Emit only the selected release workflows (Q1/Q2 from prompt_publish_targets).
    if [[ "$PUBLISH_PYPI" == "true" ]]; then
        envsubst '${PROJECT_NAME} ${GITHUB_USERNAME}' \
            < "$BLUEPRINTX_ROOT/templates/lib-minimal/.github/workflows/release-pypi.yaml" \
            > "$project_path/.github/workflows/release-pypi.yaml"
    fi
    if [[ "$PUBLISH_TEST_PYPI" == "true" ]]; then
        envsubst '${PROJECT_NAME} ${GITHUB_USERNAME}' \
            < "$BLUEPRINTX_ROOT/templates/lib-minimal/.github/workflows/release-test-pypi.yaml" \
            > "$project_path/.github/workflows/release-test-pypi.yaml"
    fi
    # Docs → GitHub Pages deploy (gh-deploy on push to default branch). No placeholders; plain cp.
    # GitHub-remote-only, like the release workflows — apply_offline_mode drops all of .github/.
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.github/workflows/docs.yaml" \
        "$project_path/.github/workflows/docs.yaml"
    cp "$SHARED_TEMPLATE_ROOT/.github/CODEOWNERS" "$project_path/.github/CODEOWNERS"
    # SECURITY.md (root; GitHub auto-detects it and flips "Security policy" to Enabled) +
    # dependabot.yml (ordinary VERSION bumps; SECURITY updates are a toggle set by
    # bin/enable_security.sh). Both are GitHub-platform features, hence GitHub-only.
    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' \
        < "$SHARED_TEMPLATE_ROOT/SECURITY.md" > "$project_path/SECURITY.md"
    cp "$COMMON_TEMPLATE_ROOT/.github/dependabot.yml" "$project_path/.github/dependabot.yml"
    cp "$SHARED_TEMPLATE_ROOT/.github/CLAUDE.md" "$project_path/.github/CLAUDE.md"
    cp "$SHARED_TEMPLATE_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$project_path/.github/PULL_REQUEST_TEMPLATE.md"
}

# The tests that cover the gates themselves. Split out of the copy function when it crossed
# the 60-line ceiling: a real grouping, not an arbitrary cut, so the next gate test has an
# obvious home instead of pushing the parent over again. Mirrors scaffold_copy_gate_tests()
# in bin/lib/scaffold_python_templates.sh.
lib_minimal_copy_gate_tests() {
    local project_path="$1"

    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_layer_imports_gate.py" \
        "$project_path/tests/unit/test_layer_imports_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_comment_language_gate.py" \
        "$project_path/tests/unit/test_comment_language_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_function_length_gate.py" \
        "$project_path/tests/unit/test_function_length_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_review_threads_gate.py" \
        "$project_path/tests/unit/test_review_threads_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_review_retry.py" \
        "$project_path/tests/unit/test_review_retry.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_docs_code_refs_gate.py" \
        "$project_path/tests/unit/test_docs_code_refs_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_assertion_weakening_gate.py" \
        "$project_path/tests/unit/test_assertion_weakening_gate.py"
}

lib_minimal_copy_project_scaffolding() {
    local project_path="$1"

    cp "$COMMON_TEMPLATE_ROOT/.gitlint" "$project_path/.gitlint"
    cp -r "$COMMON_TEMPLATE_ROOT/bin/." "$project_path/bin"
    # Reference integration test for the shared bin/ shell seams (poetry_exec.sh,
    # precommit.sh). Ships from python-common — the per-tier `cp -r tests/.` does not
    # reach python-common/tests/. See bin/CLAUDE.md "Testing shell scripts".
    mkdir -p "$project_path/tests/integration"
    cp "$COMMON_TEMPLATE_ROOT/tests/integration/test_bin_scripts.py" \
        "$project_path/tests/integration/test_bin_scripts.py"
    rm -f "$project_path/tests/integration/.keep"
    # Network-block guard + introspective-convention example — ship from
    # python-common to every tier (the per-tier `cp -r tests/.` does not reach
    # python-common/tests/). The conftest makes a real network call impossible in
    # any test; the example demonstrates enforcing a family convention via __all__.
    mkdir -p "$project_path/tests/unit"
    # The tests/ leaf doc — one source for every tier (blueprintx#124, #152).
    cp "$COMMON_TEMPLATE_ROOT/tests/CLAUDE.md" "$project_path/tests/CLAUDE.md"
    cp "$COMMON_TEMPLATE_ROOT/tests/conftest.py" "$project_path/tests/conftest.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_pr_gate.py" \
        "$project_path/tests/unit/test_pr_gate.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_backlog_ledger.py" \
        "$project_path/tests/unit/test_backlog_ledger.py"
    lib_minimal_copy_gate_tests "$project_path"
    # Covers the PEP 621 layouts no tier ships, which is the only place the pip-fallback
    # selector could be wrong without any tier noticing (blueprintx#211).
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_pip_requirements.py" \
        "$project_path/tests/unit/test_pip_requirements.py"
    cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_family_convention_example.py" \
        "$project_path/tests/unit/test_family_convention_example.py"
    cp "$SHARED_TEMPLATE_ROOT/bin/export_repo_content.sh" "$project_path/bin/export_repo_content.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/ship.sh" "$project_path/bin/ship.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/commit.sh" "$project_path/bin/commit.sh"
    chmod +x "$project_path/bin/export_repo_content.sh" "$project_path/bin/ship.sh" "$project_path/bin/commit.sh"
    # check_review_threads.py moved out of python-common/bin/ into the language-agnostic
    # templates/common/bin/ (blueprintx#175 follow-up) — the wholesale COMMON_TEMPLATE_ROOT
    # copy above no longer reaches it, so it is copied explicitly, same destination as
    # before, so review_threads.yaml's `python bin/check_review_threads.py` needs no change.
    cp "$SHARED_TEMPLATE_ROOT/bin/check_review_threads.py" "$project_path/bin/check_review_threads.py"
    mkdir -p "$project_path/dist"
    cp "$SHARED_TEMPLATE_ROOT/dist/.keep" "$project_path/dist/.keep"
    # VS Code: shared settings (python-common) + slim per-tier tasks (no db tasks).
    mkdir -p "$project_path/.vscode"
    cp "$COMMON_TEMPLATE_ROOT/.vscode/settings.json" "$project_path/.vscode/settings.json"
    cp "$COMMON_TEMPLATE_ROOT/.vscode/extensions.json" "$project_path/.vscode/extensions.json"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.vscode/tasks.json" "$project_path/.vscode/tasks.json"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/.vscode/tasks.json" "$project_path/.vscode/tasks.json"
}

copy_common_templates() {
    local project_path="$1"

    print_status "info" "Applying common Python templates..."
    lib_minimal_render_pyproject "$project_path"
    lib_minimal_copy_tooling_configs "$project_path"
    lib_minimal_copy_github_assets "$project_path"
    lib_minimal_copy_project_scaffolding "$project_path"
    print_status "success" "Common templates applied"
}

copy_mkdocs_templates() {
    local project_path="$1"

    print_status "info" "Copying MkDocs templates..."

    envsubst '${PROJECT_DISPLAY_NAME} ${REPOSITORY}' \
        < "$BLUEPRINTX_ROOT/templates/lib-minimal/mkdocs.yml" \
        > "$project_path/mkdocs.yml"
    envsubst '${PROJECT_DISPLAY_NAME}' \
        < "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/index.md" \
        > "$project_path/docs/index.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/usage.md" \
        "$project_path/docs/usage.md"
    # API reference is a directory (index + one page) from day one, never a single
    # api.md — splitting it later rots published deep links (see docs/api/index.md).
    mkdir -p "$project_path/docs/api"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/api/index.md" \
        "$project_path/docs/api/index.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/api/reference.md" \
        "$project_path/docs/api/reference.md"
    # Placeholder brand image (header logo/favicon + landing hero) + its tunable CSS.
    # Swap docs/assets/logo.png for a real asset; size/position/border are inline on the <img>.
    mkdir -p "$project_path/docs/assets"
    cp "$COMMON_TEMPLATE_ROOT/assets/logo_lorem_ipsum.png" \
        "$project_path/docs/assets/logo.png"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/examples.md" \
        "$project_path/docs/examples.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/faq.md" \
        "$project_path/docs/faq.md"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/contributing.md" \
        "$project_path/docs/contributing.md"
    cp "$COMMON_TEMPLATE_ROOT/docs/changelog.md" \
        "$project_path/docs/changelog.md"
    # Non-published docs/ authoring guide + the excluded backlog folder.
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/CLAUDE.md" \
        "$project_path/docs/CLAUDE.md"
    mkdir -p "$project_path/docs/backlog"
    cp "$BLUEPRINTX_ROOT/templates/lib-minimal/docs/backlog/.keep" \
        "$project_path/docs/backlog/.keep"


    print_status "success" "MkDocs templates copied"
}

apply_branch_protection() {
    local branch="main"
    local repo="${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}/${PROJECT_NAME}"

    if ! command -v gh >/dev/null 2>&1; then
        print_status "info" "gh CLI not found; skipping main branch protection."
        return
    fi

    if ! gh auth status >/dev/null 2>&1; then
        print_status "warning" "gh not authenticated; skipping main branch protection."
        return
    fi

    if ! gh repo view "$repo" >/dev/null 2>&1; then
        print_status "warning" "GitHub repo $repo not reachable; skipping branch protection."
        return
    fi

    read -r -p "$(prompt_main "Protect branch '$branch' on GitHub now? [y/N]: ")" protect_ans || true
    case "$protect_ans" in
        y|Y)
            # A solo maintainer cannot satisfy a required-approving-review
            # rule — GitHub forbids self-approval, so the first PR's merge
            # would be permanently blocked. Ask whether human reviewers will
            # gate merges, and build the protection payload accordingly.
            local reviews_json
            read -r -p "$(prompt_sub "Will human reviewers gate merges to '$branch'? [y/N]: ")" reviews_ans || true
            case "$reviews_ans" in
                y|Y)
                    reviews_json='"required_pull_request_reviews": { "dismiss_stale_reviews": true, "require_code_owner_reviews": false, "required_approving_review_count": 1 },'
                    ;;
                *)
                    reviews_json='"required_pull_request_reviews": null,'
                    ;;
            esac
            if gh api --method PUT \
                -H "Accept: application/vnd.github+json" \
                "/repos/$repo/branches/$branch/protection" \
                --input - <<EOF
{
  "required_status_checks": { "strict": true, "contexts": [] },
  "enforce_admins": true,
  $reviews_json
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": true
}
EOF
            then
                print_status "success" "Branch '$branch' protected on GitHub."
            else
                print_status "warning" "Failed to protect branch '$branch'; adjust settings manually in GitHub."
            fi
            ;;
        *) print_status "info" "Skipped branch protection";;
    esac
}

# Always initialise a local git repo with a first commit, independent of any
# remote setup, so every scaffold is a git repo even in non-interactive (--dev)
# runs. Skips gracefully when git is unavailable or the repo already exists.
initialize_git_repo() {
    local project_path="$1"

    if ! command -v git >/dev/null 2>&1; then
        print_status "warning" "git not found — skipping repo initialization"
        return
    fi

    if git -C "$project_path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        print_status "info" "Git repo already initialized; skipping"
        return
    fi

    (
        cd "$project_path" || exit 1
        git init -q -b main || true
        git add . || true
        git commit -q -m "feat: first commit" >/dev/null 2>&1 || true
    )
    print_status "success" "Initialized git repo (branch main) with first commit"
}

prompt_git_remote_setup() {
	# The About-sidebar Website field, same URL apply_online_docs_url writes into
	# pyproject — the most visible entry point on the repo page; blank looks unfinished.
	SCAFFOLD_REPO_HOMEPAGE="https://${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}.github.io/${PROJECT_NAME}/"
	# Protection is applied to the remote only once that remote is verified to be the
	# repository this scaffold names — not merely because the prompt returned (#212).
	if scaffold_prompt_git_remote_setup "$1"; then
		apply_branch_protection "$1"
	fi
}

apply_offline_mode() {
    local project_path="$1"

    print_status "info" "No GitHub remote connected — switching to offline mode"
    # GitHub-only assets (Actions workflows, CODEOWNERS, PR template) are not useful
    # without a GitHub remote; remove them and ship the offline git-diff workflow instead.
    rm -rf "$project_path/.github"
    print_status "info" "Removed .github (GitHub-only assets)"
    mkdir -p "$project_path/bin/lib"
    cp "$SHARED_TEMPLATE_ROOT/bin/lib/common.sh" "$project_path/bin/lib/common.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_diff_export.sh" "$project_path/bin/git_diff_export.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_diff_apply.sh" "$project_path/bin/git_diff_apply.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_diff_check.sh" "$project_path/bin/git_diff_check.sh"
    # Local git workflow + branch guard — substitute for GitHub's branch/PR flow.
    cp "$SHARED_TEMPLATE_ROOT/bin/new_branch.sh" "$project_path/bin/new_branch.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/git_merge_to_main.sh" "$project_path/bin/git_merge_to_main.sh"
    cp "$SHARED_TEMPLATE_ROOT/bin/protect_branch.sh" "$project_path/bin/protect_branch.sh"
    chmod +x "$project_path/bin/git_diff_export.sh" \
        "$project_path/bin/git_diff_apply.sh" \
        "$project_path/bin/git_diff_check.sh" \
        "$project_path/bin/new_branch.sh" \
        "$project_path/bin/git_merge_to_main.sh" \
        "$project_path/bin/protect_branch.sh"
    mkdir -p "$project_path/make"
    # Offline-only tasks. add_poe_include wires the fragment in only when it is copied:
    # poe warns on every invocation for a missing include, unlike make's silent -include.
    cp "$SHARED_TEMPLATE_ROOT/poe_tasks.offline.toml" "$project_path/poe_tasks.offline.toml"
    add_poe_include "$project_path" "poe_tasks.offline.toml"
    mkdir -p "$project_path/git_diffs"
    touch "$project_path/git_diffs/.keep"
    # Swap the stock no-commit-to-branch hook for the friendly local protect-branch
    # guard that points at `make new_branch` (offline has no server-side protection).
    swap_protect_branch_hook "$project_path"
    commit_offline_artifacts "$project_path"
    print_status "success" "Offline workflow enabled (new_branch | git_merge_to_main | git_diff_* | protect-branch)"
}

# The scaffold's first commit runs before the online/offline branch, so the
# offline artifacts (local git workflow, swapped pre-commit hook, removed
# .github) would otherwise be left uncommitted. Commit them so a freshly
# scaffolded offline project starts with a clean working tree. --no-verify
# bypasses the just-installed protect-branch hook (HEAD is the default branch).
commit_offline_artifacts() {
    local project_path="$1"
    git -C "$project_path" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
    git -C "$project_path" add -A
    git -C "$project_path" commit -q --no-verify -m "chore: enable offline git workflow" || true
}

# The first commit (pushed by prompt_git_remote_setup) runs before the online versioning/docs
# rewrites (apply_online_tag_versioning + apply_online_docs_url), so pyproject.toml + Makefile +
# tasks.sh are left modified afterwards. Commit + push them so a fresh online scaffold starts with
# a clean, fully-pushed working tree. Mirrors the service tiers' commit_and_push_github_assets.
# --no-verify bypasses the test/coverage hooks (HEAD is the default branch).
commit_online_artifacts() {
    local project_path="$1"
    git -C "$project_path" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
    [ -n "$(git -C "$project_path" status --porcelain)" ] || return 0
    git -C "$project_path" add -A
    git -C "$project_path" commit -q --no-verify -m "chore: apply tag-driven versioning and docs URL" || true
    git -C "$project_path" push >/dev/null 2>&1 \
        || print_status "warning" "Could not push versioning changes; run 'git push' manually."
}

# Replace the stock pre-commit `no-commit-to-branch` hook with a local hook that
# runs bin/protect_branch.sh first (fail-fast, friendly message). Offline only.
swap_protect_branch_hook() {
    local project_path="$1"
    local pc="$project_path/.pre-commit-config.yaml"
    [ -f "$pc" ] || return 0
    python3 - "$pc" <<'PY'
import re
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    text = fh.read()

# Drop the stock no-commit-to-branch hook (its id line + the following --branch args).
text = re.sub(
    r"\n      - id: no-commit-to-branch\n(?:        args:\n          - --branch=\S+\n)?",
    "\n",
    text,
)

# Insert a local protect-branch hook as the FIRST entry of the `repos:` list so it
# fails fast before the slow test/coverage hooks.
local_hook = (
    "repos:\n"
    "  - repo: local\n"
    "    hooks:\n"
    "      - id: protect-branch\n"
    "        name: block direct commits to main/master\n"
    "        entry: bash bin/protect_branch.sh\n"
    "        language: system\n"
    "        always_run: true\n"
    "        pass_filenames: false\n"
)
text = text.replace("repos:\n", local_hook, 1)

with open(path, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
    print_status "success" "Swapped no-commit-to-branch → local protect-branch hook"
}

# Online (GitHub remote) versioning: rewrite pyproject.toml to a "0.0.0" stub +
# poetry-dynamic-versioning so the published version is derived from the git tag, and remove
# `make bump_version` (releases are cut by tagging via the CI release workflows). Offline
# scaffolds keep the static version + bump_version. See the versioning-origin-dependent lesson.
apply_online_tag_versioning() {
    local project_path="$1"
    local pyproject="$project_path/pyproject.toml"
    [ -f "$pyproject" ] || return 0
    python3 - "$pyproject" "$PROJECT_VERSION" <<'PY'
import sys

path, version = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as fh:
    text = fh.read()

# 1) Stub the version — the real one is derived from the git tag at build time.
text = text.replace(f'version = "{version}"', 'version = "0.0.0"', 1)

# 2) Insert the dynamic-versioning config just before [build-system].
dynamic_block = (
    "[tool.poetry-dynamic-versioning]\n"
    "# Published version is derived from the latest git tag matching `v$version` (e.g. v0.2.0). On\n"
    "# an exact tag the build is clean (0.2.0); off-tag builds get a PEP 440 dev version. The CI\n"
    "# release workflows pass POETRY_DYNAMIC_VERSIONING_BYPASS to build a specific version. Needs\n"
    "# `python -m build` (a PEP 517 frontend), not `poetry build` (which ignores the backend).\n"
    "enable = true\n"
    'vcs = "git"\n'
    'style = "pep440"\n'
    "\n"
    "[build-system]\n"
)
text = text.replace("[build-system]\n", dynamic_block, 1)

# 3) Swap to the poetry-dynamic-versioning build backend.
text = text.replace(
    'requires = ["poetry-core>=1.7.0"]',
    'requires = ["poetry-core>=1.7.0", "poetry-dynamic-versioning>=1.4.0,<2.0.0"]',
)
text = text.replace(
    'build-backend = "poetry.core.masonry.api"',
    'build-backend = "poetry_dynamic_versioning.backend"',
)

with open(path, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
    strip_bump_version "$project_path"
    print_status "success" "Online: tag-driven versioning (poetry-dynamic-versioning); make bump_version removed"
}

# strip_bump_version is shared across every Python scaffold — see bin/lib/common.sh.

# Online (GitHub remote) docs website: point pyproject.toml's homepage / documentation /
# [tool.poetry.urls] Documentation at the GitHub Pages docs URL that docs.yaml deploys to
# (https://<owner>.github.io/<repo>/). Online-only — an offline scaffold has no public docs site,
# so its homepage stays generic. Pairs with the repo Website field set by prompt_git_remote_setup.
apply_online_docs_url() {
    local project_path="$1"
    local pyproject="$project_path/pyproject.toml"
    [ -f "$pyproject" ] || return 0
    local docs_url="https://${GITHUB_USERNAME:-$DEFAULT_GITHUB_USERNAME}.github.io/${PROJECT_NAME}/"
    python3 - "$pyproject" "$docs_url" <<'PY'
import re
import sys

path, docs = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as fh:
    text = fh.read()

# homepage -> the docs site.
text = re.sub(r'^homepage = ".*"$', f'homepage = "{docs}"', text, count=1, flags=re.M)
# Add a documentation field right after homepage (if not already present).
if "documentation = " not in text:
    text = re.sub(
        r'(^homepage = ".*"\n)',
        rf'\1documentation = "{docs}"\n',
        text,
        count=1,
        flags=re.M,
    )
# Add a Documentation entry under [tool.poetry.urls] (after the existing "K" = "V" lines).
if '"Documentation"' not in text:
    text = re.sub(
        r'(\[tool\.poetry\.urls\]\n(?:"[^"]+" = "[^"]*"\n)*)',
        rf'\1"Documentation" = "{docs}"\n',
        text,
        count=1,
    )

with open(path, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
    print_status "success" "Online: docs website URL wired into pyproject ($docs_url)"
}

# Optional in-repo logging helper (utils/logs.py). Kept opt-in because the convention is to
# INJECT a logger, not hard-import one (see the shipped _internal/utils/CLAUDE.md and
# retry.py's LogEmitter). logs.py provides:
#   - CreateLog                                       — logger factory (console + optional file)
#   - log_message(logger, str_message, str_level)     — level-routed emit (None → timestamped print)
#   - initiate_logging(logger, path_log)              — attach handlers / a log file
prompt_logs() {
    local answer
    read -r -p "$(prompt_main "Include the in-repo logging helper (utils/logs.py)? [y/N]: ")" answer || true
    case "$answer" in
        y|Y) INCLUDE_LOGS=true; print_status "config" "logs.py: included" ;;
        *)   INCLUDE_LOGS=false ;;
    esac
}

# Q1/Q2/Q3 publish/consume selection (scaffold-publish-target-selection). The ecosystem-neutral
# questions, resolved for Python: official public registry = PyPI, staging/sandbox = Test PyPI,
# private/non-official source = a PEP 503 index or git source. Only the selected release workflows
# are emitted; Q3 wires a consumer-side source. Empty answers (non-interactive --dev) take the
# shown defaults, preserving the prior behaviour.
prompt_publish_targets() {
    local answer
    # Two orthogonal axes, banner-separated so Q3 doesn't read as a fork of Q1/Q2:
    # publishing = where THIS library ships to; consuming = where its own deps come from.
    print_status "section" "Publishing — where this library ships to"
    read -r -p "$(prompt_main "Publish to the official public registry (PyPI)? [Y/n]: ")" answer || true
    case "$answer" in n | N) PUBLISH_PYPI=false ;; *) PUBLISH_PYPI=true ;; esac
    print_status "config" "Publish target PyPI: $PUBLISH_PYPI"

    read -r -p "$(prompt_main "Add a staging/sandbox registry (Test PyPI) first? [Y/n]: ")" answer || true
    case "$answer" in n | N) PUBLISH_TEST_PYPI=false ;; *) PUBLISH_TEST_PYPI=true ;; esac
    print_status "config" "Staging registry Test PyPI: $PUBLISH_TEST_PYPI"

    print_status "section" "Consuming — where this library's own dependencies come from"
    read -r -p "$(prompt_main "Consume this library from a non-official source (private index / git)? [y/N]: ")" answer || true
    case "$answer" in y | Y) CONSUME_PRIVATE=true ;; *) CONSUME_PRIVATE=false ;; esac
    print_status "config" "Private consumer source: $CONSUME_PRIVATE"
}

# Q3 consumer-side wiring: when the library will be consumed from a non-official source, append a
# documented (commented) explicit-priority source block to pyproject. priority = "explicit" is the
# dependency-confusion guard — poetry/pip never falls back to it for other packages.
apply_private_consumer_source() {
    local project_path="$1"
    [[ "$CONSUME_PRIVATE" == "true" ]] || return 0
    local pyproject="$project_path/pyproject.toml"
    [ -f "$pyproject" ] || return 0
    cat >> "$pyproject" <<'EOF'

# --- Private / non-official consumer source (uncomment and fill in) --------------------------
# Install this package from a source other than PyPI (a private PEP 503 index, or a git source).
# Use priority = "explicit" so poetry/pip NEVER falls back to it for other packages — the
# dependency-confusion guard. Authenticate with:
#   poetry config http-basic.private <user> <token>
# and, for pip, use --index-url (never --extra-index-url).
# [[tool.poetry.source]]
# name = "private"
# url = "https://your-private-index.example/simple/"
# priority = "explicit"
EOF
    print_status "success" "Q3: private consumer-source template appended to pyproject.toml"
}

# Optional Docker Compose DB infrastructure (mirrors the DDD/MVC prompt). A library rarely
# needs it, but the seam is offered for libs whose integration tests spin up a real DB.
prompt_docker_compose() {
    local answer db_ans
    read -r -p "$(prompt_main "Include Docker Compose for database infrastructure? [y/N]: ")" answer || true
    case "$answer" in
        y|Y)
            INCLUDE_DOCKER_COMPOSE=true
            read -r -p "$(prompt_sub "Which database backend? [postgresql/mariadb/mysql] (default: postgresql): ")" db_ans || true
            case "${db_ans:-postgresql}" in
                mariadb|mysql) DB_COMPOSE_BACKEND="$db_ans" ;;
                *) DB_COMPOSE_BACKEND="postgresql" ;;
            esac
            print_status "config" "Docker Compose: $DB_COMPOSE_BACKEND"
            ;;
        *)
            INCLUDE_DOCKER_COMPOSE=false
            ;;
    esac
}

conditional_copy_docker_compose() {
    local project_path="$1"
    if [[ "$INCLUDE_DOCKER_COMPOSE" != "true" ]]; then return; fi
    cp "$COMMON_TEMPLATE_ROOT/docker-compose.${DB_COMPOSE_BACKEND}.yml" "$project_path/docker-compose.yml"
    print_status "success" "docker-compose.yml (${DB_COMPOSE_BACKEND}) copied"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    PROJECT_PATH="$PROJECT_ROOT/$PROJECT_NAME"

    print_section "Python lib-minimal scaffold"
    print_status "config" "Target: $PROJECT_PATH"

    validate_inputs
    resolve_github_username
    prompt_logs
    prompt_docker_compose
    prompt_publish_targets
    PROJECT_DISPLAY_NAME="$(format_display_name "$PROJECT_NAME")"
    create_directory_structure "$PROJECT_PATH"
    create_python_files "$PROJECT_PATH"
    copy_internal_utils "$PROJECT_PATH"
    copy_internal_config "$PROJECT_PATH"
    copy_internal_ports "$PROJECT_PATH"
    copy_templates "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    apply_private_consumer_source "$PROJECT_PATH"
    conditional_copy_docker_compose "$PROJECT_PATH"
    copy_mkdocs_templates "$PROJECT_PATH"
    # Every `cp -r` above copies whatever sits in templates/, caches included (#205).
    scaffold_purge_caches "$PROJECT_PATH"
    initialize_git_repo "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    # When the project is not connected to a GitHub remote (no upstream tracking
    # branch after setup), switch to offline mode: drop GitHub-only assets and
    # ship the git-diff sync workflow instead.
    # ⚠️ `@{u}` alone answers "is there an upstream?", never "is it OUR upstream?" — it is TRUE
    # for a pre-existing clone whose origin points elsewhere. Offline is the safe default, so
    # an unverified remote falls here too (#212, raised by review on #215).
    if [ "$SCAFFOLD_REMOTE_VERIFIED" != "1" ] \
        || ! git -C "$PROJECT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        apply_offline_mode "$PROJECT_PATH"
    else
        apply_online_tag_versioning "$PROJECT_PATH"
        apply_online_docs_url "$PROJECT_PATH"
        # The generic service release.yaml (tag + GitHub Release, no publish) does not apply to a
        # library — the lib ships its own release-pypi.yaml / release-test-pypi.yaml. The lib copy
        # step doesn't pull it in today, but strip defensively so a future copy-list change can't
        # leak it. Only report when a file was actually removed — never claim a no-op removal.
        if [[ -f "$PROJECT_PATH/.github/workflows/release.yaml" ]]; then
            rm -f "$PROJECT_PATH/.github/workflows/release.yaml"
            print_status "success" "Library: generic service release.yaml removed (uses release-pypi instead)"
        fi
        # Sweep the online versioning/docs rewrites into a commit + push (they run after the first
        # pushed commit) so the scaffold ends with a clean working tree.
        commit_online_artifacts "$PROJECT_PATH"
    fi

    print_status "success" "Lib-minimal scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
}

main
