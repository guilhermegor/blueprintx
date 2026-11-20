"""Flag lib-minimal template residue that would ship in the next wheel.

The placeholder guard fails when a ``src/<pkg>/main.py`` still holds the template's greeting
literal, even reformatted. The reachability report walks imports from the public modules
(the walk of ``check_unreachable_modules.py``, with its allowlist) and lists the vendored
``_internal.utils`` modules left outside, plus the third-party imports only those modules
make. The report fails only under ``--strict``.
"""

import argparse
import ast
import pathlib
import re
import sys
import tomllib

import check_unreachable_modules as unreachable


STR_PLACEHOLDER = "Hello from lib-minimal!"
STR_UTILS_SEGMENT = "._internal.utils."
STR_ENTRY_SUFFIX = ".main"
RE_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
RE_NAME_SEPARATORS = re.compile(r"[-_.]+")


def is_placeholder(path_file: pathlib.Path) -> bool:
    """Say whether a module still holds the template's greeting literal.

    Parameters
    ----------
    path_file : pathlib.Path
        The module to read.

    Returns
    -------
    bool
        True when any string constant in the module equals ``STR_PLACEHOLDER``.
    """
    cls_tree = ast.parse(path_file.read_bytes(), filename=str(path_file))
    return any(
        isinstance(cls_node, ast.Constant) and cls_node.value == STR_PLACEHOLDER
        for cls_node in ast.walk(cls_tree)
    )


def placeholder_modules(dict_modules: dict[str, pathlib.Path]) -> list[str]:
    """Return the top-level ``<pkg>.main`` modules that are still the placeholder.

    Parameters
    ----------
    dict_modules : dict of str to pathlib.Path
        Every module under ``src/``.

    Returns
    -------
    list of str
        Dotted names, sorted.
    """
    return sorted(
        str_module
        for str_module, path_file in dict_modules.items()
        if str_module.count(".") == 1
        and str_module.endswith(STR_ENTRY_SUFFIX)
        and is_placeholder(path_file)
    )


def is_vendored_util(str_module: str) -> bool:
    """Say whether a module lives under a package's ``_internal.utils``.

    Parameters
    ----------
    str_module : str
        Dotted module name.

    Returns
    -------
    bool
        True for ``<pkg>._internal.utils`` and everything below it.
    """
    return STR_UTILS_SEGMENT in f"{str_module}."


def third_party_imports(path_file: pathlib.Path, *, set_first_party: set[str]) -> set[str]:
    """Collect the top-level names of a module's absolute non-stdlib imports.

    Parameters
    ----------
    path_file : pathlib.Path
        The module to read.
    set_first_party : set of str
        Top-level package names under ``src/``.

    Returns
    -------
    set of str
        Top-level import names that are neither stdlib nor first-party.
    """
    cls_tree = ast.parse(path_file.read_bytes(), filename=str(path_file))
    set_names = set()
    for cls_node in ast.walk(cls_tree):
        if isinstance(cls_node, ast.Import):
            set_names.update(cls_alias.name for cls_alias in cls_node.names)
        if isinstance(cls_node, ast.ImportFrom) and cls_node.level == 0 and cls_node.module:
            set_names.add(cls_node.module)
    set_top = {str_name.partition(".")[0] for str_name in set_names}
    return set_top - set(sys.stdlib_module_names) - set_first_party


def normalized(str_name: str) -> str:
    """Normalise a distribution or import name for comparison.

    Parameters
    ----------
    str_name : str
        A distribution or import name.

    Returns
    -------
    str
        Lowercase, with every run of ``-``, ``_`` and ``.`` folded to ``_``.
    """
    return RE_NAME_SEPARATORS.sub("_", str_name).lower()


def declared_dependencies(path_pyproject: pathlib.Path) -> dict[str, str]:
    """Read the runtime dependencies a ``pyproject.toml`` declares.

    Parameters
    ----------
    path_pyproject : pathlib.Path
        The manifest; a missing file declares nothing.

    Returns
    -------
    dict of str to str
        Normalised name to declared name, from ``[tool.poetry.dependencies]`` (bar
        ``python``) and ``[project].dependencies``.
    """
    if not path_pyproject.is_file():
        return {}
    dict_toml = tomllib.loads(path_pyproject.read_text(encoding="utf-8"))
    list_names = [
        str_name
        for str_name in dict_toml.get("tool", {}).get("poetry", {}).get("dependencies", {})
        if str_name != "python"
    ]
    for str_requirement in dict_toml.get("project", {}).get("dependencies", []):
        cls_match = RE_REQUIREMENT_NAME.match(str_requirement)
        if cls_match:
            list_names.append(cls_match.group(1))
    return {normalized(str_name): str_name for str_name in list_names}


def residue_dependencies(
    dict_modules: dict[str, pathlib.Path],
    *,
    list_residue: list[str],
    list_open: list[str],
    path_root: pathlib.Path,
) -> list[str]:
    """Name the third-party imports that only the residue modules make.

    An import counts as live only when a reachable module makes it, so a dependency the
    residue shares with another unreachable module is still reported.

    Parameters
    ----------
    dict_modules : dict of str to pathlib.Path
        Every module under ``src/`` that counts as shipped code.
    list_residue : list of str
        The unreachable vendored utils.
    list_open : list of str
        Every module still unreachable once the allowlisted ones count as roots.
    path_root : pathlib.Path
        Project root holding ``pyproject.toml``.

    Returns
    -------
    list of str
        One entry per import, labelled with its declared dependency when one matches.
    """
    set_first_party = {str_module.partition(".")[0] for str_module in dict_modules}
    dict_imports = {
        str_module: third_party_imports(path_file, set_first_party=set_first_party)
        for str_module, path_file in dict_modules.items()
    }
    set_open = set(list_open)
    set_live = set().union(
        *(
            set_names
            for str_module, set_names in dict_imports.items()
            if str_module not in set_open
        )
    )
    set_only = set().union(*(dict_imports[str_module] for str_module in list_residue)) - set_live
    dict_declared = declared_dependencies(path_root / "pyproject.toml")
    return sorted(
        dict_declared.get(
            normalized(str_name), f"{str_name} (import name; distribution name unknown)"
        )
        for str_name in set_only
    )


def allowlist_problems(path_root: pathlib.Path, *, list_dead: list[str]) -> list[str]:
    """Report allowlist entries without a reason and entries that match no unreachable module.

    Parameters
    ----------
    path_root : pathlib.Path
        Project root holding the allowlist.
    list_dead : list of str
        The modules the public roots miss.

    Returns
    -------
    list of str
        One message per problem.
    """
    list_patterns, list_problems = unreachable.load_allowlist(
        path_root / unreachable.STR_ALLOWLIST_NAME
    )
    return list_problems + unreachable.stale_patterns(list_patterns, list_dead=list_dead)


def audit(path_root: pathlib.Path) -> tuple[list[str], list[str], list[str], list[str]]:
    """Audit one project tree.

    Parameters
    ----------
    path_root : pathlib.Path
        Project root holding ``src/``.

    Returns
    -------
    tuple of list of str
        Placeholder files, unreachable vendored utils, the dependencies only those utils
        import, and the allowlist problems.

    Raises
    ------
    ValueError
        If ``src/`` holds no module.
    """
    dict_modules = unreachable.module_map(path_root / "src")
    if not dict_modules:
        raise ValueError(f"no module found under {path_root / 'src'}: nothing to check")
    list_placeholders = placeholder_modules(dict_modules)
    dict_shipped = {
        str_module: path_file
        for str_module, path_file in dict_modules.items()
        if str_module not in list_placeholders
    }
    list_patterns, _ = unreachable.load_allowlist(path_root / unreachable.STR_ALLOWLIST_NAME)
    list_dead, list_open = unreachable.dead_modules(dict_shipped, list_patterns=list_patterns)
    list_residue = [str_module for str_module in list_open if is_vendored_util(str_module)]
    list_files = [
        str(dict_modules[str_module].relative_to(path_root)) for str_module in list_placeholders
    ]
    list_deps = residue_dependencies(
        dict_shipped, list_residue=list_residue, list_open=list_open, path_root=path_root
    )
    list_problems = allowlist_problems(path_root, list_dead=list_dead)
    return list_files, list_residue, list_deps, list_problems


def main(list_argv: list[str] | None = None) -> int:
    """Run the gate.

    Parameters
    ----------
    list_argv : list of str or None
        Arguments; defaults to ``sys.argv[1:]``.

    Returns
    -------
    int
        1 on a placeholder, an unparsable tree, or (under ``--strict``) any residue or
        allowlist problem; else 0.
    """
    cls_parser = argparse.ArgumentParser(description=__doc__)
    cls_parser.add_argument("--root", type=pathlib.Path, default=unreachable.PATH_ROOT)
    cls_parser.add_argument("--strict", action="store_true")
    cls_args = cls_parser.parse_args(list_argv)
    try:
        list_files, list_residue, list_deps, list_problems = audit(cls_args.root.resolve())
    except (SyntaxError, ValueError) as cls_error:
        print(f"❌ {cls_error}")
        return 1
    for str_file in list_files:
        print(
            f"❌ {str_file} still holds the lib-minimal placeholder ({STR_PLACEHOLDER!r}):"
            " replace it with the library's API or delete it before releasing"
        )
    for str_problem in list_problems:
        print(f"allowlist: {str_problem}")
    for str_module in list_residue:
        print(f"unreachable vendored util: {str_module}")
    for str_dep in list_deps:
        print(f"runtime dependency only unreachable utils import: {str_dep}")
    print(
        f"{len(list_residue)} unreachable _internal.utils module(s),"
        f" {len(list_deps)} dependency(ies) only they import"
    )
    if cls_args.strict and list_problems and not (list_files or list_residue):
        print(
            f"❌ {len(list_problems)} allowlist problem(s): give each"
            f" {unreachable.STR_ALLOWLIST_NAME} entry a reason and remove entries that match"
            " no unreachable module"
        )
    if list_residue:
        print(
            "Delete each unreachable util with its tests and the dependencies only it imports,"
            f" or allowlist it in {unreachable.STR_ALLOWLIST_NAME} with the reason it is loaded"
            " dynamically."
        )
    return int(bool(list_files) or (cls_args.strict and bool(list_residue or list_problems)))


if __name__ == "__main__":
    sys.exit(main())
