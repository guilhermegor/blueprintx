"""Fail when a tag-versioned project's ``pyproject.toml`` version is not the ``0.0.0`` stub.

A project that sets ``[tool.poetry-dynamic-versioning] enable = true`` takes its published
version from the git tag, so ``[tool.poetry] version`` is only a placeholder. A hand-bump of
that placeholder contradicts the tag and the package index (opendata-rfb#30: stub bumped to
``1.0.0`` while ``v1.0.1`` and ``v1.0.2`` shipped from tags).

Conditional by construction: a project without dynamic versioning enabled (the service tiers,
whose ``cz bump`` / ``release.yml`` write a real static version, and offline-mode libraries)
is a no-op and exits 0.

Usage: ``python bin/check_dynamic_version_stub.py [--root DIR]``
"""

import argparse
import pathlib
import sys
import tomllib


STR_STUB = "0.0.0"
STR_DYNAMIC_SECTION = "tool.poetry-dynamic-versioning"
STR_POETRY_SECTION = "tool.poetry"


def find_problem(dict_doc: dict) -> str:
    """Return the gate's finding for one parsed ``pyproject.toml``, or ``""`` when clean.

    Parameters
    ----------
    dict_doc : dict
        The parsed ``pyproject.toml`` (``tomllib`` output).

    Returns
    -------
    str
        A finding message, empty when the project is a no-op or carries the stub.
    """
    dict_tool = dict_doc.get("tool", {})
    dict_dynamic = dict_tool.get("poetry-dynamic-versioning", {})
    if dict_dynamic.get("enable") is not True:
        return ""
    str_found = dict_tool.get("poetry", {}).get("version", "<missing>")
    if str_found == STR_STUB:
        return ""
    return (
        f"[{STR_POETRY_SECTION}] version is {str_found!r} but "
        f"[{STR_DYNAMIC_SECTION}] is enabled: the version comes from the git tag, so it must "
        f"stay {STR_STUB!r}. Revert the hand-bump; see docs/contributing.md#releasing."
    )


def main(list_argv: list) -> int:
    """Run the gate against ``<root>/pyproject.toml``.

    Parameters
    ----------
    list_argv : list of str
        Arguments after the program name; only ``--root DIR`` is accepted.

    Returns
    -------
    int
        0 when clean or not applicable, 1 on a finding (argparse exits 2 on bad usage).
    """
    cls_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cls_parser.add_argument("--root", default=".", help="project root holding pyproject.toml")
    path_root = pathlib.Path(cls_parser.parse_args(list_argv).root)
    path_pyproject = path_root / "pyproject.toml"
    if not path_pyproject.is_file():
        print(f"{path_pyproject} not found; nothing to check")
        return 0
    try:
        with path_pyproject.open("rb") as cls_file:
            dict_doc = tomllib.load(cls_file)
    except tomllib.TOMLDecodeError as cls_exc:
        print(f"{path_pyproject}: invalid TOML ({cls_exc})")
        return 1
    str_problem = find_problem(dict_doc)
    if str_problem:
        print(f"{path_pyproject}: {str_problem}")
        return 1
    print("dynamic version stub OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
