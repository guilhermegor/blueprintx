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


_SET_WRITER_MODULES = frozenset({"builtins", "sys", "inspect"})
_SET_SAFE_DECORATORS = frozenset(
    {
        "classmethod",
        "property",
        "abstractmethod",
        "override",
        "cached_property",
        "final",
        "overload",
    }
)
_SET_ACCESSORS = frozenset({"setter", "getter", "deleter"})
_SET_SAFE_MODULES = frozenset({"abc", "typing", "typing_extensions", "functools", "builtins"})
_TUPLE_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
_SET_DYNAMIC_WRITERS = frozenset(
    {
        "globals",
        "locals",
        "vars",
        "setattr",
        "exec",
        "eval",
        "__import__",
        "modules",
        "f_globals",
        "_getframe",
        "currentframe",
        "__globals__",
        "f_locals",
    }
)


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


def _extends_all(list_nodes: list[ast.stmt]) -> bool:
    """Return whether ``__all__`` is anything but one literal list the gate can read.

    ``declared_all`` reads only the first assignment, and only its string literals, so a second
    assignment, ``+=``, ``.extend``, ``.append``, a subscript write, or a non-literal value
    leaves an ``__all__`` the gate cannot trust to exclude a name.

    Parameters
    ----------
    list_nodes : list of ast.stmt
        The module-level statements.

    Returns
    -------
    bool
        ``True`` when ``__all__`` is not a single literal list of strings.
    """
    list_subs = [cls_sub for cls_node in list_nodes for cls_sub in ast.walk(cls_node)]
    int_stores = sum(
        isinstance(cls_sub, ast.Name)
        and cls_sub.id == "__all__"
        and isinstance(cls_sub.ctx, ast.Store)
        for cls_sub in list_subs
    )
    return int_stores > 1 or any(
        _all_is_opaque(cls_sub) or _all_is_deleted(cls_sub) for cls_sub in list_subs
    )


def _all_is_deleted(cls_sub: ast.AST) -> bool:
    """Return whether a node is ``__all__`` being deleted, which makes a star import export all.

    Parameters
    ----------
    cls_sub : ast.AST
        Any node under a module-level statement.

    Returns
    -------
    bool
        ``True`` for the ``__all__`` in ``del __all__``.
    """
    return (
        isinstance(cls_sub, ast.Name)
        and cls_sub.id == "__all__"
        and isinstance(cls_sub.ctx, ast.Del)
    )


def _all_is_opaque(cls_sub: ast.AST) -> bool:
    """Return whether one node reaches into ``__all__`` or assigns it a non-literal value.

    Parameters
    ----------
    cls_sub : ast.AST
        Any node under a module-level statement.

    Returns
    -------
    bool
        ``True`` for ``__all__.x``, ``__all__[...]``, or ``__all__ = <not a string list>``.
    """
    if isinstance(cls_sub, ast.Attribute | ast.Subscript):
        return isinstance(cls_sub.value, ast.Name) and cls_sub.value.id == "__all__"
    if not isinstance(cls_sub, ast.Assign):
        return False
    if not any(isinstance(cls_t, ast.Name) and cls_t.id == "__all__" for cls_t in cls_sub.targets):
        return False
    return not isinstance(cls_sub.value, ast.List | ast.Tuple) or any(
        not (isinstance(cls_elt, ast.Constant) and isinstance(cls_elt.value, str))
        for cls_elt in cls_sub.value.elts
    )


def _scope_nodes(list_nodes: list[ast.stmt]) -> Iterator[ast.AST]:
    """Yield every node in the statements, not entering a nested def, class or lambda.

    Parameters
    ----------
    list_nodes : list of ast.stmt
        The module-level statements.

    Yields
    ------
    ast.AST
        Each node evaluated in the module namespace itself.
    """
    list_stack: list[ast.AST] = list(list_nodes)
    while list_stack:
        cls_cur = list_stack.pop()
        yield cls_cur
        if isinstance(cls_cur, _TUPLE_SCOPES):
            list_stack.extend(_header_nodes(cls_cur))
        elif isinstance(cls_cur, ast.comprehension):
            list_stack.extend([cls_cur.iter, *cls_cur.ifs])
        else:
            list_stack.extend(ast.iter_child_nodes(cls_cur))


def _header_nodes(
    cls_scope: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda,
) -> list[ast.AST]:
    """Return the parts of a def, class or lambda that run in the enclosing scope.

    Decorators, defaults, annotations and class bases are evaluated where the statement sits, so
    a walrus there binds a name in that scope even though the body does not.

    Parameters
    ----------
    cls_scope : ast.FunctionDef or ast.AsyncFunctionDef or ast.ClassDef or ast.Lambda
        The nested scope.

    Returns
    -------
    list of ast.AST
        The expressions evaluated outside its body.
    """
    if isinstance(cls_scope, ast.ClassDef):
        return [*cls_scope.decorator_list, *cls_scope.bases, *cls_scope.keywords]
    cls_args = cls_scope.args
    list_found: list[ast.AST] = [*cls_args.defaults, *filter(None, cls_args.kw_defaults)]
    if isinstance(cls_scope, ast.Lambda):
        return list_found
    list_annots = [
        cls_arg.annotation
        for cls_arg in [
            *cls_args.posonlyargs,
            *cls_args.args,
            *cls_args.kwonlyargs,
            *filter(None, [cls_args.vararg, cls_args.kwarg]),
        ]
        if cls_arg.annotation
    ]
    return [
        *cls_scope.decorator_list,
        *list_found,
        *list_annots,
        *filter(None, [cls_scope.returns]),
    ]


def _binds_dynamically(list_nodes: list[ast.stmt]) -> bool:
    """Return whether the module writes its namespace by a route the AST cannot list.

    The whole tree is read, nested scopes, defaults and decorators included, because a function
    called at import time writes the module namespace as surely as a module-level statement.
    A writer name counts as a bare name or as an attribute (``builtins.exec``, ``sys.modules``).
    The one exemption is ``setattr(x, ...)`` or ``vars(x)`` inside a method body, where ``x`` is
    that method's own first parameter: a caller can still pass a module there, so a lambda or a
    plain function never qualifies. A file that binds ``setattr`` or ``vars`` itself gets none.

    Parameters
    ----------
    list_nodes : list of ast.stmt
        The module-level statements.

    Returns
    -------
    bool
        ``True`` when a dynamic writer is named outside that exemption.
    """
    set_exempt = (
        set()
        if _module_shadows_writer(list_nodes)
        else {
            int_id for cls_fn in _methods(list_nodes) for int_id in _own_parameter_writes(cls_fn)
        }
    )
    return any(
        _names_writer(cls_sub) and id(cls_sub) not in set_exempt
        for cls_node in list_nodes
        for cls_sub in ast.walk(cls_node)
    )


def _names_writer(cls_sub: ast.AST) -> bool:
    """Return whether a node names a dynamic writer, including through an import alias.

    Parameters
    ----------
    cls_sub : ast.AST
        Any node.

    Returns
    -------
    bool
        ``True`` for a bare or attribute writer name, a ``__class__`` store, or
        ``from x import <writer> as y``.
    """
    if isinstance(cls_sub, ast.Name):
        return cls_sub.id in _SET_DYNAMIC_WRITERS
    if isinstance(cls_sub, ast.Attribute):
        return cls_sub.attr in _SET_DYNAMIC_WRITERS or (
            cls_sub.attr == "__class__" and isinstance(cls_sub.ctx, ast.Store)
        )
    return (
        isinstance(cls_sub, ast.ImportFrom)
        and cls_sub.level == 0
        and cls_sub.module in _SET_WRITER_MODULES
        and any(cls_alias.name in _SET_DYNAMIC_WRITERS for cls_alias in cls_sub.names)
    )


def _own_parameter_writes(cls_fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[int]:
    """Return the ids of ``setattr``/``vars`` names that act on this method's own ``self``/``cls``.

    A ``staticmethod`` has no bound first parameter, a rebound ``self`` is no longer the
    instance, and a nested def or lambda that takes the name as its own parameter shadows it,
    so none of those exempt. A closure that merely reads the method's ``self`` still does.

    Parameters
    ----------
    cls_fn : ast.FunctionDef or ast.AsyncFunctionDef
        A method with at least one positional parameter.

    Returns
    -------
    set of int
        ``id()`` of each exempt ``Name`` node; empty when the method gets no exemption.
    """
    list_positional = [*cls_fn.args.posonlyargs, *cls_fn.args.args]
    str_param = list_positional[0].arg
    if (
        str_param not in {"self", "cls"}
        or len(cls_fn.args.defaults) >= len(list_positional)
        or _loses_exemption(cls_fn)
        or _rebinds(cls_fn, str_param)
        or _shadows_writer(cls_fn)
        or _shadowed_by_nested(cls_fn, str_param)
    ):
        return set()
    return {
        id(cls_hit)
        for cls_stmt in cls_fn.body
        for cls_sub in ast.walk(cls_stmt)
        for cls_hit in [_own_write_node(cls_sub, str_param)]
        if cls_hit is not None
    }


def _own_write_node(cls_sub: ast.AST, str_param: str) -> ast.AST | None:
    """Return the node to exempt when ``cls_sub`` writes through the parameter, else ``None``.

    Parameters
    ----------
    cls_sub : ast.AST
        Any node under a method body.
    str_param : str
        The method's first parameter name.

    Returns
    -------
    ast.AST or None
        The ``setattr``/``vars`` name of a call on the parameter, or the ``__class__``
        attribute of a store to it.
    """
    if isinstance(cls_sub, ast.Attribute):
        is_own = isinstance(cls_sub.value, ast.Name) and cls_sub.value.id == str_param
        return cls_sub if is_own and cls_sub.attr == "__class__" else None
    if not (isinstance(cls_sub, ast.Call) and isinstance(cls_sub.func, ast.Name)):
        return None
    is_own = bool(cls_sub.args) and (
        isinstance(cls_sub.args[0], ast.Name) and cls_sub.args[0].id == str_param
    )
    return cls_sub.func if is_own and cls_sub.func.id in {"setattr", "vars"} else None


def _shadowed_by_nested(cls_fn: ast.FunctionDef | ast.AsyncFunctionDef, str_param: str) -> bool:
    """Return whether a def or lambda nested in the method takes the name as a parameter.

    Parameters
    ----------
    cls_fn : ast.FunctionDef or ast.AsyncFunctionDef
        The method.
    str_param : str
        Its first parameter name.

    Returns
    -------
    bool
        ``True`` when any nested scope declares a parameter of that name.
    """
    return any(
        isinstance(cls_sub, ast.arg) and cls_sub.arg == str_param
        for cls_stmt in cls_fn.body
        for cls_sub in ast.walk(cls_stmt)
    )


def _loses_exemption(cls_fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return whether a def gets no ``self``/``cls`` exemption (``__new__``, unknown decorator).

    Only ``classmethod``, ``property``, ``abstractmethod``, ``override``, ``cached_property``,
    ``final`` and ``overload`` (bare, or on ``abc``/``typing``/``typing_extensions``/
    ``functools``/``builtins``) and
    ``*.setter``/``getter``/``deleter`` keep the exemption. ``staticmethod`` and any
    decorator that could call the method with another object (``@(lambda fn: fn(me))``)
    lose it.

    Parameters
    ----------
    cls_fn : ast.FunctionDef or ast.AsyncFunctionDef
        The def.

    Returns
    -------
    bool
        ``True`` when the def is ``__new__`` or carries a decorator outside the safe set.
    """
    return cls_fn.name == "__new__" or not all(
        _is_safe_decorator(cls_dec, cls_fn.name) for cls_dec in cls_fn.decorator_list
    )


def _is_safe_decorator(cls_dec: ast.expr, str_method: str) -> bool:
    """Return whether a decorator is one of the known names that never calls the method.

    A property accessor counts only on the method's own name (``@x.setter def x``).

    Parameters
    ----------
    cls_dec : ast.expr
        One entry of ``decorator_list``.
    str_method : str
        The name of the decorated method.

    Returns
    -------
    bool
        ``True`` for a safe bare name, a safe name on a known module, or a property accessor.
    """
    if isinstance(cls_dec, ast.Name):
        return cls_dec.id in _SET_SAFE_DECORATORS
    return isinstance(cls_dec, ast.Attribute) and (
        (
            cls_dec.attr in _SET_ACCESSORS
            and isinstance(cls_dec.value, ast.Name)
            and cls_dec.value.id == str_method
        )
        or (
            cls_dec.attr in _SET_SAFE_DECORATORS
            and isinstance(cls_dec.value, ast.Name)
            and cls_dec.value.id in _SET_SAFE_MODULES
        )
    )


def _rebinds(cls_fn: ast.FunctionDef | ast.AsyncFunctionDef, str_param: str) -> bool:
    """Return whether the name is bound or deleted by any statement under the def.

    A store or delete, an ``import ... as``, a ``match`` capture, an ``except ... as`` and a
    nested ``def`` or ``class`` of that name, and a ``global`` or ``nonlocal`` declaration of
    it, all count. Nested scopes are included, which can
    only over-charge.

    Parameters
    ----------
    cls_fn : ast.FunctionDef or ast.AsyncFunctionDef
        The def.
    str_param : str
        Its first parameter name.

    Returns
    -------
    bool
        ``True`` when a binding of that name is found.
    """
    return any(
        (isinstance(cls_sub, ast.Global | ast.Nonlocal) and str_param in cls_sub.names)
        or (
            _bound_name(cls_sub) == str_param
            and not (isinstance(cls_sub, ast.Name) and isinstance(cls_sub.ctx, ast.Load))
        )
        for cls_stmt in cls_fn.body
        for cls_sub in ast.walk(cls_stmt)
    )


def _shadows_writer(cls_fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return whether the def rebinds ``setattr`` or ``vars``, or takes either as a parameter.

    Parameters
    ----------
    cls_fn : ast.FunctionDef or ast.AsyncFunctionDef
        The def.

    Returns
    -------
    bool
        ``True`` when a call to either name in the body may not reach the builtin.
    """
    return any(
        isinstance(cls_sub, ast.arg) and cls_sub.arg in {"setattr", "vars"}
        for cls_sub in ast.walk(cls_fn)
    ) or any(_rebinds(cls_fn, str_writer) for str_writer in ("setattr", "vars"))


def _module_shadows_writer(list_nodes: list[ast.stmt]) -> bool:
    """Return whether the module namespace binds ``setattr`` or ``vars`` by any statement.

    A star import counts as a possible binding. An import, ``def``, ``class``, ``except ... as`` or ``match`` capture all count; a plain
    assignment is a ``Name`` the writer scan already charges. Class bodies are not entered, so a
    method named ``vars`` does not shadow the builtin its sibling methods call.

    Parameters
    ----------
    list_nodes : list of ast.stmt
        The module-level statements.

    Returns
    -------
    bool
        ``True`` when a call to either name in a method may not reach the builtin.
    """
    return any(
        _bound_name(cls_sub) in {"setattr", "vars", "*"}
        and not (isinstance(cls_sub, ast.Name) and isinstance(cls_sub.ctx, ast.Load))
        for cls_sub in _scope_nodes(list_nodes)
    ) or _function_shadows_writer(list_nodes)


def _function_shadows_writer(list_nodes: list[ast.stmt]) -> bool:
    """Return whether a ``global`` or any def can rebind ``setattr`` or ``vars``.

    A ``global`` statement rebinds the module name from inside a function, and a def, method
    included, that binds either name locally shadows the builtin for a class nested in it.
    The scan covers the whole file, so it can only over-charge.

    Parameters
    ----------
    list_nodes : list of ast.stmt
        The module-level statements.

    Returns
    -------
    bool
        ``True`` when either route is found anywhere in the tree.
    """
    return any(
        (isinstance(cls_sub, ast.Global) and {"setattr", "vars"} & set(cls_sub.names))
        or (
            isinstance(cls_sub, ast.FunctionDef | ast.AsyncFunctionDef)
            and _shadows_writer(cls_sub)
        )
        for cls_node in list_nodes
        for cls_sub in ast.walk(cls_node)
    )


def _bound_name(cls_node: ast.AST) -> str | None:
    """Return the name a node binds or mentions, whichever node shape carries it.

    Parameters
    ----------
    cls_node : ast.AST
        Any node.

    Returns
    -------
    str or None
        The identifier, the first component of a dotted ``import`` or ``None``.
    """
    if isinstance(cls_node, ast.Name):
        return cls_node.id
    if isinstance(cls_node, ast.alias):
        return cls_node.asname or cls_node.name.split(".")[0]
    if isinstance(cls_node, ast.MatchMapping):
        return cls_node.rest
    str_name = getattr(cls_node, "name", None)
    return str_name if isinstance(str_name, str) else None


def _methods(list_nodes: list[ast.stmt]) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield every def that sits directly in a class body and takes a first parameter.

    Parameters
    ----------
    list_nodes : list of ast.stmt
        The module-level statements.

    Yields
    ------
    ast.FunctionDef or ast.AsyncFunctionDef
        Each method with at least one positional parameter.
    """
    for cls_node in list_nodes:
        for cls_cls in ast.walk(cls_node):
            if isinstance(cls_cls, ast.ClassDef):
                yield from (
                    cls_fn
                    for cls_fn in cls_cls.body
                    if isinstance(cls_fn, ast.FunctionDef | ast.AsyncFunctionDef)
                    and (cls_fn.args.posonlyargs or cls_fn.args.args)
                )


def _pattern_names(cls_sub: ast.AST) -> set[str]:
    """Return the names a ``match`` pattern node captures.

    Parameters
    ----------
    cls_sub : ast.AST
        Any node.

    Returns
    -------
    set of str
        The captured names; empty for a node that is not a capturing pattern.
    """
    if isinstance(cls_sub, ast.MatchAs | ast.MatchStar):
        return {cls_sub.name} if cls_sub.name else set()
    if isinstance(cls_sub, ast.MatchMapping) and cls_sub.rest:
        return {cls_sub.rest}
    return set()


def _bound_names(list_nodes: list[ast.stmt]) -> set[str]:
    """Return every name the statements bind outside a nested def, class or lambda.

    Wider than ``_definitions``: loop and ``with`` targets, tuple unpacking, walrus, ``match``
    captures and ``except ... as`` also count, as does a name a function declares ``global``.
    Names bound inside comprehensions are included, which can only over-charge.

    Parameters
    ----------
    list_nodes : list of ast.stmt
        Statements to read.

    Returns
    -------
    set of str
        The bound names, private ones included.
    """
    set_names = _definitions(list_nodes)
    for cls_cur in _scope_nodes(list_nodes):
        if isinstance(cls_cur, ast.Name) and isinstance(cls_cur.ctx, ast.Store):
            set_names.add(cls_cur.id)
        if isinstance(cls_cur, ast.ExceptHandler) and cls_cur.name:
            set_names.add(cls_cur.name)
        set_names |= _pattern_names(cls_cur)
    for cls_node in list_nodes:
        set_names.update(
            str_g
            for cls_sub in ast.walk(cls_node)
            if isinstance(cls_sub, ast.Global)
            for str_g in cls_sub.names
        )
    return set_names


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
    if "_internal" not in (cls_node.module or "").split("."):
        return _from_import_origin(path_module, cls_node, str_name, set_seen)
    path_target = _import_target(path_module, cls_node)
    if path_target is not None and not _star_provides(path_target, str_name, frozenset()):
        return None
    return _from_import_origin(path_module, cls_node, str_name, set_seen)


def _star_provides(
    path_module: pathlib.Path, str_name: str, set_seen: frozenset[pathlib.Path]
) -> bool:
    """Return whether ``from <module> import *`` would bind ``str_name``.

    The module's own ``__all__`` limits what a star import brings in, and a name it only
    re-exports through a star import of its own counts. A nested star import that cannot be
    resolved, a dynamic namespace write, or an ``__all__`` the gate cannot read as one literal
    list is assumed to provide the name, so the check fails closed.

    Parameters
    ----------
    path_module : pathlib.Path
        The module being star-imported.
    str_name : str
        The name to look for.
    set_seen : frozenset of pathlib.Path
        Modules already visited, so an import cycle terminates.

    Returns
    -------
    bool
        ``True`` when the name may come from this module.
    """
    if path_module in set_seen:
        return False
    list_nodes = list(_module_statements(_parse(path_module).body))
    list_exported = declared_all(path_module)
    if _binds_dynamically(list_nodes):
        return True
    if _extends_all(list_nodes):
        return True
    if list_exported is not None:
        return str_name in list_exported
    if str_name in _bound_names(list_nodes) | _imported_names(list_nodes):
        return True
    set_next = set_seen | {path_module}
    return any(
        (path_target := _import_target(path_module, cls_node)) is None
        or _star_provides(path_target, str_name, set_next)
        for cls_node in list_nodes
        if isinstance(cls_node, ast.ImportFrom)
        and any(cls_alias.name == "*" for cls_alias in cls_node.names)
    )


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
        return f"{'.' * cls_node.level}{cls_node.module}"
    if str_source_name == "_internal":
        return _internal_package_origin(path_module, cls_node)
    path_target = _import_target(path_module, cls_node)
    if path_target is None:
        return None
    return _internal_origin(path_target, str_source_name, set_seen)


def _internal_package_origin(path_module: pathlib.Path, cls_node: ast.ImportFrom) -> str | None:
    """Return the dotted ``_internal`` package a ``from … import _internal`` names, or ``None``.

    The bare relative form (``from . import _internal``) is always first-party. With a module
    named, the import counts only when that module resolves inside this package's tree, so
    ``from pydantic import _internal`` is not charged.

    Parameters
    ----------
    path_module : pathlib.Path
        The module containing the import.
    cls_node : ast.ImportFrom
        The import statement.

    Returns
    -------
    str or None
        The dotted path, with its leading dots for a relative import.
    """
    if not cls_node.module:
        return f"{'.' * cls_node.level}_internal"
    if not cls_node.level and _import_target(path_module, cls_node) is None:
        return None
    return f"{'.' * cls_node.level}{cls_node.module}._internal"


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
