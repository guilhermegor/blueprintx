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
_SHARED_ROOT = _ROOT / "templates/python-common"
_SHARED_TESTS = _SHARED_ROOT / "tests/unit"
_SHARED_WORKFLOWS = _SHARED_ROOT / ".github/workflows"
_SCAFFOLD_DIR = _ROOT / "bin/scaffold"

DICT_DOCS_EXPECTED_ABSENT = {
    "python_lib_minimal.sh": {
        "src/config/CLAUDE.md": "lib-minimal ships templates/lib-minimal/config_CLAUDE.md",
        "src/config/contracts/CLAUDE.md": "lib-minimal documents contracts in config_CLAUDE.md",
        "src/utils/CLAUDE.md": "lib-minimal ships templates/lib-minimal/utils_CLAUDE.md",
    },
}
_DOCS_NEVER_SHIPPED = {"CLAUDE.md"}

_EXCLUSION_TABLE_NAMES = {
    "test": "DICT_EXPECTED_ABSENT",
    "workflow": "DICT_WORKFLOWS_EXPECTED_ABSENT",
    "doc": "DICT_DOCS_EXPECTED_ABSENT",
}

DICT_WORKFLOWS_EXPECTED_ABSENT = {
    "python_lib_minimal.sh": {
        "release.yaml": "lib-minimal ships its own release-pypi workflows",
        "contract_drift.yaml": "lib-minimal ships no contract oracle registry",
    },
}

DICT_EXPECTED_ABSENT = {
    "python_lib_minimal.sh": {
        "test_env_config.py": "lib-minimal ships no src/config/env_config.py",
        "test_queries.py": "lib-minimal ships no DB engine selection or queries/ tree",
        "test_contract_oracle_example.py": "lib-minimal ships no contract oracle registry",
        "test_contract_drift.py": "lib-minimal ships no contract_drift driver or registry",
        "test_all_exports_gate.py": "lib-minimal ships no package declaring __all__",
        "test_contract_family_conventions.py": "lib-minimal ships no contract family",
        "test_startup_fragility_order.py": "lib-minimal ships no src/config/startup.py",
        "test_verify_venv_imports.py": "lib-minimal ships no bin/lib/pip_fallback.sh bootstrap",
        "test_typing.py": "lib-minimal RENDERS it from a template, not a cp",
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
        "test_ms_office_excel_sheet_names.py": "lib-minimal does not ship ms_office/",
        "test_email_dispatch.py": "lib-minimal does not ship email/",
        "test_email_sender.py": "lib-minimal does not ship email/",
        "test_email_html_body.py": "lib-minimal does not ship email/",
        "test_config_schemas_example.py": "schemas/ pydantic dep not yet wired (#267)",
        "test_dead_code_gate.py": "check_dead_code.py gate not yet wired (#332 follow-up)",
        "test_migration_graph_gate.py": "cp line not yet wired into any scaffold (#308 follow-up)",
        "test_docs_gap_gate.py": "cp line not yet wired into any scaffold (#340 follow-up)",
    },
    "python_ddd_service.sh": {
        "test_config_schemas_example.py": "schemas/ pydantic dep not yet wired (#267)",
        "test_dead_code_gate.py": "check_dead_code.py gate not yet wired (#332 follow-up)",
        "test_migration_graph_gate.py": "cp line not yet wired into any scaffold (#308 follow-up)",
        "test_docs_gap_gate.py": "cp line not yet wired into any scaffold (#340 follow-up)",
    },
    "python_api_service.sh": {
        "test_config_schemas_example.py": "schemas/ seam not yet wired (#267); no src/config/schemas/ module",
        "test_dead_code_gate.py": "check_dead_code.py gate not yet wired (#332 follow-up)",
        "test_docs_gap_gate.py": "cp line not yet wired into any scaffold (#340 follow-up)",
    },
    "python_ddd_service_orm.sh": {
        "test_config_schemas_example.py": "schemas/ pydantic dep not yet wired (#267)",
        "test_dead_code_gate.py": "check_dead_code.py gate not yet wired (#332 follow-up)",
        "test_migration_graph_gate.py": "cp line not yet wired into any scaffold (#308 follow-up)",
        "test_docs_gap_gate.py": "cp line not yet wired into any scaffold (#340 follow-up)",
    },
    "python_mvc_service.sh": {
        "test_config_schemas_example.py": "schemas/ pydantic dep not yet wired (#267)",
        "test_dead_code_gate.py": "check_dead_code.py gate not yet wired (#332 follow-up)",
        "test_migration_graph_gate.py": "cp line not yet wired into any scaffold (#308 follow-up)",
        "test_docs_gap_gate.py": "cp line not yet wired into any scaffold (#340 follow-up)",
    },
    "python_mvc_service_orm.sh": {
        "test_config_schemas_example.py": "schemas/ pydantic dep not yet wired (#267)",
        "test_dead_code_gate.py": "check_dead_code.py gate not yet wired (#332 follow-up)",
        "test_migration_graph_gate.py": "cp line not yet wired into any scaffold (#308 follow-up)",
        "test_docs_gap_gate.py": "cp line not yet wired into any scaffold (#340 follow-up)",
    },
}

_RE_EXPLICIT_CP = re.compile(
    r"^[^\S\n]*(?!#)\S*\bcp\b[^\n]*?COMMON_TEMPLATE_ROOT/tests/unit/(test_[a-z0-9_]+\.py)",
    re.M,
)

_RE_WORKFLOW_CP = re.compile(
    r"^[^\S\n]*(?!#)\S*\bcp\b(?:\s+-{1,2}[A-Za-z-]+)*\s+"
    r"[\"']?\$(?:\{)?COMMON_TEMPLATE_ROOT(?:\})?/\.github/workflows/"
    r"([a-z0-9_\-]+\.ya?ml)",
    re.M,
)

_RE_SHARED_SOURCE_CP = re.compile(
    r"^[^\S\n]*(?!#)\S*\bcp\b(?:\s+-{1,2}[A-Za-z-]+)*\s+"
    r"[\"']?\$(?:\{)?COMMON_TEMPLATE_ROOT(?:\})?/([A-Za-z0-9_./-]+)[\"']?"
    r"(?:\s|\\\n)+[\"']?([^\s\"']+)",
    re.M,
)

_RE_UTILS_FN = re.compile(r"^copy_shared_utils\(\)\s*\{(.*?)^\}", re.M | re.S)
_RE_UTILS_LOOP = re.compile(r"^[^\S\n]*(?!#)\S*\s*for\s+util\s+in\s+(.*?);\s*do", re.M | re.S)
_RE_UTILS_ARRAY = re.compile(
    r"^[^\S\n]*(?!#)\S*\s*local\s+-a\s+utils=\((.*?)\)", re.M | re.S
)
_RE_UTIL_NAME = re.compile(r"[a-z][a-z0-9_]*")
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


def shared_doc_names() -> set:
    """Return every shippable leaf doc, as a path relative to python-common.

    Returns
    -------
    set of str
        Paths like ``src/config/contracts/CLAUDE.md``; the family root doc is excluded.
    """
    return {
        path_file.relative_to(_SHARED_ROOT).as_posix()
        for path_file in _SHARED_ROOT.rglob("CLAUDE.md")
    } - _DOCS_NEVER_SHIPPED


def dest_stays_in_project(str_operand: str, str_dest: str) -> bool:
    """Return whether a ``cp`` destination lands inside the project under the source's name.

    Parameters
    ----------
    str_operand : str
        The source operand relative to python-common, e.g. ``src/config/CLAUDE.md`` or ``bin/.``.
    str_dest : str
        The raw destination operand, e.g. ``$project_path/src/config/CLAUDE.md``.

    Returns
    -------
    bool
        True when the destination is rooted at a shell variable, has no ``..`` segment, and ends
        with the source's last segment (a file also needs its parent directory to match).
    """
    list_src = [str_seg for str_seg in str_operand.split("/") if str_seg not in ("", ".")]
    list_dst = [str_seg for str_seg in str_dest.split("/") if str_seg not in ("", ".")]
    int_tail = 2 if not str_operand.endswith("/.") else 1
    return (
        str_dest.startswith("$")
        and ".." not in list_dst
        and list_dst[-int_tail:] == list_src[-int_tail:]
    )


def reachable_docs(str_source: str, set_shared: set) -> set:
    """Return the shared leaf docs one scaffold script copies, by file or by directory.

    Parameters
    ----------
    str_source : str
        The scaffold script's text.
    set_shared : set of str
        Every shippable doc path, so a directory copy can be expanded to the docs under it.

    Returns
    -------
    set of str
        Doc paths delivered by an active ``cp`` from python-common, directly or wholesale.
    """
    set_reachable = set()
    for str_operand, str_dest in _RE_SHARED_SOURCE_CP.findall(str_source):
        if not dest_stays_in_project(str_operand, str_dest):
            continue
        if str_operand in set_shared:
            set_reachable.add(str_operand)
        elif str_operand.endswith("/."):
            str_prefix = str_operand[:-1]
            set_reachable.update(str_doc for str_doc in set_shared if str_doc.startswith(str_prefix))
    return set_reachable


def _reachable_util_names(str_names: str, cls_array: re.Match | None) -> set:
    """Return the valid utility names reachable from a copy_shared_utils loop body.

    Parameters
    ----------
    str_names : str
        Whitespace-separated names captured from the loop's own match.
    cls_array : re.Match or None
        Optional array-literal match whose group(1) contributes more names.

    Returns
    -------
    set of str
        Names matching ``_RE_UTIL_NAME`` — each yields a ``test_<name>.py``.
    """
    if cls_array:
        str_names = f"{str_names} {cls_array.group(1)}"
    return {str_util for str_util in str_names.split() if _RE_UTIL_NAME.fullmatch(str_util)}


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

    cls_fn = _RE_UTILS_FN.search(str_source)
    if cls_fn:
        str_body = cls_fn.group(1)
        cls_loop = _RE_UTILS_LOOP.search(str_body)
        if cls_loop and _RE_UTILS_TEST_CP.search(str_body):
            cls_array = _RE_UTILS_ARRAY.search(str_body)
            for str_util in _reachable_util_names(cls_loop.group(1), cls_array):
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
    str_exclusions = _EXCLUSION_TABLE_NAMES[str_kind]

    list_problems = []
    for str_asset in sorted(set_shared - set_reachable):
        if str_asset in dict_allowed:
            continue
        list_problems.append(
            f"❌ {path_scaffold.name}: never copies {str_asset} — {str_consequence}"
        )

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


def scaffold_problems(
    path_scaffold: pathlib.Path, set_shared: set, set_workflows: set, set_docs: set
) -> list:
    """Return every copy-list problem for one scaffold, across all three asset classes.

    Parameters
    ----------
    path_scaffold : pathlib.Path
        A ``bin/scaffold/python_*.sh`` script.
    set_shared : set of str
        Every shared test filename.
    set_workflows : set of str
        Every shared workflow filename.
    set_docs : set of str
        Every shippable leaf doc path.

    Returns
    -------
    list of str
        One message per problem — tests, then workflows, then docs.
    """
    str_source = scaffold_source_text(path_scaffold)

    return asset_problems(
        path_scaffold,
        set_docs,
        reachable_docs(str_source, set_docs),
        DICT_DOCS_EXPECTED_ABSENT.get(path_scaffold.name, {}),
        "doc",
        "templates/python-common/",
        "the doc would be written, committed, and never read in any generated project",
    ) + asset_problems(
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
    set_docs = shared_doc_names()

    if not set_shared:
        print(f"❌ no shared tests found under {_SHARED_TESTS} — this gate would pass vacuously")
        return 1
    if not set_workflows:
        print(f"❌ no workflows found under {_SHARED_WORKFLOWS} — this gate would pass vacuously")
        return 1
    if not set_docs:
        print(f"❌ no leaf CLAUDE.md found under {_SHARED_ROOT} — this gate would pass vacuously")
        return 1

    list_scaffolds = sorted(_SCAFFOLD_DIR.glob("python_*.sh"))
    if not list_scaffolds:
        print(f"❌ no python_*.sh scaffolds found under {_SCAFFOLD_DIR}")
        return 1

    list_problems = []
    for path_scaffold in list_scaffolds:
        list_problems.extend(
            scaffold_problems(path_scaffold, set_shared, set_workflows, set_docs)
        )

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
        f"+ {len(set_docs)} leaf doc(s) reachable from all "
        f"{len(list_scaffolds)} Python scaffolds."
    )
    return 0


if __name__ == "__main__":
    for cls_stream in (sys.stdout, sys.stderr):
        if hasattr(cls_stream, "reconfigure"):
            cls_stream.reconfigure(encoding="utf-8", errors="replace")

    sys.exit(main())
