"""Fail on any ``src/`` module that no public module reaches through imports.

A public module is one whose dotted path has no ``_``-prefixed segment. The gate walks
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
    """
    dict_modules = {}
    for path_file in sorted(path_src.rglob("*.py")):
        list_parts = list(path_file.relative_to(path_src).with_suffix("").parts)
        if list_parts[-1] == "__init__":
            list_parts.pop()
        if list_parts:
            dict_modules[".".join(list_parts)] = path_file
    return dict_modules


def package_of(str_module: str, path_file: pathlib.Path) -> str:
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


def base_of(cls_node: ast.ImportFrom, str_package: str) -> str | None:
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
        Absolute dotted name (empty for the source root), or None when the relative import
        climbs above ``src/``.
    """
    if cls_node.level == 0:
        return cls_node.module or ""
    list_parts = str_package.split(".") if str_package else []
    int_keep = len(list_parts) - (cls_node.level - 1)
    if int_keep < 0:
        return None
    if cls_node.module:
        list_parts = list_parts[:int_keep] + [cls_node.module]
    else:
        list_parts = list_parts[:int_keep]
    return ".".join(list_parts)


def imported_names(cls_tree: ast.AST, str_package: str) -> set[str]:
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
        str_base = base_of(cls_node, str_package)
        if str_base is None:
            continue
        set_names.add(str_base)
        for cls_alias in cls_node.names:
            set_names.add(f"{str_base}.{cls_alias.name}" if str_base else cls_alias.name)
    return set_names


def with_ancestors(str_name: str, dict_modules: dict[str, pathlib.Path]) -> list[str]:
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
        True when no segment of the name starts with an underscore.
    """
    return not any(str_part.startswith("_") for str_part in str_module.split("."))


def reachable(dict_modules: dict[str, pathlib.Path]) -> set[str]:
    """Walk the import graph from the public modules.

    Parameters
    ----------
    dict_modules : dict of str to pathlib.Path
        Every module under ``src/``.

    Returns
    -------
    set of str
        Every module reached, the roots included.

    Raises
    ------
    SyntaxError
        If a reached module cannot be parsed.
    """
    set_seen = set()
    list_queue = [str_module for str_module in dict_modules if is_public(str_module)]
    while list_queue:
        str_module = list_queue.pop()
        if str_module in set_seen:
            continue
        set_seen.add(str_module)
        path_file = dict_modules[str_module]
        cls_tree = ast.parse(path_file.read_text(encoding="utf-8"), filename=str(path_file))
        for str_name in imported_names(cls_tree, package_of(str_module, path_file)):
            list_queue.extend(with_ancestors(str_name, dict_modules))
    return set_seen


def load_allowlist(path_allowlist: pathlib.Path) -> tuple[list[str], list[str]]:
    """Read the allowlist: one ``<module or glob> | <reason>`` per line.

    Parameters
    ----------
    path_allowlist : pathlib.Path
        The allowlist file; a missing file is an empty allowlist.

    Returns
    -------
    tuple of list of str
        The module patterns, then one problem message per entry that lacks a reason.
    """
    list_patterns = []
    list_problems = []
    if not path_allowlist.is_file():
        return list_patterns, list_problems
    for int_line, str_line in enumerate(path_allowlist.read_text(encoding="utf-8").splitlines(), 1):
        if not str_line.strip():
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


def audit(path_root: pathlib.Path, path_allowlist: pathlib.Path) -> tuple[list[str], int]:
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
        set_reached = reachable(dict_modules)
    except SyntaxError as cls_error:
        return [*list_problems, f"could not parse ({cls_error})"], len(dict_modules)
    list_dead = sorted(set(dict_modules) - set_reached)
    for str_pattern in list_patterns:
        if not fnmatch.filter(list_dead, str_pattern):
            list_problems.append(
                f"allowlist entry '{str_pattern}' matches no unreachable module: remove it"
            )
    for str_module in list_dead:
        if not any(fnmatch.fnmatch(str_module, str_pattern) for str_pattern in list_patterns):
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
    list_problems, int_checked = audit(path_root, path_allowlist)
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
