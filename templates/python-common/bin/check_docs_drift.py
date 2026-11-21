#!/usr/bin/env python3
"""Fail when the docs cite something the code no longer has (blueprintx#1233).

Two blocking checks, both decidable offline:

- every ``poe <task>`` cited inside a code fence or inline code span of ``README*.md``,
  ``CONTRIBUTING*.md`` or ``docs/**/*.md`` is defined in ``poe_tasks*.toml``;
- every non-dunder name in a ``src/<package>/__init__.py`` ``__all__`` appears as a
  word-bounded mention in ``docs/api/reference.md``.

One advisory check, reported and never failing the run: ``.docs-coupling.yaml`` maps a
source glob to the docs that describe it, and a changed source without its doc touched is
listed. A ``Docs: not needed because <reason>`` line in any commit of the range, or a bot
author, silences it.

Usage::

    python bin/check_docs_drift.py                       # blocking checks, this project
    python bin/check_docs_drift.py --root DIR            # one project root
    python bin/check_docs_drift.py --coupling --base REF # advisory coupling report
"""

import ast
import fnmatch
import pathlib
import re
import subprocess
import sys
import tomllib

import yaml


STR_REFERENCE = "docs/api/reference.md"
STR_COUPLING = ".docs-coupling.yaml"
STR_ROOT_FLAG = "--root"
STR_DEFAULT_ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
STR_BASE_FLAG = "--base"
STR_COUPLING_FLAG = "--coupling"
SET_SKIP_DIRS = {".git", ".venv", "node_modules", "site", "htmlcov"}

RE_FENCE = re.compile(r"^\s*(```|~~~)")
RE_SPAN = re.compile(r"`([^`\n]+)`")
RE_POE = re.compile(r"\bpoe\s+([A-Za-z_][A-Za-z0-9_-]*)")
RE_ESCAPE = re.compile(r"^Docs:\s*not needed because\s+\S", re.IGNORECASE | re.MULTILINE)


def doc_files(path_root: pathlib.Path) -> list:
    """Return the Markdown files whose commands and symbols are checked.

    Parameters
    ----------
    path_root : pathlib.Path
        The project root.

    Returns
    -------
    list of pathlib.Path
        Root ``README*.md`` and ``CONTRIBUTING*.md`` plus every page under ``docs/``.
    """
    list_files = sorted(path_root.glob("README*.md")) + sorted(path_root.glob("CONTRIBUTING*.md"))
    list_files += sorted(path_root.glob("docs/**/*.md"))
    return [
        path_file
        for path_file in list_files
        if not SET_SKIP_DIRS & set(path_file.relative_to(path_root).parts)
    ]


def code_segments(str_text: str) -> list:
    """Return the code-only text of a Markdown page: fenced lines and inline spans.

    Parameters
    ----------
    str_text : str
        The page content.

    Returns
    -------
    list of str
        One entry per fenced line or inline code span; prose is never included.
    """
    list_segments = []
    bool_fenced = False
    for str_line in str_text.splitlines():
        if RE_FENCE.match(str_line):
            bool_fenced = not bool_fenced
        elif bool_fenced:
            list_segments.append(str_line)
        else:
            list_segments += RE_SPAN.findall(str_line)
    return list_segments


def cited_tasks(str_text: str) -> set:
    """Return the poe task names a page cites in code.

    Parameters
    ----------
    str_text : str
        The page content.

    Returns
    -------
    set of str
        Every name following ``poe`` inside a fence or an inline span.
    """
    return {
        str_name for str_seg in code_segments(str_text) for str_name in RE_POE.findall(str_seg)
    }


def defined_tasks(path_root: pathlib.Path) -> set:
    """Return the task names every ``poe_tasks*.toml`` fragment defines.

    Parameters
    ----------
    path_root : pathlib.Path
        The project root.

    Returns
    -------
    set of str
        Task names across ``poe_tasks.toml`` and its fragments.
    """
    set_names = set()
    for path_toml in sorted(path_root.glob("poe_tasks*.toml")):
        dict_doc = tomllib.loads(path_toml.read_text(encoding="utf-8"))
        set_names |= set(dict_doc.get("tool", {}).get("poe", {}).get("tasks", {}))
    return set_names


def poe_problems(path_root: pathlib.Path, *, list_docs: list) -> list:
    """Return one finding per cited poe task the project does not define.

    Parameters
    ----------
    path_root : pathlib.Path
        The project root.
    list_docs : list of pathlib.Path
        The pages to read.

    Returns
    -------
    list of str
        ``<page>: poe <task> is not defined`` per drifted citation.
    """
    set_defined = defined_tasks(path_root)
    list_problems = []
    for path_doc in list_docs:
        set_cited = cited_tasks(path_doc.read_text(encoding="utf-8"))
        list_problems += [
            f"{path_doc.relative_to(path_root)}: poe {str_name} is not defined in poe_tasks*.toml"
            for str_name in sorted(set_cited - set_defined)
        ]
    return list_problems


def declared_all(path_init: pathlib.Path) -> list:
    """Return the string entries of a module-level ``__all__`` list or tuple.

    Parameters
    ----------
    path_init : pathlib.Path
        An ``__init__.py`` file.

    Returns
    -------
    list of str
        The entries, empty when the module declares no ``__all__``.
    """
    for cls_node in ast.parse(path_init.read_text(encoding="utf-8")).body:
        if not isinstance(cls_node, ast.Assign) or not isinstance(
            cls_node.value, ast.List | ast.Tuple
        ):
            continue
        if any(
            isinstance(cls_t, ast.Name) and cls_t.id == "__all__" for cls_t in cls_node.targets
        ):
            return [
                cls_elt.value
                for cls_elt in cls_node.value.elts
                if isinstance(cls_elt, ast.Constant) and isinstance(cls_elt.value, str)
            ]
    return []


def exported_names(path_root: pathlib.Path) -> list:
    """Return the public names every top-level package exports through ``__all__``.

    Parameters
    ----------
    path_root : pathlib.Path
        The project root.

    Returns
    -------
    list of str
        Non-dunder names from each ``src/<package>/__init__.py``.
    """
    return [
        str_name
        for path_init in sorted(path_root.glob("src/*/__init__.py"))
        for str_name in declared_all(path_init)
        if not str_name.startswith("__")
    ]


def all_problems(path_root: pathlib.Path) -> list:
    """Return one finding per exported name the API reference never mentions.

    Parameters
    ----------
    path_root : pathlib.Path
        The project root.

    Returns
    -------
    list of str
        One message per undocumented name, or one when the reference page is missing.
    """
    list_names = exported_names(path_root)
    if not list_names:
        return []
    path_ref = path_root / STR_REFERENCE
    if not path_ref.is_file():
        return [f"{STR_REFERENCE} does not exist but a package declares __all__"]
    str_ref = path_ref.read_text(encoding="utf-8")
    return [
        f"{STR_REFERENCE}: {str_name} is in __all__ but is never mentioned"
        for str_name in list_names
        if not re.search(rf"\b{re.escape(str_name)}\b", str_ref)
    ]


def git_lines(path_root: pathlib.Path, *, list_args: list) -> list:
    """Run a read-only git query and return its output lines.

    Parameters
    ----------
    path_root : pathlib.Path
        The repository root.
    list_args : list of str
        Arguments after ``git``.

    Returns
    -------
    list of str
        Output lines, empty when git fails.
    """
    cls_run = subprocess.run(  # noqa: S603 -- constant argv, no shell
        ["git", "-C", str(path_root), *list_args],  # noqa: S607 -- git on PATH
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return cls_run.stdout.splitlines() if cls_run.returncode == 0 else []


def coupling_problems(path_root: pathlib.Path, *, str_base: str) -> list:
    """Return the coupling-map entries whose source changed without its doc.

    Parameters
    ----------
    path_root : pathlib.Path
        The project root.
    str_base : str
        The ref the branch is compared against.

    Returns
    -------
    list of str
        One message per source glob changed while none of its docs was.
    """
    path_map = path_root / STR_COUPLING
    if not path_map.is_file():
        return []
    str_range = f"{str_base}...HEAD"
    list_changed = git_lines(path_root, list_args=["diff", "--name-only", str_range])
    str_log = "\n".join(
        git_lines(path_root, list_args=["log", "--format=%an%n%B", f"{str_base}..HEAD"])
    )
    if RE_ESCAPE.search(str_log) or "[bot]" in str_log:
        return []
    list_problems = []
    for dict_entry in yaml.safe_load(path_map.read_text(encoding="utf-8")).get("couplings", []):
        list_hit = [
            str_path
            for str_path in list_changed
            if fnmatch.fnmatch(str_path, dict_entry["source"])
        ]
        if list_hit and not set(dict_entry["docs"]) & set(list_changed):
            list_problems.append(
                f"{list_hit[0]} changed but none of {', '.join(dict_entry['docs'])} did"
            )
    return list_problems


def option(list_argv: list, *, str_flag: str, str_default: str) -> str:
    """Return the value following a flag, or a default.

    Parameters
    ----------
    list_argv : list of str
        Arguments after the program name.
    str_flag : str
        The flag to look up.
    str_default : str
        The value when the flag is absent.

    Returns
    -------
    str
        The token after ``str_flag``, else ``str_default``.
    """
    return list_argv[list_argv.index(str_flag) + 1] if str_flag in list_argv else str_default


def main(list_argv: list) -> int:
    """Run the blocking checks, then the advisory coupling report when asked.

    Parameters
    ----------
    list_argv : list of str
        Arguments after the program name.

    Returns
    -------
    int
        0 when the blocking checks pass, 1 on a finding or when no page was found.
    """
    path_root = pathlib.Path(
        option(list_argv, str_flag=STR_ROOT_FLAG, str_default=STR_DEFAULT_ROOT)
    )
    list_docs = doc_files(path_root)
    if not list_docs:
        print(f"{path_root}: no README, CONTRIBUTING or docs/ page found; nothing was checked")
        return 1
    list_problems = poe_problems(path_root, list_docs=list_docs) + all_problems(path_root)
    if STR_COUPLING_FLAG in list_argv:
        for str_advice in coupling_problems(
            path_root,
            str_base=option(list_argv, str_flag=STR_BASE_FLAG, str_default="origin/main"),
        ):
            print(f"advisory: {str_advice}")
    for str_problem in list_problems:
        print(str_problem)
    if list_problems:
        print(f"{len(list_problems)} finding(s): the docs cite something the code lacks.")
        return 1
    int_tasks = len(defined_tasks(path_root))
    print(f"docs drift OK ({len(list_docs)} page(s), {int_tasks} poe task(s) checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
