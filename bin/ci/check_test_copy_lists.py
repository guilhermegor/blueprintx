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

🔴 **The only tell is the test COUNT, never the colour.** A scaffold verification that goes from
234 to 234 after adding 18 tests looks exactly like a scaffold verification that went from 234
to 252. Nobody reads the number; everybody reads the colour. Hence a gate.

Deliberate exclusions live in ``DICT_EXPECTED_ABSENT`` with a reason each — a tier that
genuinely should not receive a test (``lib-minimal`` has no service config, so the env-config
and contract-oracle tests do not apply there).
"""

import pathlib
import re
import sys


_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SHARED_TESTS = _ROOT / "templates/python-common/tests/unit"
_SCAFFOLD_DIR = _ROOT / "bin/scaffold"

# Tests a given scaffold deliberately does NOT copy, with the reason. An entry here is a claim
# that the tier cannot use the test, not a shortcut for "I forgot to wire it".
DICT_EXPECTED_ABSENT = {
    "python_lib_minimal.sh": {
        # A distributable library has no runtime .env to read, so the service tiers'
        # env-config seam (and its test) is not shipped.
        "test_env_config.py": "lib-minimal ships no src/config/env_config.py",
        # Contract oracles describe an ingested external file; a library tier ships none.
        "test_contract_oracle_example.py": "lib-minimal ships no contract oracle registry",
        # startup.py is a service-tier singleton; a library has no import-time bootstrap.
        "test_startup_fragility_order.py": "lib-minimal ships no src/config/startup.py",
        # NOT missing — DELIVERED BY A THIRD MECHANISM this gate does not model: the scaffold
        # GENERATES it from a heredoc (python_lib_minimal.sh), because the file needs the
        # package name substituted in and covers a smaller matrix than the service tiers'.
        # Verified present and running in a real lib-minimal scaffold. Modelling heredoc
        # generation would mean a third parser for one case; the stale-exclusion check below
        # will flag this entry the day it becomes an ordinary `cp`.
        "test_typing.py": "lib-minimal GENERATES it from a heredoc, not a cp",
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
        "test_outlook_gateway.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_paths.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_provenance.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_retry.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_sidecar_metadata.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_signatures.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_tabular_reader.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_text.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
        "test_zip_extractor.py": "lib-minimal vendors utils under _internal/ (import rewrite)",
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

# The `copy_shared_utils` function body, from its definition to the closing brace.
_RE_UTILS_FN = re.compile(r"^copy_shared_utils\(\)\s*\{(.*?)^\}", re.M | re.S)
# Its `for util in … ; do` header, searched INSIDE that body only.
_RE_UTILS_LOOP = re.compile(r"for\s+util\s+in\s+(.*?);\s*do", re.S)
# Proof the loop body actually copies the test beside the module.
_RE_UTILS_TEST_CP = re.compile(r"\bcp\b[^\n]*tests/unit/test_\$\{util\}\.py")


def shared_test_names() -> set:
    """Return every shared unit test filename.

    Returns
    -------
    set of str
        Filenames like ``test_dtypes.py`` under ``templates/python-common/tests/unit/``.
    """
    return {path.name for path in _SHARED_TESTS.glob("test_*.py")}


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
            for str_util in cls_loop.group(1).split():
                if str_util != "\\":
                    set_reachable.add(f"test_{str_util}.py")

    return set_reachable


def scaffold_problems(path_scaffold: pathlib.Path, set_shared: set) -> list:
    """Return the shared tests a scaffold neither copies nor deliberately excludes.

    Parameters
    ----------
    path_scaffold : pathlib.Path
        A ``bin/scaffold/python_*.sh`` script.
    set_shared : set of str
        Every shared test filename.

    Returns
    -------
    list of str
        One message per unreachable test.
    """
    str_source = path_scaffold.read_text(encoding="utf-8")
    set_reachable = reachable_tests(str_source)
    dict_allowed = DICT_EXPECTED_ABSENT.get(path_scaffold.name, {})

    list_problems = []
    for str_test in sorted(set_shared - set_reachable):
        if str_test in dict_allowed:
            continue
        list_problems.append(
            f"❌ {path_scaffold.name}: never copies {str_test} — it would be written, "
            f"committed, and never run in any generated project"
        )

    # A stale exclusion is its own defect: it silently keeps a test out long after the reason
    # expired, and reads as intentional forever.
    for str_test, str_reason in sorted(dict_allowed.items()):
        if str_test in set_reachable:
            list_problems.append(
                f"❌ {path_scaffold.name}: {str_test} IS copied, but DICT_EXPECTED_ABSENT still "
                f"claims it is not ({str_reason}) — remove the stale exclusion"
            )
        elif str_test not in set_shared:
            list_problems.append(
                f"❌ {path_scaffold.name}: DICT_EXPECTED_ABSENT names {str_test}, which no "
                f"longer exists in templates/python-common/tests/unit/ — remove it"
            )

    return list_problems


def main() -> int:
    """Check every Python scaffold's test copy list against the shared source.

    Returns
    -------
    int
        0 when every shared test is reachable from every scaffold, 1 otherwise.
    """
    set_shared = shared_test_names()

    # Scanning nothing yields no findings, which reads exactly like a clean pass.
    if not set_shared:
        print(f"❌ no shared tests found under {_SHARED_TESTS} — this gate would pass vacuously")
        return 1

    list_scaffolds = sorted(_SCAFFOLD_DIR.glob("python_*.sh"))
    if not list_scaffolds:
        print(f"❌ no python_*.sh scaffolds found under {_SCAFFOLD_DIR}")
        return 1

    list_problems = []
    for path_scaffold in list_scaffolds:
        list_problems.extend(scaffold_problems(path_scaffold, set_shared))

    for str_problem in list_problems:
        print(str_problem)

    if list_problems:
        print(
            f"\n{len(list_problems)} problem(s). A shared test reaches a generated project "
            f"either through an explicit cp line or through the copy_shared_utils loop. Add the "
            f"missing cp line, or record a deliberate exclusion in DICT_EXPECTED_ABSENT with a "
            f"reason."
        )
        return 1

    print(
        f"test copy lists OK: {len(set_shared)} shared test(s) reachable from all "
        f"{len(list_scaffolds)} Python scaffolds."
    )
    return 0


if __name__ == "__main__":
    # Windows' stdout defaults to cp1252, which cannot encode the status glyphs above.
    for cls_stream in (sys.stdout, sys.stderr):
        if hasattr(cls_stream, "reconfigure"):
            cls_stream.reconfigure(encoding="utf-8", errors="replace")

    sys.exit(main())
