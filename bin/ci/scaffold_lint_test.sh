#!/usr/bin/env bash

set -euo pipefail

SKELETON="${1:?skeleton name required}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=bin/lib/spec.sh
source "$REPO_ROOT/bin/lib/spec.sh"

if grep -nE 'cp .*\.github/CODEOWNERS' "$REPO_ROOT"/bin/scaffold/*.sh; then
    echo "ERROR: a scaffold copies CODEOWNERS with cp; render it with envsubst '\${GITHUB_USERNAME}'" >&2
    exit 1
fi
META="$REPO_ROOT/templates/$SKELETON/skeleton.meta"

[ -f "$META" ] || { echo "ERROR: skeleton '$SKELETON' not found" >&2; exit 1; }

str_language="$(grep '^language=' "$META" | cut -d= -f2-)"
if [ "$str_language" != "python" ]; then
    echo "Skipping '$SKELETON' — not a Python skeleton (language=$str_language)."
    exit 0
fi

str_scaffold_rel="$(grep '^scaffold=' "$META" | cut -d= -f2-)"
[ -n "$str_scaffold_rel" ] || { echo "ERROR: no scaffold= in $META" >&2; exit 1; }

git config --global user.email >/dev/null 2>&1 || git config --global user.email "ci-bot@example.com"
git config --global user.name >/dev/null 2>&1 || git config --global user.name "ci-bot"

source "$REPO_ROOT/bin/lib/no_background_git.sh"

WORK_DIR="$(mktemp -d)"
PROJECT_NAME="${SCAFFOLD_PROJECT_NAME:-ci-scaffold}"
PROJECT_PATH="$WORK_DIR/$PROJECT_NAME"

SEEDED_CACHES=(
    "$REPO_ROOT/templates/$SKELETON/src/__pycache__"
    "$REPO_ROOT/templates/$SKELETON/src/.pytest_cache"
    "$REPO_ROOT/templates/python-common/src/utils/__pycache__"
    "$REPO_ROOT/templates/python-common/src/utils/.ruff_cache"
    "$REPO_ROOT/templates/python-common/optional/typing/__pycache__"
    "$REPO_ROOT/templates/python-common/optional/typing/.mypy_cache"
)
SEEDED_FILES=(
    "$REPO_ROOT/templates/python-common/src/utils/seeded_probe.pyc"
    "$REPO_ROOT/templates/python-common/src/utils/seeded_probe.pyo"
)
cleanup() {
    local int_rc=$?
    rm -rf "$WORK_DIR" "${SEEDED_CACHES[@]}" "${SEEDED_FILES[@]}" || true
    return "$int_rc"
}
trap cleanup EXIT

int_seeded=0
for str_cache in "${SEEDED_CACHES[@]}"; do
    [ -d "$(dirname "$str_cache")" ] || continue
    mkdir -p "$str_cache"
    printf 'seeded by scaffold_lint_test.sh\n' >"$str_cache/seeded.cpython-000.pyc"
    int_seeded=$((int_seeded + 1))
done
for str_file in "${SEEDED_FILES[@]}"; do
    [ -d "$(dirname "$str_file")" ] || continue
    printf 'seeded by scaffold_lint_test.sh\n' >"$str_file"
    int_seeded=$((int_seeded + 1))
done
[ "$int_seeded" -ge 4 ] || {
    echo "ERROR: seeded $int_seeded fixture(s) — too few for the purge check to mean anything" >&2
    exit 1
}

str_opt_label="${SCAFFOLD_SPEC_FILE:+opt-ins from $SCAFFOLD_SPEC_FILE}"
echo "::group::Scaffold $SKELETON (offline, ${str_opt_label:-no opt-ins})"
spec_skeleton_supported "$SKELETON" || {
    echo "ERROR: bin/lib/spec.sh has no named-key prompt map for '$SKELETON'" >&2
    exit 1
}
if [ -n "${SCAFFOLD_SPEC_FILE:-}" ] && { [ ! -f "$SCAFFOLD_SPEC_FILE" ] || [ ! -r "$SCAFFOLD_SPEC_FILE" ]; }; then
    echo "ERROR: SCAFFOLD_SPEC_FILE is set but is not a readable file: $SCAFFOLD_SPEC_FILE" >&2
    exit 1
fi
spec_validate_answers "$SKELETON" "${SCAFFOLD_SPEC_FILE:-}" || exit 1
spec_stdin_for_skeleton "$SKELETON" "${SCAFFOLD_SPEC_FILE:-}" \
    | BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot bash "$REPO_ROOT/$str_scaffold_rel" \
        "$WORK_DIR" "$PROJECT_NAME" "CI scaffold lint+test" "0.0.1"
echo "::endgroup::"

str_leaked="$(find "$PROJECT_PATH" \
    \( -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' \
    -o -name '.mypy_cache' \) -o -type f -name '*.py[cod]' \) -print)"
if [ -n "$str_leaked" ]; then
    echo "ERROR: the scaffold shipped interpreter/tool caches into the generated project:" >&2
    echo "$str_leaked" >&2
    exit 1
fi
echo "No interpreter/tool caches leaked into the generated project."

for str_online_only in coderabbit_trigger.yaml review_threads.yaml review_retry.yaml secret_scan.yaml; do
    if [ -e "$PROJECT_PATH/.github/workflows/$str_online_only" ]; then
        echo "ERROR: offline scaffold shipped the GitHub-only $str_online_only" >&2
        exit 1
    fi
done
echo "No GitHub-only workflows in the offline project."

bash "$REPO_ROOT/bin/ci/check_review_config_shipped.sh" --project "$PROJECT_PATH"

bash "$PROJECT_PATH/bin/check_specs_structure.sh" --root "$PROJECT_PATH"
str_probe="$(mktemp -d)"
cp -r "$PROJECT_PATH/.specs" "$str_probe/.specs"
touch "$str_probe/.specs/notes.md"
if bash "$PROJECT_PATH/bin/check_specs_structure.sh" --root "$str_probe" >/dev/null 2>&1; then
    echo "ERROR: the project's .specs/ gate accepted a stray top-level note" >&2
    rm -rf "$str_probe"
    exit 1
fi
rm -rf "$str_probe"
echo "The project's .specs/ gate passes its skeleton and rejects a stray note."

bash "$PROJECT_PATH/bin/check_docs_boundary.sh" --root "$PROJECT_PATH"
str_probe="$(mktemp -d)"
cp -r "$PROJECT_PATH/docs" "$str_probe/docs"
mkdir -p "$str_probe/docs/backlog"
touch "$str_probe/docs/backlog/x.md"
if bash "$PROJECT_PATH/bin/check_docs_boundary.sh" --root "$str_probe" >/dev/null 2>&1; then
    echo "ERROR: the project's docs/ boundary gate accepted docs/backlog/x.md" >&2
    rm -rf "$str_probe"
    exit 1
fi
rm -rf "$str_probe"
echo "The project's docs/ gate passes its skeleton and rejects docs/backlog/."

cd "$PROJECT_PATH"

echo "::group::poetry install (runtime + dev)"
poetry install --with dev --no-interaction --no-ansi
echo "::endgroup::"

git add -A
git commit -q --no-verify -m "ci: scaffold baseline" || true

poetry run pre-commit run docs-gap --all-files
python3 - <<'PY'
s = open("mkdocs.yml").read()
rows = "".join(f"  - X{n}: index.md\n" for n in range(9))
open("mkdocs.yml", "w").write(s.replace("nav:\n", "nav:\n" + rows, 1))
PY
str_gap_out="$(poetry run pre-commit run docs-gap --all-files 2>&1)" && int_gap_rc=0 || int_gap_rc=$?
git checkout -q -- mkdocs.yml
if [ "$int_gap_rc" -eq 0 ] || ! grep -q "top-level nav entries" <<<"$str_gap_out"; then
    echo "ERROR: [$SKELETON] the docs-gap hook did not reject a nav over the ceiling:" >&2
    echo "$str_gap_out" >&2
    exit 1
fi
echo "The project's docs-gap hook passes its nav and rejects a flat one over the ceiling."

if ! git ls-files --error-unmatch poetry.lock >/dev/null 2>&1; then
    echo "ERROR: [$SKELETON] the generated project does not TRACK poetry.lock." >&2
    echo "       It exists on disk but git is ignoring it — check .gitignore for a" >&2
    echo "       lock pattern. An untracked lockfile makes the project unreproducible" >&2
    echo "       for anyone who clones it." >&2
    git check-ignore -v poetry.lock >&2 || true
    exit 1
fi
echo "The generated project tracks poetry.lock."

str_cz_version="$(poetry run cz version --project 2>/dev/null || true)"
case "$str_cz_version" in
    [0-9]*.[0-9]*.[0-9]*) echo "commitizen resolves its config ($str_cz_version)." ;;
    *)
        echo "ERROR: [$SKELETON] commitizen cannot resolve the project version." >&2
        echo "       Got: '${str_cz_version:-<empty>}'" >&2
        echo "       .cz.toml is probably missing from this tier's scaffold copy list —" >&2
        echo "       cz falls back to defaults silently (exit 0), so nothing else notices." >&2
        exit 1
        ;;
esac

echo "::group::poe lint (must leave the tree unchanged)"
bash bin/poe_exec.sh lint
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: 'poe lint' modified the freshly scaffolded tree:" >&2
    git status --short >&2
    git --no-pager diff >&2
    exit 1
fi
echo "poe lint left the tree clean."
echo "::endgroup::"

echo "::group::poe unit_tests"
bash bin/poe_exec.sh unit_tests
echo "::endgroup::"

echo "::group::poe integration_tests"
bash bin/poe_exec.sh integration_tests || [ $? -eq 5 ]
echo "::endgroup::"

echo "OK: $SKELETON scaffolds clean, lints clean, and unit + integration tests pass."
