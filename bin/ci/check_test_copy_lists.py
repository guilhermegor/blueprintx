"""Every shared unit test must be reachable by each scaffold's copy list.

``templates/python-common/tests/unit/`` is the single source for the tests shared by all Python
tiers, but nothing copies that directory wholesale. Each ``bin/scaffold/python_*.sh`` reaches it
two ways:

1. an explicit ``cp .../tests/unit/test_x.py`` line — used for the gate and example tests;
2. the ``copy_shared_utils`` loop, which copies ``test_<util>.py`` alongside ``<util>.py`` for
   each name in its list — so those tests travel with their subject and cannot be forgotten.

A test that matches **neither** is written, committed, and silently never runs in any generated
project. That is the failure this gate exists for, and it is invisible from every angle that
normally reports: the template's own suite runs it and passes, `make lint` is clean, and the
scaffolded project is green — green because the file is not there to fail.

🔴 **Before this gate the only available signal was the test COUNT**, and nobody compares it
against an expectation: a run that adds 18 tests and still prints 234 is exactly as green as one
printing 252. The count is weak even when read, because an unchanged total hides one test
vanishing while another appears. So this gate does not count — it compares **sets**: each
scaffold's reachable shared-test set against the set that exists on disk, naming every absentee.

Deliberate exclusions live in ``DICT_EXPECTED_ABSENT`` with a reason each — a tier that
genuinely should not receive a test (``lib-minimal`` has no service config, so the env-config
and contract-oracle tests do not apply there).
"""

import pathlib
import re
import sys


_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SHARED_TESTS = _ROOT / "templates/python-common/tests/unit"
_SHARED_WORKFLOWS = _ROOT / "templates/python-common/.github/workflows"
_SCAFFOLD_DIR = _ROOT / "bin/scaffold"

# Workflows are the SECOND hand-maintained copy list with exactly this defect shape, and it is
# worse there: a CI job that no scaffold copies is not a test that silently does not run, it is
# a GATE that silently does not exist in any generated project — and nothing anywhere reports a
# workflow that was never installed. Found by adding `review_threads.yaml` and noticing the cp
# list would not carry it.
DICT_WORKFLOWS_EXPECTED_ABSENT = {
    "python_lib_minimal.sh": {
        # A library publishes to PyPI through its own release-pypi / release-test-pypi pair.
        "release.yaml": "lib-minimal ships its own release-pypi workflows",
        # Contract drift describes an ingested external file; a library tier registers none.
        "contract_drift.yaml": "lib-minimal ships no contract oracle registry",
    },
}

# blueprintx#359: NOT a clean exclusion — a known, temporary gap recorded honestly rather than
# hidden behind a bare "I forgot". The one shared cp-list lives in
# `bin/lib/scaffold_python_templates.sh`, locked by open PRs #316/#319/#403/#406 at the time
# `test_gate_integrity_gate.py` was added — editing it here would conflict with all four. Wire
#     cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_gate_integrity_gate.py" \
#         "$str_project_path/tests/unit/test_gate_integrity_gate.py"
# beside the test_rmw_race_gate.py entry once unblocked, then remove this exclusion from all 5
# scaffolds below.
_STR_GATE_INTEGRITY_TEST_BLOCKED = (
    "cp blocked by locked bin/lib/scaffold_python_templates.sh (#316/#319/#403/#406) — wire "
    "beside test_rmw_race_gate.py once unblocked (#359)"
)

# Tests a given scaffold deliberately does NOT copy, with the reason. An entry here is a claim
# that the tier cannot use the test, not a shortcut for "I forgot to wire it".
DICT_EXPECTED_ABSENT = {
    "python_lib_minimal.sh": {
        # A distributable library has no runtime .env to read, so the service tiers'
        # env-config seam (and its test) is not shipped.
        "test_env_config.py": "lib-minimal ships no src/config/env_config.py",
        # A clean exclusion, not the vendoring hole below: the per-engine query loader
        # resolves config/queries/<DB_BACKEND>/, and a distributable library selects no
        # database engine and ships no queries directory. utils/queries.py is not vendored
        # into lib-minimal at all, so its test has nothing to cover.
        "test_queries.py": "lib-minimal ships no DB engine selection or queries/ tree",
        # Contract oracles describe an ingested external file; a library tier ships none.
        "test_contract_oracle_example.py": "lib-minimal ships no contract oracle registry",
        # The weekly drift reporter re-fetches the sources in config/contract_oracles.yaml;
        # a library tier ships neither the registry nor bin/check_contract_drift.py, so the
        # test would have no module to load.
        "test_contract_drift.py": "lib-minimal ships no contract_drift driver or registry",
        # The gate walks src/ packages that declare __all__; lib-minimal declares none.
        "test_all_exports_gate.py": "lib-minimal ships no package declaring __all__",
        "test_contract_family_conventions.py": "lib-minimal ships no contract family",
        # startup.py is a service-tier singleton; a library has no import-time bootstrap.
        "test_startup_fragility_order.py": "lib-minimal ships no src/config/startup.py",
        # verify_venv_imports.py is invoked only from bin/lib/pip_fallback.sh, and lib-minimal
        # copies only bin/lib/common.sh (line ~680) — no bootstrap.sh, pip_fallback.sh, venv.sh
        # or run.sh, so it has no pip-fallback bootstrap to guard in the first place.
        "test_verify_venv_imports.py": "lib-minimal ships no bin/lib/pip_fallback.sh bootstrap",
        # NOT missing — DELIVERED BY A THIRD MECHANISM this gate does not model: the scaffold
        # RENDERS it from templates/lib-minimal/rendered/test_typing.py.tmpl via envsubst,
        # because the file needs the package name substituted in and covers a smaller matrix
        # than the service tiers'. (It was a heredoc until blueprintx#189 moved it into a
        # template file; the mechanism changed, the exclusion did not.) Verified present and
        # running in a real lib-minimal scaffold. Modelling the render would mean a third
        # parser for one case; the stale-exclusion check below will flag this entry the day
        # it becomes an ordinary `cp` from python-common.
        "test_typing.py": "lib-minimal RENDERS it from a template, not a cp",
        # ⚠️ NOT a clean exclusion — a known gap, recorded honestly rather than hidden.
        # lib-minimal vendors the shared helpers into `<pkg>/_internal/utils/` and rewrites
        # their import prefix, so these tests — written against the service tiers' flat
        # `utils.x` layout — would not resolve as copied. The modules therefore ship into
        # every generated library WITHOUT their tests. Fixing it means running the same
        # `rewrite_internal_imports` over the test files; until then this is a documented
        # hole, not a design decision.
        "test_br_identifiers.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_dates.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_decimals.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_dtypes.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_frames.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_http_downloader.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_logs.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_logs_emitter.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_ms_office_outlook_gateway.py": (
            "lib-minimal vendors utils under _internal/ (import rewrite)"
        ),
        "test_paths.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_provenance.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_daily_cache.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_raw_workspace.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_retry.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_sidecar_metadata.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_signatures.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_tabular_reader.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_xml_reader.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_text.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_zip_extractor.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        # ms_office/ (Outlook automation, Excel sheet-name rules) and email/ (dispatch
        # orchestration) are service-tier concerns (blueprintx#118/#121) — lib-minimal ships
        # neither package, so their tests have no module here to cover.
        "test_ms_office_excel_sheet_names.py": "lib-minimal does not ship ms_office/",
        "test_email_dispatch.py": "lib-minimal does not ship email/",
        "test_email_sender.py": "lib-minimal does not ship email/",
        "test_email_html_body.py": "lib-minimal does not ship email/",
        # ⚠️ NOT a clean exclusion — the config/schemas/ seam (blueprintx#267) ships in
        # src/config/schemas/ here, but `pydantic` is not yet a declared dependency in ANY
        # tier's pyproject.toml (that needs its own explicit yes, priced separately per the
        # issue), so wiring the cp line now would ship a test that imports a package the
        # generated project never installs. Remove this exclusion together with the cp line
        # the day pydantic lands as a dependency.
        "test_config_schemas_example.py": "schemas/ pydantic dep not yet wired (#267)",
        "test_gate_integrity_gate.py": _STR_GATE_INTEGRITY_TEST_BLOCKED,
        "test_ruff_ret_rule.py": _STR_GATE_INTEGRITY_TEST_BLOCKED,
    },
    "python_ddd_service.sh": {
        "test_config_schemas_example.py": "schemas/ pydantic dep not yet wired (#267)",
        "test_gate_integrity_gate.py": _STR_GATE_INTEGRITY_TEST_BLOCKED,
        "test_ruff_ret_rule.py": _STR_GATE_INTEGRITY_TEST_BLOCKED,
    },
    "python_ddd_service_orm.sh": {
        "test_config_schemas_example.py": "schemas/ pydantic dep not yet wired (#267)",
        "test_gate_integrity_gate.py": _STR_GATE_INTEGRITY_TEST_BLOCKED,
        "test_ruff_ret_rule.py": _STR_GATE_INTEGRITY_TEST_BLOCKED,
    },
    "python_mvc_service.sh": {
        "test_config_schemas_example.py": "schemas/ pydantic dep not yet wired (#267)",
        "test_gate_integrity_gate.py": _STR_GATE_INTEGRITY_TEST_BLOCKED,
        "test_ruff_ret_rule.py": _STR_GATE_INTEGRITY_TEST_BLOCKED,
    },
    "python_mvc_service_orm.sh": {
        "test_config_schemas_example.py": "schemas/ pydantic dep not yet wired (#267)",
        "test_gate_integrity_gate.py": _STR_GATE_INTEGRITY_TEST_BLOCKED,
        "test_ruff_ret_rule.py": _STR_GATE_INTEGRITY_TEST_BLOCKED,
    },
}

# ⚠️ Both patterns must prove a COPY, not merely a mention.
#
# An earlier version matched `tests/unit/(test_x.py)` anywhere in the file, so a filename inside
# a comment — or inside this gate's own exclusion prose quoted into a script — counted as
# delivery. Likewise it accepted the first `for util in …; do` anywhere, without checking the
# loop actually copies the test. Either way the gate could report a scaffold as complete while
# the file never arrives, which is a FALSE PASS in the one direction that matters: the whole
# point is catching a test that silently never runs.
#
# So: the explicit form must be an active `cp` command whose SOURCE is the shared tests dir, and
# the loop form must be the real `copy_shared_utils` body containing a `cp` of `test_${util}.py`.

# `cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_x.py" …` — anchored on `cp` and on the source root,
# and rejecting a leading `#` so a commented-out line never counts.
_RE_EXPLICIT_CP = re.compile(
    r"^[^\S\n]*(?!#)\S*\bcp\b[^\n]*?COMMON_TEMPLATE_ROOT/tests/unit/(test_[a-z0-9_]+\.py)",
    re.M,
)

# Same anchoring for the workflow copy list, plus one more constraint the test form does not
# need: the shared path must be the **SOURCE operand**, i.e. immediately after `cp` and its
# flags. Allowing it anywhere on the line counts a REVERSE copy —
#   cp "$project_path/.github/workflows/tests.yaml" "$COMMON_TEMPLATE_ROOT/.github/workflows/tests.yaml"
# — as delivery, when it installs nothing in the generated project. Verified: the looser regex
# reported `tests.yaml` reachable from exactly that line.
_RE_WORKFLOW_CP = re.compile(
    # `cp`, then only FLAGS, then the shared path as the first operand. Anything else between
    # them would let the destination match instead of the source.
    r"^[^\S\n]*(?!#)\S*\bcp\b(?:\s+-{1,2}[A-Za-z-]+)*\s+"
    r"[\"']?\$(?:\{)?COMMON_TEMPLATE_ROOT(?:\})?/\.github/workflows/"
    r"([a-z0-9_\-]+\.ya?ml)",
    re.M,
)

# The `copy_shared_utils` function body, from its definition to the closing brace.
_RE_UTILS_FN = re.compile(r"^copy_shared_utils\(\)\s*\{(.*?)^\}", re.M | re.S)
# Its `for util in … ; do` header, searched INSIDE that body only — and rejected when
# commented out, exactly like the explicit form above. Both patterns need the guard: adding
# `(?!#)` to only one of them leaves the other able to satisfy the gate from a comment.
_RE_UTILS_LOOP = re.compile(r"^[^\S\n]*(?!#)\S*\s*for\s+util\s+in\s+(.*?);\s*do", re.M | re.S)
# The names may live in the loop header OR in a `local -a utils=( … )` array the loop iterates
# — the scaffolds declare the array so the step can print a COUNT instead of an enumeration
# that goes stale. Reading only the header would call every shared test undelivered the moment
# a scaffold switches form, which is a FALSE FAILURE in a gate whose value is its false-pass
# detection. Same no-comment anchoring as the rest.
_RE_UTILS_ARRAY = re.compile(
    r"^[^\S\n]*(?!#)\S*\s*local\s+-a\s+utils=\((.*?)\)", re.M | re.S
)
# A util name, so a shell token in the same position (`"${utils[@]}"`, a `\` continuation) is
# not mistaken for a module.
_RE_UTIL_NAME = re.compile(r"[a-z][a-z0-9_]*")
# Proof the loop body actually copies the test beside the module — likewise not from a comment.
_RE_UTILS_TEST_CP = re.compile(
    r"^[^\S\n]*(?!#)\S*\bcp\b[^\n]*tests/unit/test_\$\{util\}\.py", re.M
)


def shared_test_names() -> set:
    """Return every shared unit test filename.

    Returns
    -------
    set of str
        Filenames like ``test_dtypes.py`` under ``templates/python-common/tests/unit/``.
    """
    return {path_file.name for path_file in _SHARED_TESTS.glob("test_*.py")}


def shared_workflow_names() -> set:
    """Return every shared workflow filename.

    Returns
    -------
    set of str
        Filenames like ``tests.yaml`` under ``templates/python-common/.github/workflows/``.
    """
    return {path_file.name for path_file in _SHARED_WORKFLOWS.glob("*.y*ml")}


def reachable_tests(str_source: str) -> set:
    """Return the shared tests one scaffold script can deliver, by either mechanism.

    Parameters
    ----------
    str_source : str
        The scaffold script's text.

    Returns
    -------
    set of str
        Test filenames reachable via an explicit ``cp`` line or the shared-utils loop.
    """
    set_reachable = set(_RE_EXPLICIT_CP.findall(str_source))

    # The loop counts only when it is the real copy_shared_utils body AND that body demonstrably
    # copies test_${util}.py. A loop that merely iterates util names copies no test.
    cls_fn = _RE_UTILS_FN.search(str_source)
    if cls_fn:
        str_body = cls_fn.group(1)
        cls_loop = _RE_UTILS_LOOP.search(str_body)
        if cls_loop and _RE_UTILS_TEST_CP.search(str_body):
            str_names = cls_loop.group(1)
            cls_array = _RE_UTILS_ARRAY.search(str_body)
            if cls_array:
                str_names = f"{str_names} {cls_array.group(1)}"
            for str_util in str_names.split():
                if _RE_UTIL_NAME.fullmatch(str_util):
                    set_reachable.add(f"test_{str_util}.py")

    return set_reachable


def reachable_workflows(str_source: str) -> set:
    """Return the shared workflows one scaffold script copies.

    Parameters
    ----------
    str_source : str
        The scaffold script's text.

    Returns
    -------
    set of str
        Workflow filenames delivered by an active ``cp`` from the shared workflows directory.
    """
    return set(_RE_WORKFLOW_CP.findall(str_source))


def asset_problems(
    path_scaffold: pathlib.Path,
    set_shared: set,
    set_reachable: set,
    dict_allowed: dict,
    str_kind: str,
    str_source_dir: str,
    str_consequence: str,
) -> list:
    """Return the shared assets a scaffold neither copies nor deliberately excludes.

    One function for both copy lists: tests and workflows have identical failure shapes, so a
    second implementation would be a second place for the stale-exclusion check to rot.

    Parameters
    ----------
    path_scaffold : pathlib.Path
        A ``bin/scaffold/python_*.sh`` script.
    set_shared : set of str
        Every shared asset filename that exists on disk.
    set_reachable : set of str
        The assets this scaffold can actually deliver.
    dict_allowed : dict of {str: str}
        Deliberate exclusions for this scaffold, mapped to their reason.
    str_kind : str
        Human label for the asset class, e.g. ``"test"``.
    str_source_dir : str
        Repo-relative directory the assets come from, named in the stale-exclusion message.
    str_consequence : str
        What going missing actually costs, appended to the "never copies" message.

    Returns
    -------
    list of str
        One message per problem.
    """
    str_exclusions = "DICT_EXPECTED_ABSENT" if str_kind == "test" else "DICT_WORKFLOWS_EXPECTED_ABSENT"

    list_problems = []
    for str_asset in sorted(set_shared - set_reachable):
        if str_asset in dict_allowed:
            continue
        list_problems.append(
            f"❌ {path_scaffold.name}: never copies {str_asset} — {str_consequence}"
        )

    # A stale exclusion is its own defect: it silently keeps an asset out long after the reason
    # expired, and reads as intentional forever.
    for str_asset, str_reason in sorted(dict_allowed.items()):
        if str_asset in set_reachable:
            list_problems.append(
                f"❌ {path_scaffold.name}: {str_asset} IS copied, but {str_exclusions} still "
                f"claims it is not ({str_reason}) — remove the stale exclusion"
            )
        elif str_asset not in set_shared:
            list_problems.append(
                f"❌ {path_scaffold.name}: {str_exclusions} names {str_asset}, which no longer "
                f"exists in {str_source_dir} — remove it"
            )

    return list_problems


def scaffold_source_text(path_scaffold: pathlib.Path) -> str:
    """Return a scaffold's text joined with every ``bin/lib`` script it sources.

    A copy list is "reachable from this scaffold" whether the ``cp`` line sits in the
    scaffold itself or in a lib the scaffold sources — the generated project is identical
    either way. Reading only the scaffold was correct while every list was inline; the
    moment ``copy_common_templates`` moved into ``bin/lib/scaffold_python_templates.sh`` it would
    have made this gate report every shared test as missing from four tiers.

    ⚠️ The failure would have been loud, which is luck rather than design. The dangerous
    version of this is the mirror image: a gate that reads too NARROW a source and finds
    nothing to complain about. Keep the union honest whenever a copy list moves.

    Parameters
    ----------
    path_scaffold : pathlib.Path
        A ``bin/scaffold/python_*.sh`` script.

    Returns
    -------
    str
        The scaffold's own text, followed by the text of each lib it sources.
    """
    str_source = path_scaffold.read_text(encoding="utf-8")
    list_parts = [str_source]
    for str_lib in re.findall(r'source\s+"\$SCRIPT_DIR/\.\./lib/([A-Za-z0-9_]+\.sh)"', str_source):
        path_lib = _ROOT / "bin/lib" / str_lib
        if path_lib.is_file():
            list_parts.append(path_lib.read_text(encoding="utf-8"))
    return "\n".join(list_parts)


def scaffold_problems(path_scaffold: pathlib.Path, set_shared: set, set_workflows: set) -> list:
    """Return every copy-list problem for one scaffold, across both asset classes.

    Parameters
    ----------
    path_scaffold : pathlib.Path
        A ``bin/scaffold/python_*.sh`` script.
    set_shared : set of str
        Every shared test filename.
    set_workflows : set of str
        Every shared workflow filename.

    Returns
    -------
    list of str
        One message per problem, tests first.
    """
    str_source = scaffold_source_text(path_scaffold)

    return asset_problems(
        path_scaffold,
        set_shared,
        reachable_tests(str_source),
        DICT_EXPECTED_ABSENT.get(path_scaffold.name, {}),
        "test",
        "templates/python-common/tests/unit/",
        "it would be written, committed, and never run in any generated project",
    ) + asset_problems(
        path_scaffold,
        set_workflows,
        reachable_workflows(str_source),
        DICT_WORKFLOWS_EXPECTED_ABSENT.get(path_scaffold.name, {}),
        "workflow",
        "templates/python-common/.github/workflows/",
        "that CI gate would not exist at all in any generated project",
    )


def main() -> int:
    """Check every Python scaffold's test copy list against the shared source.

    Returns
    -------
    int
        0 when every shared test is reachable from every scaffold, 1 otherwise.
    """
    set_shared = shared_test_names()
    set_workflows = shared_workflow_names()

    # Scanning nothing yields no findings, which reads exactly like a clean pass.
    if not set_shared:
        print(f"❌ no shared tests found under {_SHARED_TESTS} — this gate would pass vacuously")
        return 1
    if not set_workflows:
        print(f"❌ no workflows found under {_SHARED_WORKFLOWS} — this gate would pass vacuously")
        return 1

    list_scaffolds = sorted(_SCAFFOLD_DIR.glob("python_*.sh"))
    if not list_scaffolds:
        print(f"❌ no python_*.sh scaffolds found under {_SCAFFOLD_DIR}")
        return 1

    list_problems = []
    for path_scaffold in list_scaffolds:
        list_problems.extend(scaffold_problems(path_scaffold, set_shared, set_workflows))

    for str_problem in list_problems:
        print(str_problem)

    if list_problems:
        print(
            f"\n{len(list_problems)} problem(s). A shared asset reaches a generated project only "
            f"through an active cp line (tests may also ride the copy_shared_utils loop). Add the "
            f"missing cp, or record a deliberate exclusion with a reason."
        )
        return 1

    print(
        f"copy lists OK: {len(set_shared)} shared test(s) + {len(set_workflows)} workflow(s) "
        f"reachable from all "
        f"{len(list_scaffolds)} Python scaffolds."
    )
    return 0


if __name__ == "__main__":
    # Windows' stdout defaults to cp1252, which cannot encode the status glyphs above.
    for cls_stream in (sys.stdout, sys.stderr):
        if hasattr(cls_stream, "reconfigure"):
            cls_stream.reconfigure(encoding="utf-8", errors="replace")

    sys.exit(main())
