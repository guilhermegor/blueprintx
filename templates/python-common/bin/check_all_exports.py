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
import pathlib
import sys


_SRC = pathlib.Path("src")
_EXCLUDED_PARTS = frozenset({"typing", "__pycache__", "example_feature"})


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
    set_names: set[str] = set()
    cls_tree = ast.parse(path_module.read_text(encoding="utf-8"))
    for cls_node in cls_tree.body:
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
    return {str_name for str_name in set_names if not str_name.startswith("_")}


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
    if "_internal" in path_init.parts:
        return []
    list_problems: list[str] = []
    for str_name in sorted(set_exported):
        str_origin = _internal_origin(path_init, str_name, frozenset())
        if str_origin is not None:
            list_problems.append(
                f"{path_init}: '{str_name}' in __all__ is defined under _internal "
                f"({str_origin}) — the underscore marks it private, so it must not be "
                f"part of the public surface"
            )
    return list_problems


def _internal_origin(
    path_module: pathlib.Path, str_name: str, set_seen: frozenset[pathlib.Path]
) -> str | None:
    """Return the ``_internal`` module a module-level binding of ``str_name`` comes from.

    Only bindings in the module namespace count, so an import inside a function body cannot
    shadow a public name. A relative import of a sibling submodule is followed into that
    sibling, so a name re-exported through a public module is traced to its definition.

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
    cls_tree = ast.parse(path_module.read_text(encoding="utf-8"))
    for cls_node in cls_tree.body:
        str_hit = _node_origin(path_module, cls_node, str_name, set_seen | {path_module})
        if str_hit is not None:
            return str_hit
    return None


def _node_origin(
    path_module: pathlib.Path,
    cls_node: ast.stmt,
    str_name: str,
    set_seen: frozenset[pathlib.Path],
) -> str | None:
    """Trace ``str_name`` through one top-level statement, or ``None`` when it does not bind it.

    Parameters
    ----------
    path_module : pathlib.Path
        The module containing the statement.
    cls_node : ast.stmt
        A top-level statement.
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
    if cls_node.level != 1 or not cls_node.module:
        return None
    path_sibling = path_module.parent / f"{cls_node.module}.py"
    if not path_sibling.is_file():
        return None
    return _internal_origin(path_sibling, str_source_name, set_seen)


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
        if path_module.name == "__init__.py":
            continue
        for str_name in sorted(public_names(path_module) - set_exported):
            list_problems.append(
                f"{path_init}: '{str_name}' is defined in {path_module.name} but missing from "
                f"__all__ — importable, unexported, and invisible to every gate that "
                f"discovers the family THROUGH __all__"
            )
    return list_problems


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
