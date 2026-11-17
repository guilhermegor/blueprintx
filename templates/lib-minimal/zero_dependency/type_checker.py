"""Standard-library runtime type checking for plain annotated parameters.

The package ships with no runtime dependencies, so this decorator replaces a third-party
checker. It validates every argument whose annotation is a plain class (``str``, ``int``)
and leaves generic, union and string-forward annotations to mypy. Annotations resolve on
the first call, so a class defined later in the module works and a name imported only under
``TYPE_CHECKING`` skips that one parameter's check instead of failing the import.
"""

from __future__ import annotations

from collections.abc import Callable
import functools
import inspect
import types
from typing import Any, ParamSpec, TypeVar, get_type_hints


_P = ParamSpec("_P")
_R = TypeVar("_R")
_WIDENED = {float: (int, float), complex: (int, float, complex)}


def _accepts(*, cls_expected: type, value: object) -> bool:
    """Return whether ``value`` satisfies a plain-class annotation.

    ``int`` widens to ``float`` and ``complex`` as PEP 484 allows; ``bool`` is rejected where
    ``int`` is annotated, which is stricter than mypy on purpose.

    Parameters
    ----------
    cls_expected : type
        The annotated class.
    value : object
        The argument value.

    Returns
    -------
    bool
        ``True`` when the value is acceptable.
    """
    if cls_expected is int and isinstance(value, bool):
        return False
    return isinstance(value, _WIDENED.get(cls_expected, cls_expected))


def _positional_values(value: object) -> list[object]:
    """Return the elements of a bound ``*args`` tuple.

    Parameters
    ----------
    value : object
        The bound tuple.

    Returns
    -------
    list[object]
        Its elements.
    """
    return list(value)  # type: ignore[call-overload]


def _keyword_values(value: object) -> list[object]:
    """Return the values of a bound ``**kwargs`` dict.

    Parameters
    ----------
    value : object
        The bound dict.

    Returns
    -------
    list[object]
        Its values.
    """
    return list(value.values())  # type: ignore[attr-defined]


def _single_value(value: object) -> list[object]:
    """Wrap a plain bound value so every kind is checked the same way.

    Parameters
    ----------
    value : object
        The bound value.

    Returns
    -------
    list[object]
        A one-element list.
    """
    return [value]


_EXPANDERS: dict[inspect._ParameterKind, Callable[[object], list[object]]] = {
    inspect.Parameter.VAR_POSITIONAL: _positional_values,
    inspect.Parameter.VAR_KEYWORD: _keyword_values,
}


def _plain_class(hint: object) -> type:
    """Return the annotation when it is a plain class, else ``object`` (always satisfied).

    Parameters
    ----------
    hint : object
        A resolved annotation, or ``None`` when the parameter has none.

    Returns
    -------
    type
        The class to check against.
    """
    if isinstance(hint, type) and hint is not Any:
        return hint
    return object


def _check_item(*, str_name: str, cls_expected: type, item: object) -> None:
    """Raise ``TypeError`` when one value violates the annotated class.

    Parameters
    ----------
    str_name : str
        Parameter name.
    cls_expected : type
        The annotated class.
    item : object
        The value to check.

    Returns
    -------
    None
        Nothing; the check either passes or raises.

    Raises
    ------
    TypeError
        If the value is not acceptable for the class.
    """
    if not _accepts(cls_expected=cls_expected, value=item):
        raise TypeError(
            f"parameter {str_name}={item!r} violates type hint "
            f"{cls_expected.__name__}, got {type(item).__name__}"
        )


def _check_argument(
    *, cls_parameter: inspect.Parameter, value: object, dict_hints: dict[str, object]
) -> None:
    """Check one bound argument, element by element for ``*args`` and ``**kwargs``.

    Parameters
    ----------
    cls_parameter : inspect.Parameter
        The parameter the value is bound to.
    value : object
        Argument bound to that parameter.
    dict_hints : dict[str, object]
        Resolved annotations of the decorated function.

    Returns
    -------
    None
        Nothing; the check either passes or raises ``TypeError``.
    """
    cls_expected = _plain_class(dict_hints.get(cls_parameter.name))
    for item in _EXPANDERS.get(cls_parameter.kind, _single_value)(value):
        _check_item(str_name=cls_parameter.name, cls_expected=cls_expected, item=item)


def _check_call(
    *,
    cls_signature: inspect.Signature,
    dict_hints: dict[str, object],
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    """Check every bound argument of one call.

    Parameters
    ----------
    cls_signature : inspect.Signature
        Signature of the decorated function.
    dict_hints : dict[str, object]
        Resolved annotations of the decorated function.
    args : tuple[object, ...]
        Positional arguments of the call.
    kwargs : dict[str, object]
        Keyword arguments of the call.

    Returns
    -------
    None
        Nothing; the check either passes or raises ``TypeError``.
    """
    for str_name, value in cls_signature.bind(*args, **kwargs).arguments.items():
        _check_argument(
            cls_parameter=cls_signature.parameters[str_name],
            value=value,
            dict_hints=dict_hints,
        )


def _annotation_holder() -> None:
    """Provide a code object whose annotations are replaced per parameter."""


def _resolve_one(
    *, fn_target: Callable[_P, _R], str_name: str, annotation: object
) -> dict[str, object]:
    """Resolve a single annotation, or none when its name is unavailable.

    Parameters
    ----------
    fn_target : Callable[_P, _R]
        The decorated function, whose globals resolve the annotation.
    str_name : str
        Parameter name.
    annotation : object
        The raw annotation, usually a string under ``from __future__ import annotations``.

    Returns
    -------
    dict[str, object]
        The resolved annotation keyed by name; empty on ``NameError``.
    """
    dict_globals = getattr(fn_target, "__globals__", {})
    fn_stub = types.FunctionType(_annotation_holder.__code__, dict_globals)
    fn_stub.__annotations__ = {str_name: annotation}
    try:
        return get_type_hints(fn_stub)
    except NameError:
        return {}


def _resolve_each(fn_target: Callable[_P, _R]) -> dict[str, object]:
    """Resolve every annotation separately, dropping only the unresolvable ones.

    Parameters
    ----------
    fn_target : Callable[_P, _R]
        The decorated function.

    Returns
    -------
    dict[str, object]
        The annotations that resolved.
    """
    dict_hints: dict[str, object] = {}
    for str_name, annotation in getattr(fn_target, "__annotations__", {}).items():
        dict_one = _resolve_one(fn_target=fn_target, str_name=str_name, annotation=annotation)
        dict_hints.update(dict_one)
    return dict_hints


def _resolve_hints(fn_target: Callable[_P, _R]) -> dict[str, object]:
    """Resolve the annotations of ``fn_target``, skipping only those with an unavailable name.

    Parameters
    ----------
    fn_target : Callable[_P, _R]
        The decorated function.

    Returns
    -------
    dict[str, object]
        The resolved annotations; one referring to a ``TYPE_CHECKING``-only name is left out
        while every other parameter is still checked.
    """
    try:
        return get_type_hints(fn_target)
    except NameError:
        return _resolve_each(fn_target)


def type_checker(fn_target: Callable[_P, _R]) -> Callable[_P, _R]:
    """Validate the annotated parameters of ``fn_target`` on every call.

    Parameters
    ----------
    fn_target : Callable[_P, _R]
        Function whose plain-class annotated parameters are checked at call time.

    Returns
    -------
    Callable[_P, _R]
        The wrapped function, with its signature and docstring preserved.
    """
    cls_signature = inspect.signature(fn_target)
    fn_hints = functools.cache(lambda: _resolve_hints(fn_target))

    @functools.wraps(fn_target)
    def fn_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        """Check the bound arguments, then call the wrapped function."""
        dict_hints = fn_hints()
        _check_call(cls_signature=cls_signature, dict_hints=dict_hints, args=args, kwargs=kwargs)
        return fn_target(*args, **kwargs)

    return fn_wrapper
