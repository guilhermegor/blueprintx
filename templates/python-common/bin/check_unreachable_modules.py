"""Fail on any ``src/`` module that no public module reaches through imports.

A public module is one whose dotted path has no ``_``-prefixed segment, bar ``__main__`` (run
by ``python -m``, so it is a root, not a dead end). The gate walks
``ast.Import`` / ``ast.ImportFrom`` from those roots, resolves relative imports, and makes
every reached module reach its parent packages.
"""

import argparse
import ast
import fnmatch
import pathlib
import sys


STR_ALLOWLIST_NAME = ".unreachable-modules.txt"
STR_REASON_SEPARATOR = "|"
STR_COMMENT_PREFIX = "#"
STR_ENTRY_MODULE = "__main__"

PATH_ROOT = pathlib.Path(__file__).resolve().parent.parent


def module_map(path_src: pathlib.Path) -> dict[str, pathlib.Path]:
    """Map every module under ``src/`` to its source file.

    Parameters
    ----------
    path_src : pathlib.Path
        The ``src`` directory.

    Returns
    -------
    dict of str to pathlib.Path
        Dotted module name (``pkg.sub.mod``; a package ``__init__`` is the package) to file.
        When ``pkg.py`` and ``pkg/__init__.py`` both exist the package wins, as it does for
        the import system.
    """
    dict_modules = {}
    for path_file in sorted(path_src.rglob("*.py")):
        list_parts = list(path_file.relative_to(path_src).with_suffix("").parts)
        if list_parts[-1] == "__init__":
            list_parts.pop()
        str_name = ".".join(list_parts)
        path_known = dict_modules.get(str_name)
        if list_parts and not (path_known and path_known.name == "__init__.py"):
            dict_modules[str_name] = path_file
    return dict_modules


def package_of(str_module: str, *, path_file: pathlib.Path) -> str:
    """Return the package a module's relative imports resolve against.

    Parameters
    ----------
    str_module : str
        Dotted module name.
    path_file : pathlib.Path
        The module's source file.

    Returns
    -------
    str
        The module itself for an ``__init__``, otherwise its parent package (possibly empty).
    """
    if path_file.name == "__init__.py":
        return str_module
    return str_module.rpartition(".")[0]


def base_of(cls_node: ast.ImportFrom, *, str_package: str) -> str | None:
    """Resolve the module a ``from ... import`` statement draws from.

    Parameters
    ----------
    cls_node : ast.ImportFrom
        The import statement.
    str_package : str
        Package the importing module resolves relative imports against.

    Returns
    -------
    str or None
        Absolute dotted name, or None when the relative import climbs above the top-level
        package (Python raises ``ImportError`` there).
    """
    if cls_node.level == 0:
        return cls_node.module or ""
    list_parts = str_package.split(".") if str_package else []
    int_keep = len(list_parts) - (cls_node.level - 1)
    if int_keep <= 0:
        return None
    if cls_node.module:
        list_parts = list_parts[:int_keep] + [cls_node.module]
    else:
        list_parts = list_parts[:int_keep]
    return ".".join(list_parts)


def imported_names(cls_tree: ast.AST, *, str_package: str) -> set[str]:
    """Collect every dotted name a module's import statements may refer to.

    Parameters
    ----------
    cls_tree : ast.AST
        The parsed module.
    str_package : str
        Package the module resolves relative imports against.

    Returns
    -------
    set of str
        Absolute dotted names. A ``from pkg import name`` yields both ``pkg`` and
        ``pkg.name``, since ``name`` may be a submodule.
    """
    set_names = set()
    for cls_node in ast.walk(cls_tree):
        if isinstance(cls_node, ast.Import):
            set_names.update(cls_alias.name for cls_alias in cls_node.names)
        if not isinstance(cls_node, ast.ImportFrom):
            continue
        str_base = base_of(cls_node, str_package=str_package)
        if str_base is None:
            continue
        set_names.add(str_base)
        for cls_alias in cls_node.names:
            set_names.add(f"{str_base}.{cls_alias.name}" if str_base else cls_alias.name)
    return set_names


def with_ancestors(str_name: str, *, dict_modules: dict[str, pathlib.Path]) -> list[str]:
    """Return the modules a dotted name reaches: itself and every parent package.

    Parameters
    ----------
    str_name : str
        Absolute dotted name.
    dict_modules : dict of str to pathlib.Path
        Every module under ``src/``.

    Returns
    -------
    list of str
        Each dotted prefix of the name that is a module under ``src/``.
    """
    list_parts = str_name.split(".")
    list_prefixes = [".".join(list_parts[: int_end + 1]) for int_end in range(len(list_parts))]
    return [str_prefix for str_prefix in list_prefixes if str_prefix in dict_modules]


def is_public(str_module: str) -> bool:
    """Say whether a module is a root of the walk.

    Parameters
    ----------
    str_module : str
        Dotted module name.

    Returns
    -------
    bool
        True when no segment of the name starts with an underscore, except ``__main__``.
    """
    return not any(
        str_part.startswith("_") and str_part != STR_ENTRY_MODULE
        for str_part in str_module.split(".")
    )


def reachable(dict_modules: dict[str, pathlib.Path], *, list_extra_roots: list[str]) -> set[str]:
    """Walk the import graph from the public modules and any extra roots.

    Parameters
    ----------
    dict_modules : dict of str to pathlib.Path
        Every module under ``src/``.
    list_extra_roots : list of str
        Modules that count as roots besides the public ones (the allowlisted ones).

    Returns
    -------
    set of str
        Every module reached, the roots included.

    Raises
    ------
    SyntaxError
        If a reached module cannot be parsed, including undecodable bytes. Parsing bytes
        honours a BOM and a PEP 263 coding cookie, as the import system does.
    ValueError
        If a reached module holds a NUL byte on Python below 3.12.
    """
    set_seen = set()
    list_queue = [str_module for str_module in dict_modules if is_public(str_module)]
    list_queue.extend(list_extra_roots)
    while list_queue:
        str_module = list_queue.pop()
        if str_module in set_seen:
            continue
        set_seen.add(str_module)
        path_file = dict_modules[str_module]
        cls_tree = ast.parse(path_file.read_bytes(), filename=str(path_file))
        for str_name in imported_names(
            cls_tree, str_package=package_of(str_module, path_file=path_file)
        ):
            list_queue.extend(with_ancestors(str_name, dict_modules=dict_modules))
    return set_seen


def load_allowlist(path_allowlist: pathlib.Path) -> tuple[list[str], list[str]]:
    """Read the allowlist: one ``<module or glob> | <reason>`` per line.

    Parameters
    ----------
    path_allowlist : pathlib.Path
        The allowlist file; a missing file is an empty allowlist. Blank lines and lines
        starting with ``#`` are skipped.

    Returns
    -------
    tuple of list of str
        The module patterns, then one problem message per entry that lacks a reason.
    """
    list_patterns = []
    list_problems = []
    if not path_allowlist.is_file():
        return list_patterns, list_problems
    list_lines = path_allowlist.read_text(encoding="utf-8").splitlines()
    for int_line, str_line in enumerate(list_lines, 1):
        if not str_line.strip() or str_line.lstrip().startswith(STR_COMMENT_PREFIX):
            continue
        str_pattern, _, str_reason = str_line.partition(STR_REASON_SEPARATOR)
        if not str_reason.strip():
            list_problems.append(
                f"{path_allowlist.name}:{int_line}: entry '{str_pattern.strip()}' has no reason"
                f" (write '<module> {STR_REASON_SEPARATOR} <why it is loaded dynamically>')"
            )
            continue
        list_patterns.append(str_pattern.strip())
    return list_patterns, list_problems


def dead_modules(
    dict_modules: dict[str, pathlib.Path], *, list_patterns: list[str]
) -> tuple[list[str], list[str]]:
    """Find the modules no root reaches, before and after the allowlist counts as roots.

    Parameters
    ----------
    dict_modules : dict of str to pathlib.Path
        Every module under ``src/``.
    list_patterns : list of str
        Allowlist patterns. An allowlisted module is loaded dynamically, so what it imports
        is reached too.

    Returns
    -------
    tuple of list of str
        The modules the public roots miss, then those still missed once the allowlisted
        ones are roots as well.
    """
    list_dead = sorted(set(dict_modules) - reachable(dict_modules, list_extra_roots=[]))
    list_allowed = [
        str_module
        for str_module in list_dead
        if any(fnmatch.fnmatchcase(str_module, str_pattern) for str_pattern in list_patterns)
    ]
    return list_dead, sorted(
        set(dict_modules) - reachable(dict_modules, list_extra_roots=list_allowed)
    )


def audit(path_root: pathlib.Path, *, path_allowlist: pathlib.Path) -> tuple[list[str], int]:
    """Audit one project tree.

    Parameters
    ----------
    path_root : pathlib.Path
        Project root holding ``src/``.
    path_allowlist : pathlib.Path
        The allowlist file.

    Returns
    -------
    tuple of list of str and int
        One message per finding, then the number of modules checked.
    """
    dict_modules = module_map(path_root / "src")
    if not dict_modules:
        return [f"no module found under {path_root / 'src'}: this gate would pass vacuously"], 0
    list_patterns, list_problems = load_allowlist(path_allowlist)
    try:
        list_dead, list_open = dead_modules(dict_modules, list_patterns=list_patterns)
    except (SyntaxError, ValueError) as cls_error:
        return [*list_problems, f"could not parse ({cls_error})"], len(dict_modules)
    for str_pattern in list_patterns:
        if not any(fnmatch.fnmatchcase(str_module, str_pattern) for str_module in list_dead):
            list_problems.append(
                f"allowlist entry '{str_pattern}' matches no unreachable module: remove it"
            )
    for str_module in list_open:
        list_problems.append(
            f"{dict_modules[str_module].relative_to(path_root)}: {str_module} is unreachable"
            " from the public modules"
        )
    return list_problems, len(dict_modules)


def main(list_argv: list[str] | None = None) -> int:
    """Run the gate.

    Parameters
    ----------
    list_argv : list of str or None
        Arguments; defaults to ``sys.argv[1:]``.

    Returns
    -------
    int
        0 when every module is reachable or allowlisted, 1 otherwise.
    """
    cls_parser = argparse.ArgumentParser(description=__doc__)
    cls_parser.add_argument("--root", type=pathlib.Path, default=PATH_ROOT)
    cls_parser.add_argument("--allowlist", type=pathlib.Path, default=None)
    cls_args = cls_parser.parse_args(list_argv)
    path_root = cls_args.root.resolve()
    path_allowlist = cls_args.allowlist or path_root / STR_ALLOWLIST_NAME
    list_problems, int_checked = audit(path_root, path_allowlist=path_allowlist)
    for str_problem in list_problems:
        print(str_problem)
    if not list_problems:
        print(f"✅ unreachable modules OK ({int_checked} module(s) checked)")
        return 0
    print(
        f"\n{len(list_problems)} finding(s). Delete an unreachable module with its tests and the"
        f" dependencies only it imported, or allowlist it in {STR_ALLOWLIST_NAME} with the reason"
        " it is loaded dynamically."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
