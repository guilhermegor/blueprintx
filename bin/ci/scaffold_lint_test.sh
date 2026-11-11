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

export DOCS_LOCALE="${DOCS_LOCALE:-en}"
case "$DOCS_LOCALE" in
    en|pt-BR) ;;
    *) echo "ERROR: DOCS_LOCALE must be en or pt-BR, got '$DOCS_LOCALE'" >&2; exit 1 ;;
esac
str_opt_label="${SCAFFOLD_SPEC_FILE:+opt-ins from $SCAFFOLD_SPEC_FILE}"
echo "::group::Scaffold $SKELETON (offline, docs_locale=$DOCS_LOCALE, ${str_opt_label:-no opt-ins})"
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
    | BLUEPRINTX_STDIN_ANSWERS=1 GITHUB_USERNAME=ci-bot LINKEDIN_URL=https://www.linkedin.com/in/ci-bot \
        bash "$REPO_ROOT/$str_scaffold_rel" \
        "$WORK_DIR" "$PROJECT_NAME" "CI scaffold lint+test" "0.0.1"
echo "::endgroup::"

[[ -f "$PROJECT_PATH/mkdocs.yml" ]] || {
    echo "ERROR: the scaffold did not generate $PROJECT_PATH/mkdocs.yml" >&2
    exit 1
}
if ! grep -Eq "^[[:space:]]+language:[[:space:]]*[\"']?${DOCS_LOCALE}[\"']?[[:space:]]*(#.*)?$" "$PROJECT_PATH/mkdocs.yml"; then
    echo "ERROR: DOCS_LOCALE=$DOCS_LOCALE did not reach the generated mkdocs.yml (language:)" >&2
    exit 1
fi
echo "Generated mkdocs.yml carries language: $DOCS_LOCALE."

str_leaked="$(find "$PROJECT_PATH" \
    \( -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' \
    -o -name '.mypy_cache' \) -o -type f -name '*.py[cod]' \) -print)"
if [ -n "$str_leaked" ]; then
    echo "ERROR: the scaffold shipped interpreter/tool caches into the generated project:" >&2
    echo "$str_leaked" >&2
    exit 1
fi
echo "No interpreter/tool caches leaked into the generated project."

for str_online_only in coderabbit-trigger.yml review-threads.yml review-retry.yml secret-scan.yml; do
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

bash "$PROJECT_PATH/bin/check_readme_structure.sh" "$PROJECT_PATH/README.md"
str_probe="$(mktemp -d)"
sed 's/^## Overview$/## 🚀 Overview/' "$PROJECT_PATH/README.md" >"$str_probe/emoji.md"
grep -vF '<!-- slug: license -->' "$PROJECT_PATH/README.md" >"$str_probe/no-license.md"
for str_broken in emoji no-license; do
    if bash "$PROJECT_PATH/bin/check_readme_structure.sh" "$str_probe/$str_broken.md" >/dev/null 2>&1; then
        echo "ERROR: the project's README gate accepted a README with: $str_broken" >&2
        rm -rf "$str_probe"
        exit 1
    fi
done
rm -rf "$str_probe"
echo "The project's README gate passes its skeleton and rejects an emoji heading and a missing core section."

cd "$PROJECT_PATH"

echo "::group::poetry install (runtime + dev)"
poetry install --with dev --no-interaction --no-ansi
echo "::endgroup::"

git add -A
git commit -q --no-verify -m "ci: scaffold baseline" || true

git branch -M main
str_clean_sha="$(git rev-parse HEAD)"
mkdir -p tests/unit
printf 'def test_probe():\n    assert 1 + 1 == 2\n' >tests/unit/test_probe.py
git add tests/unit/test_probe.py
git commit -q --no-verify -m "test: probe"
git checkout -q -b assertion-probe
printf 'def test_probe():\n    assert 1 + 1 in (2, 3)\n' >tests/unit/test_probe.py
git add tests/unit/test_probe.py
git commit -q --no-verify -m "test: weaken probe"
str_aw_out="$(poetry run python bin/check_assertion_weakening.py 2>&1)" && int_aw_rc=0 || int_aw_rc=$?
if [ "$int_aw_rc" -eq 0 ] || ! grep -q "operator weakened from == to in" <<<"$str_aw_out"; then
    echo "ERROR: [$SKELETON] the assertion-weakening gate accepted == weakened to in:" >&2
    echo "$str_aw_out" >&2
    exit 1
fi
str_aw_hook="$(poetry run pre-commit run assertion-weakening --all-files 2>&1)" && int_aw_hook_rc=0 || int_aw_hook_rc=$?
if [ "$int_aw_hook_rc" -eq 0 ] || ! grep -q "operator weakened from == to in" <<<"$str_aw_hook"; then
    echo "ERROR: [$SKELETON] the assertion-weakening hook did not fire:" >&2
    echo "$str_aw_hook" >&2
    exit 1
fi
git checkout -q main
git branch -q -D assertion-probe
git reset -q --hard "$str_clean_sha"
echo "The project's assertion-weakening hook rejects == weakened to in."

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

poetry run python "$REPO_ROOT/bin/ci/check_poe_task_set.py" "$SKELETON"
bash bin/poe_exec.sh --help >/dev/null

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

echo "::group::final tree is self-consistent"
poetry install --only docs --no-root --no-interaction --no-ansi
poetry run mkdocs build --strict -d "$(mktemp -d)"
git add -A
git diff --cached --quiet \
    || { echo "ERROR: [$SKELETON] the tree has uncommitted changes after the run:" >&2; git status --short >&2; exit 1; }
str_pushed_note="push check skipped (no origin remote)"
if git remote get-url origin >/dev/null 2>&1; then
    str_pushed_note="pushed"
    git rev-parse --verify -q main >/dev/null \
        || { echo "ERROR: [$SKELETON] local branch main is missing; cannot prove it was pushed." >&2; exit 1; }
    git rev-parse --verify -q origin/main >/dev/null \
        || { echo "ERROR: [$SKELETON] origin is set but origin/main is missing; cannot prove main was pushed." >&2; exit 1; }
    [ -z "$(git rev-list origin/main..main)" ] \
        || { echo "ERROR: [$SKELETON] local main has commits origin/main lacks:" >&2; git rev-list --oneline origin/main..main >&2; exit 1; }
fi
[ ! -e .specs/.specs ] \
    || { echo "ERROR: [$SKELETON] nested .specs/.specs was scaffolded." >&2; exit 1; }
echo "Final tree: committed, $str_pushed_note, no nested .specs, mkdocs --strict builds."
echo "::endgroup::"

if [ "$SKELETON" = "lib-minimal" ]; then
    echo "::group::built wheel carries py.typed"
    poetry build -f wheel --no-interaction --no-ansi
    # shellcheck source=bin/lib/common.sh
    source "$REPO_ROOT/bin/lib/common.sh"
    str_member="$(to_import_package_name "$PROJECT_NAME")/py.typed"
    list_wheels=(dist/*.whl)
    [ "${#list_wheels[@]}" -eq 1 ] && [ -f "${list_wheels[0]}" ] \
        || { echo "ERROR: expected exactly one built wheel in dist/" >&2; exit 1; }
    python3 -c 'import sys, zipfile; sys.exit(sys.argv[2] not in zipfile.ZipFile(sys.argv[1]).namelist())' \
        "${list_wheels[0]}" "$str_member" \
        || { echo "ERROR: $str_member missing from wheel" >&2; exit 1; }
    echo "::endgroup::"
fi

echo "OK: $SKELETON scaffolds clean, lints clean, and unit + integration tests pass."
