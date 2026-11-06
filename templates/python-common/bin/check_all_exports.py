"""Enforce that a package's ``__all__`` names every public member its submodules define.

A convention that every member of a family must follow deserves an executable check, not a
doc paragraph. The usual shape of that check is an introspective test that **discovers the
family through ``__all__``** and asserts something about each member — and that shape has a
hole it cannot see: **a member missing from ``__all__`` is invisible to it.** The sweep simply
returns one fewer item, `parametrize` generates one fewer case, and the suite passes by not
looking.

Measured (filings-cvm#164): three readers registered by an anchor-replace landed in the import
block but never in ``__all__``. They were importable, unexported, and every test was green.
The sibling failure is worse: narrowing an ``__all__`` **empties** every gate that discovers
through it — 2182 → 1311 tests with no new failure, four gates silently inert.

So this walks the FILES, not the exports. For every package whose ``__init__.py`` declares
``__all__``, it collects the public module-level names its sibling submodules define and fails
on any that the list omits.

Scope is opt-in by design: a package with no ``__all__`` is not checked. Declaring an export
list is the promise; this enforces it. Reading is done with ``ast`` — never by importing —
so the gate has no side effects and needs no dependency installed.

⚠️ Discovery matching **zero** packages is a FAILURE, not a pass. A gate that scanned nothing
also found nothing wrong, and exits 0 forever the day a path is renamed.
"""

import ast
from collections.abc import Iterable, Iterator
import pathlib
import sys


_SRC = pathlib.Path("src")
_EXCLUDED_PARTS = frozenset({"typing", "__pycache__", "example_feature"})
_BLOCK_STATEMENTS = (ast.If, ast.Try, ast.TryStar, ast.With, ast.AsyncWith)


class _UnparseableError(Exception):
    """A module the tracer had to read could not be parsed; the message names it."""


def _parse(path_module: pathlib.Path) -> ast.Module:
    """Parse a module, turning a syntax error into a reportable ``_UnparseableError``.

    Parameters
    ----------
    path_module : pathlib.Path
        The module to read.

    Returns
    -------
    ast.Module
        The parsed module.

    Raises
    ------
    _UnparseableError
        When the module is not valid Python.
    """
    try:
        return ast.parse(path_module.read_text(encoding="utf-8"))
    except SyntaxError as cls_exc:
        raise _UnparseableError(
            f"{path_module}: could not parse ({cls_exc.msg}, line {cls_exc.lineno}) — "
            f"the export check cannot trace through a file it cannot read"
        ) from cls_exc


def _module_statements(list_body: list[ast.stmt]) -> Iterator[ast.stmt]:
    """Yield the statements bound at module level, descending into ``if``/``try``/``with`` blocks.

    A guarded import (``try:``, ``if TYPE_CHECKING:``, ``if sys.version_info``, ``with suppress``)
    still binds a module-level name; function and class bodies do not, so they are not entered.

    Parameters
    ----------
    list_body : list of ast.stmt
        A module body, or the body of a block already entered.

    Yields
    ------
    ast.stmt
        Each statement, outer before inner.
    """
    for cls_node in list_body:
        yield cls_node
        if not isinstance(cls_node, _BLOCK_STATEMENTS):
            continue
        for str_field in ("body", "orelse", "finalbody"):
            yield from _module_statements(getattr(cls_node, str_field, []))
        for cls_handler in getattr(cls_node, "handlers", []):
            yield from _module_statements(cls_handler.body)


def declared_all(path_init: pathlib.Path) -> list[str] | None:
    """Return the names in a module's ``__all__``, or ``None`` when it declares none.

    Parameters
    ----------
    path_init : pathlib.Path
        The ``__init__.py`` to read.

    Returns
    -------
    list of str or None
        The exported names, or ``None`` when the module has no ``__all__``.
    """
    cls_tree = ast.parse(path_init.read_text(encoding="utf-8"))
    for cls_node in cls_tree.body:
        if not isinstance(cls_node, ast.Assign):
            continue
        for cls_target in cls_node.targets:
            if isinstance(cls_target, ast.Name) and cls_target.id == "__all__":
                if not isinstance(cls_node.value, ast.List | ast.Tuple):
                    return []
                return [
                    cls_elt.value
                    for cls_elt in cls_node.value.elts
                    if isinstance(cls_elt, ast.Constant) and isinstance(cls_elt.value, str)
                ]
    return None


def public_names(path_module: pathlib.Path) -> set[str]:
    """Return the public module-level names a submodule defines.

    Only definitions count — a name this module merely IMPORTED belongs to whoever defined it,
    and requiring re-export of every import would force the package to publish its dependencies.

    Parameters
    ----------
    path_module : pathlib.Path
        The submodule to read.

    Returns
    -------
    set of str
        Public names bound at module level by a def, class, or assignment.
    """
    return {
        str_name
        for str_name in _definitions(_parse(path_module).body)
        if not str_name.startswith("_")
    }


def _definitions(list_nodes: Iterable[ast.stmt]) -> set[str]:
    """Return every name the given statements bind by def, class, or assignment.

    Parameters
    ----------
    list_nodes : iterable of ast.stmt
        Statements to read; nested blocks are not entered.

    Returns
    -------
    set of str
        The bound names, private ones included.
    """
    set_names: set[str] = set()
    for cls_node in list_nodes:
        if isinstance(cls_node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            set_names.add(cls_node.name)
        elif isinstance(cls_node, ast.Assign):
            set_names.update(
                cls_target.id
                for cls_target in cls_node.targets
                if isinstance(cls_target, ast.Name)
            )
        elif isinstance(cls_node, ast.AnnAssign) and isinstance(cls_node.target, ast.Name):
            set_names.add(cls_node.target.id)
    return set_names


def internal_exports(path_init: pathlib.Path, set_exported: set[str]) -> list[str]:
    """Return one message per exported name imported from a module under ``_internal``.

    The leading underscore is a promise that a path is not public API, and ``__all__`` must
    not break it. A package that is itself inside ``_internal`` is out of scope.

    Parameters
    ----------
    path_init : pathlib.Path
        The package's ``__init__.py``.
    set_exported : set of str
        The names in its ``__all__``.

    Returns
    -------
    list of str
        Human-readable problems; empty when no exported name originates under ``_internal``.
    """
    if _inside_internal(path_init):
        return []
    list_problems = [_export_problem(path_init, str_name) for str_name in sorted(set_exported)]
    return list(dict.fromkeys(str_problem for str_problem in list_problems if str_problem))


def _export_problem(path_init: pathlib.Path, str_name: str) -> str | None:
    """Return the problem for one exported name, or ``None`` when it is not an ``_internal`` leak.

    Parameters
    ----------
    path_init : pathlib.Path
        The package's ``__init__.py``.
    str_name : str
        One name from its ``__all__``.

    Returns
    -------
    str or None
        The message, which is the parse failure when a file on the trace is unreadable.
    """
    try:
        str_origin = _internal_origin(path_init, str_name, frozenset())
    except _UnparseableError as cls_exc:
        return str(cls_exc)
    if str_origin is None:
        return None
    return (
        f"{path_init}: '{str_name}' in __all__ is defined under _internal "
        f"({str_origin}) — the underscore marks it private, so it must not be "
        f"part of the public surface"
    )


def _inside_internal(path_init: pathlib.Path) -> bool:
    """Return whether the package sits inside an ``_internal`` package (checkout path ignored).

    Parameters
    ----------
    path_init : pathlib.Path
        The package's ``__init__.py``.

    Returns
    -------
    bool
        ``True`` when a package directory above it, up to the top package, is ``_internal``.
    """
    path_dir = path_init.parent
    while path_dir.name != "_internal":
        if path_dir.parent == path_dir or not (path_dir.parent / "__init__.py").is_file():
            return False
        path_dir = path_dir.parent
    return True


def _internal_origin(
    path_module: pathlib.Path, str_name: str, set_seen: frozenset[pathlib.Path]
) -> str | None:
    """Return the ``_internal`` module a module-level binding of ``str_name`` comes from.

    Only bindings in the module namespace count, so an import inside a function body cannot
    shadow a public name; imports under a module-level ``try:`` or ``if`` do count. An import
    of a first-party submodule, relative or absolute, is followed into that file, so a name
    re-exported through a public module is traced to its definition. A ``*`` import is a
    fallback, tried only when nothing in the module binds the name explicitly.

    Parameters
    ----------
    path_module : pathlib.Path
        The module whose namespace is read.
    str_name : str
        The bound name to trace.
    set_seen : frozenset of pathlib.Path
        Modules already visited, so an import cycle terminates.

    Returns
    -------
    str or None
        The dotted ``_internal`` module, or ``None`` when the name does not originate there.
    """
    if path_module in set_seen:
        return None
    list_nodes = list(_module_statements(_parse(path_module).body))
    set_next = set_seen | {path_module}
    for cls_node in list_nodes:
        str_hit = _node_origin(path_module, cls_node, str_name, set_next)
        if str_hit is not None:
            return str_hit
    if str_name in _definitions(list_nodes) | _imported_names(list_nodes):
        return None
    return next(
        (
            str_hit
            for cls_node in list_nodes
            if isinstance(cls_node, ast.ImportFrom)
            and any(cls_alias.name == "*" for cls_alias in cls_node.names)
            for str_hit in [_star_origin(path_module, cls_node, str_name, set_next)]
            if str_hit is not None
        ),
        None,
    )


def _star_origin(
    path_module: pathlib.Path,
    cls_node: ast.ImportFrom,
    str_name: str,
    set_seen: frozenset[pathlib.Path],
) -> str | None:
    """Trace ``str_name`` through one ``*`` import, attributing it only to a module that has it.

    A star import from an ``_internal`` module leaks only the names that module actually binds,
    so a public name supplied by a sibling star import is not charged to it. When the
    ``_internal`` file cannot be resolved the name is attributed to it, as before.

    Parameters
    ----------
    path_module : pathlib.Path
        The module containing the import.
    cls_node : ast.ImportFrom
        The ``from … import *`` statement.
    str_name : str
        The bound name to trace.
    set_seen : frozenset of pathlib.Path
        Modules already visited.

    Returns
    -------
    str or None
        The dotted ``_internal`` module, or ``None``.
    """
    path_target = _import_target(path_module, cls_node)
    if "_internal" in (cls_node.module or "").split(".") and path_target is not None:
        list_nodes = list(_module_statements(_parse(path_target).body))
        if str_name not in _definitions(list_nodes) | _imported_names(list_nodes):
            return None
    return _from_import_origin(path_module, cls_node, str_name, set_seen)


def _imported_names(list_nodes: Iterable[ast.stmt]) -> set[str]:
    """Return every name the given statements bind by a non-star import.

    Parameters
    ----------
    list_nodes : iterable of ast.stmt
        Statements to read.

    Returns
    -------
    set of str
        The local names bound by ``import`` and ``from … import`` (``*`` excluded).
    """
    return {
        cls_alias.asname or cls_alias.name.split(".")[0]
        for cls_node in list_nodes
        if isinstance(cls_node, ast.Import | ast.ImportFrom)
        for cls_alias in cls_node.names
        if cls_alias.name != "*"
    }


def _node_origin(
    path_module: pathlib.Path,
    cls_node: ast.stmt,
    str_name: str,
    set_seen: frozenset[pathlib.Path],
) -> str | None:
    """Trace ``str_name`` through one module-level statement, or ``None`` when it does not bind it.

    Parameters
    ----------
    path_module : pathlib.Path
        The module containing the statement.
    cls_node : ast.stmt
        A module-level statement.
    str_name : str
        The bound name to trace.
    set_seen : frozenset of pathlib.Path
        Modules already visited.

    Returns
    -------
    str or None
        The dotted ``_internal`` module, or ``None``.
    """
    if isinstance(cls_node, ast.Import):
        return next(
            (
                cls_alias.name
                for cls_alias in cls_node.names
                if cls_alias.asname == str_name and "_internal" in cls_alias.name.split(".")
            ),
            None,
        )
    if not isinstance(cls_node, ast.ImportFrom):
        return None
    for cls_alias in cls_node.names:
        if (cls_alias.asname or cls_alias.name) == str_name:
            return _from_import_origin(path_module, cls_node, cls_alias.name, set_seen)
    return None


def _from_import_origin(
    path_module: pathlib.Path,
    cls_node: ast.ImportFrom,
    str_source_name: str,
    set_seen: frozenset[pathlib.Path],
) -> str | None:
    """Trace one ``from … import`` binding to an ``_internal`` module, or ``None``.

    Parameters
    ----------
    path_module : pathlib.Path
        The module containing the import.
    cls_node : ast.ImportFrom
        The import statement.
    str_source_name : str
        The name as defined in the module it is imported from.
    set_seen : frozenset of pathlib.Path
        Modules already visited.

    Returns
    -------
    str or None
        The dotted ``_internal`` module, or ``None`` when the import does not lead there.
    """
    if "_internal" in (cls_node.module or "").split("."):
        return cls_node.module
    if str_source_name == "_internal":
        return f"{cls_node.module}._internal" if cls_node.module else str_source_name
    path_target = _import_target(path_module, cls_node)
    if path_target is None:
        return None
    return _internal_origin(path_target, str_source_name, set_seen)


def _import_target(path_module: pathlib.Path, cls_node: ast.ImportFrom) -> pathlib.Path | None:
    """Resolve a first-party ``from … import`` to the file it names, or ``None``.

    A relative import climbs from the importing module's own package; an absolute one resolves
    only when its first component is the name of the top package the importing module sits in.

    Parameters
    ----------
    path_module : pathlib.Path
        The module containing the import.
    cls_node : ast.ImportFrom
        The import statement.

    Returns
    -------
    pathlib.Path or None
        The module or package ``__init__.py`` file, or ``None`` when it is not first-party or
        does not exist.
    """
    if not cls_node.module:
        return None
    tuple_parts = tuple(cls_node.module.split("."))
    if cls_node.level:
        if cls_node.level > len(path_module.parents):
            return None
        return _module_file(path_module.parents[cls_node.level - 1], tuple_parts)
    path_top = _top_package(path_module)
    if tuple_parts[0] != path_top.name:
        return None
    return _module_file(path_top.parent, tuple_parts)


def _top_package(path_module: pathlib.Path) -> pathlib.Path:
    """Return the outermost package directory that contains a module.

    Parameters
    ----------
    path_module : pathlib.Path
        Any module inside a package.

    Returns
    -------
    pathlib.Path
        The package directory furthest up the tree that still holds an ``__init__.py``.
    """
    path_dir = path_module.parent
    while path_dir.parent != path_dir and (path_dir.parent / "__init__.py").is_file():
        path_dir = path_dir.parent
    return path_dir


def _module_file(path_base: pathlib.Path, tuple_parts: tuple[str, ...]) -> pathlib.Path | None:
    """Return the file a dotted module path names below a base directory, or ``None``.

    Parameters
    ----------
    path_base : pathlib.Path
        The directory the dotted path starts from.
    tuple_parts : tuple of str
        The dotted path, split.

    Returns
    -------
    pathlib.Path or None
        ``<base>/a/b.py`` or ``<base>/a/b/__init__.py``, whichever exists.
    """
    path_target = path_base.joinpath(*tuple_parts)
    return next(
        (
            path_candidate
            for path_candidate in (path_target.with_suffix(".py"), path_target / "__init__.py")
            if path_candidate.is_file()
        ),
        None,
    )


def _missing_exports(
    path_init: pathlib.Path, path_module: pathlib.Path, set_exported: set[str]
) -> list[str]:
    """Return one message per public name a submodule defines that ``__all__`` omits.

    Parameters
    ----------
    path_init : pathlib.Path
        The package's ``__init__.py``.
    path_module : pathlib.Path
        The submodule to read.
    set_exported : set of str
        The names in the package's ``__all__``.

    Returns
    -------
    list of str
        Human-readable problems; the parse failure when the submodule is unreadable.
    """
    try:
        set_missing = public_names(path_module) - set_exported
    except _UnparseableError as cls_exc:
        return [str(cls_exc)]
    return [
        f"{path_init}: '{str_name}' is defined in {path_module.name} but missing from "
        f"__all__ — importable, unexported, and invisible to every gate that "
        f"discovers the family THROUGH __all__"
        for str_name in sorted(set_missing)
    ]


def check_package(path_init: pathlib.Path) -> list[str]:
    """Return one message per public name the package defines but does not export.

    Parameters
    ----------
    path_init : pathlib.Path
        The package's ``__init__.py``.

    Returns
    -------
    list of str
        Human-readable problems; empty when the export list is complete.
    """
    list_exported = declared_all(path_init)
    if list_exported is None:
        return []
    set_exported = set(list_exported)
    list_problems: list[str] = internal_exports(path_init, set_exported)
    for path_module in sorted(path_init.parent.glob("*.py")):
        if path_module.name != "__init__.py":
            list_problems += _missing_exports(path_init, path_module, set_exported)
    return list(dict.fromkeys(list_problems))


def main() -> int:
    """Run the gate over every package under ``src/`` that declares ``__all__``.

    Returns
    -------
    int
        ``0`` when every declared export list is complete, ``1`` otherwise.
    """
    list_inits = [
        path_init
        for path_init in _SRC.rglob("__init__.py")
        if _EXCLUDED_PARTS.isdisjoint(path_init.parts) and declared_all(path_init) is not None
    ]
    if not list_inits:
        print(
            "check_all_exports: found ZERO packages declaring __all__ under src/ — refusing to "
            "report success. Either the layout moved or the discovery is broken; a gate that "
            "scanned nothing also found nothing wrong.",
            file=sys.stderr,
        )
        return 1

    list_problems = [
        str_problem for path_init in list_inits for str_problem in check_package(path_init)
    ]
    for str_problem in list_problems:
        print(f"❌ {str_problem}", file=sys.stderr)
    if list_problems:
        return 1
    print(f"__all__ exports complete in {len(list_inits)} package(s).")
    return 0


if __name__ == "__main__":
    for cls_stream in (sys.stdout, sys.stderr):
        if hasattr(cls_stream, "reconfigure"):
            cls_stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
