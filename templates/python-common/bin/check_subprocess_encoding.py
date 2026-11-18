"""Fail a text-mode ``subprocess`` call that does not name its encoding (blueprintx#1203).

``subprocess.run(..., text=True)`` decodes the pipe with the locale code page, which is
cp1252 on Windows. A child that prints UTF-8 then kills the reader thread and leaves
``stdout`` as ``None``. Ruff's ``PLW1514`` covers ``open()`` only, so this ``ast`` gate
covers the subprocess family: ``run``, ``check_output``, ``check_call``, ``call`` and
``Popen``, called as ``subprocess.<name>`` or imported from ``subprocess``.

A call is a finding when it passes ``text=True`` (or ``universal_newlines=True``) without
``encoding=``. A call that forwards ``**kwargs`` is not judged, since the keywords are not
visible. Rationale and the rule: ``CONTRIBUTING.md`` in BlueprintX.
"""

import argparse
import ast
import pathlib
import sys


PATH_ROOT = pathlib.Path(__file__).resolve().parent.parent

TUPLE_SKIP_DIRS = (
    ".git",
    ".claude",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "htmlcov",
    "node_modules",
    "site",
)

SET_CALLS = frozenset({"run", "check_output", "check_call", "call", "Popen"})

TUPLE_TEXT_KWARGS = ("text", "universal_newlines")


def bare_subprocess_names(cls_tree: ast.AST) -> set:
    """Return the subprocess callables a module imports by bare name.

    Parameters
    ----------
    cls_tree : ast.AST
        The parsed module.

    Returns
    -------
    set of str
        Local names bound by ``from subprocess import <name> [as <alias>]``.
    """
    return {
        cls_alias.asname or cls_alias.name
        for cls_node in ast.walk(cls_tree)
        if isinstance(cls_node, ast.ImportFrom) and cls_node.module == "subprocess"
        for cls_alias in cls_node.names
        if cls_alias.name in SET_CALLS
    }


def subprocess_module_aliases(cls_tree: ast.AST) -> set:
    """Return the local names the ``subprocess`` module is bound to.

    Parameters
    ----------
    cls_tree : ast.AST
        The parsed module.

    Returns
    -------
    set of str
        Names bound by ``import subprocess [as <alias>]``; empty without such an import.
    """
    return {
        cls_alias.asname or "subprocess"
        for cls_node in ast.walk(cls_tree)
        if isinstance(cls_node, ast.Import)
        for cls_alias in cls_node.names
        if cls_alias.name == "subprocess"
    }


def is_subprocess_call(cls_call: ast.Call, *, set_bare: set, set_modules: set) -> bool:
    """Return whether a call targets one of the checked subprocess callables.

    Parameters
    ----------
    cls_call : ast.Call
        A call node.
    set_bare : set of str
        Bare names the module imported from ``subprocess``.
    set_modules : set of str
        Local names bound to the ``subprocess`` module.

    Returns
    -------
    bool
        True for ``<module>.<name>(...)`` or a bare imported name.
    """
    cls_func = cls_call.func
    if isinstance(cls_func, ast.Attribute):
        return (
            cls_func.attr in SET_CALLS
            and isinstance(cls_func.value, ast.Name)
            and cls_func.value.id in set_modules
        )
    return isinstance(cls_func, ast.Name) and cls_func.id in set_bare


def drops_encoding(cls_call: ast.Call) -> bool:
    """Return whether a call decodes text without naming an encoding.

    Parameters
    ----------
    cls_call : ast.Call
        A subprocess call node.

    Returns
    -------
    bool
        True when a text keyword is set, ``encoding`` is absent, and no ``**kwargs``
        could be supplying it.
    """
    dict_kw = {cls_kw.arg: cls_kw.value for cls_kw in cls_call.keywords}
    cls_encoding = dict_kw.get("encoding")
    is_none_literal = isinstance(cls_encoding, ast.Constant) and cls_encoding.value is None
    if None in dict_kw or (cls_encoding is not None and not is_none_literal):
        return False
    return any(
        str_kw in dict_kw
        and not (isinstance(dict_kw[str_kw], ast.Constant) and not dict_kw[str_kw].value)
        for str_kw in TUPLE_TEXT_KWARGS
    )


def file_problems(path_file: pathlib.Path, *, path_root: pathlib.Path) -> list:
    """Return one message per offending call in a Python file.

    Parameters
    ----------
    path_file : pathlib.Path
        A ``.py`` source file.
    path_root : pathlib.Path
        Root used to shorten the path in messages.

    Returns
    -------
    list of str
        Findings; an unparsable file is one finding, since it cannot be checked.
    """
    try:
        str_shown = str(path_file.relative_to(path_root))
    except ValueError:
        str_shown = str(path_file)
    try:
        cls_tree = ast.parse(path_file.read_text(encoding="utf-8"), filename=str_shown)
    except (SyntaxError, UnicodeDecodeError) as cls_err:
        return [f"{str_shown}: could not parse ({cls_err})"]

    set_bare = bare_subprocess_names(cls_tree)
    set_modules = subprocess_module_aliases(cls_tree)
    return [
        f"{str_shown}:{cls_node.lineno}: text-mode subprocess call without encoding="
        for cls_node in ast.walk(cls_tree)
        if isinstance(cls_node, ast.Call)
        and is_subprocess_call(cls_node, set_bare=set_bare, set_modules=set_modules)
        and drops_encoding(cls_node)
    ]


def audit_paths(path_root: pathlib.Path) -> list:
    """Discover every Python file under the root, skipping vendored and generated trees.

    Parameters
    ----------
    path_root : pathlib.Path
        Directory to walk.

    Returns
    -------
    list of pathlib.Path
        Sorted ``.py`` paths.
    """
    return sorted(
        path_file
        for path_file in path_root.rglob("*.py")
        if not set(path_file.relative_to(path_root).parts) & set(TUPLE_SKIP_DIRS)
    )


def main(list_argv: list) -> int:
    """Check the named files, or every Python file under ``--root``.

    Parameters
    ----------
    list_argv : list of str
        Optional ``--root <dir>`` and filenames, as pre-commit passes them.

    Returns
    -------
    int
        0 when every call names its encoding, 1 on a finding or an empty discovery.
    """
    cls_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cls_parser.add_argument("--root", type=pathlib.Path, default=PATH_ROOT)
    cls_parser.add_argument("files", nargs="*", type=pathlib.Path)
    cls_args = cls_parser.parse_args(list_argv)

    path_root = cls_args.root.resolve()
    list_paths = [path.resolve() for path in cls_args.files] or audit_paths(path_root)
    if not list_paths:
        print(f"ERROR: no .py file found under {path_root}; this gate would pass vacuously.")
        return 1

    list_problems = [
        str_problem
        for path_file in list_paths
        for str_problem in file_problems(path_file, path_root=path_root)
    ]
    for str_problem in list_problems:
        print(str_problem)
    if not list_problems:
        print(f"OK: subprocess encoding ({len(list_paths)} file(s) checked)")
        return 0

    print(
        f'\n{len(list_problems)} finding(s). Add encoding="utf-8" next to text=True: without '
        f"it the pipe is decoded with the locale code page (cp1252 on Windows)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
