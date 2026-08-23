#!/usr/bin/env bash
# Negative control for blueprintx#113 — a project name carries TWO identities.
#
# A PyPI *distribution* name may contain hyphens; a Python *import package* may not.
# The scaffold used to conflate them, writing `src/my-lib/` and rendering
# `from my-lib.main import main` into the generated tests — a parse-time SyntaxError.
#
# The defect hid because the two obvious checks both PASS on the broken form:
# the top-level `__init__` compiles (it imports nothing from itself), and
# `importlib.import_module("my-lib")` succeeds on the string form. Only a submodule
# import written as SOURCE breaks, so this control renders the real templates with a
# hyphenated name and asks Python to COMPILE the result.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"

int_failures=0

fail() {
    print_status "error" "$1"
    int_failures=$((int_failures + 1))
}

assert_eq() {
    local str_actual="$1" str_expected="$2" str_what="$3"
    [ "$str_actual" = "$str_expected" ] ||
        fail "$str_what: expected '$str_expected', got '$str_actual'"
}

# --- the derivation ---------------------------------------------------------

assert_eq "$(to_import_package_name "filings-b3")" "filings_b3" "hyphen becomes underscore"
assert_eq "$(to_import_package_name "duskko")" "duskko" "a clean name is untouched"
assert_eq "$(to_import_package_name "a-b-c")" "a_b_c" "every hyphen, not just the first"

# --- the validator ----------------------------------------------------------

for str_good in duskko filings-b3 my_lib _private a1; do
    is_valid_project_name "$str_good" || fail "'$str_good' should be accepted"
done
# A hyphen is rescued by the derivation; these are not, so they must be refused at
# the prompt rather than shipped as a package nobody can import.
for str_bad in "1lib" "my.lib" "my lib" "my/lib" ""; do
    ! is_valid_project_name "$str_bad" || fail "'$str_bad' should be rejected"
done

# --- the rendered templates actually COMPILE --------------------------------

if ! command -v envsubst >/dev/null 2>&1; then
    fail "envsubst is required to render the templates — install gettext"
else
    str_tmp="$(mktemp -d)"
    trap 'rm -rf "$str_tmp"' EXIT

    str_dist="filings-b3"
    str_pkg="$(to_import_package_name "$str_dist")"
    int_rendered=0

    for str_tmpl in "$REPO_ROOT"/templates/lib-minimal/rendered/*.tmpl; do
        [ -f "$str_tmpl" ] || continue
        str_out="$str_tmp/$(basename "$str_tmpl" .tmpl)"
        PROJECT_NAME="$str_dist" PROJECT_PKG_NAME="$str_pkg" \
            envsubst '${PROJECT_NAME} ${PROJECT_PKG_NAME}' <"$str_tmpl" >"$str_out"
        # Compile, never import: the modules these render import a package that does
        # not exist here. A hyphen fails at COMPILE time, which is the whole point.
        if ! python3 -m py_compile "$str_out" 2>/dev/null; then
            fail "$(basename "$str_tmpl") does not compile when the dist name is hyphenated"
            grep -n '^from\|^import' "$str_out" >&2 || true
        fi
        int_rendered=$((int_rendered + 1))
    done

    # A gate that discovers nothing must not report success — the failure mode this
    # repo writes gates to prevent.
    [ "$int_rendered" -gt 0 ] ||
        fail "no .tmpl files discovered under templates/lib-minimal/rendered/"
fi

# --- no template may build an import out of the DIST name -------------------

if grep -rn 'from \${PROJECT_NAME}\|import \${PROJECT_NAME}' "$REPO_ROOT/templates/" 2>/dev/null; then
    fail "a template builds an import from the distribution name (use \${PROJECT_PKG_NAME})"
fi

if [ "$int_failures" -gt 0 ]; then
    print_status "error" "project-name identities: $int_failures failure(s)"
    exit 1
fi

print_status "success" "project-name identities OK ($int_rendered template(s) rendered and compiled)"
