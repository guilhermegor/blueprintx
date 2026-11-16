"""Standard-library runtime type checking for plain annotated parameters.

The package ships with no runtime dependencies, so this decorator replaces a third-party
checker. It validates every argument whose annotation is a plain class (``str``, ``int``)
and leaves generic, union and string-forward annotations to mypy.
"""

from __future__ import annotations

from collections.abc import Callable
import functools
import inspect
from typing import ParamSpec, TypeVar, get_type_hints


_P = ParamSpec("_P")
_R = TypeVar("_R")


def _check_argument(*, str_name: str, value: object, dict_hints: dict[str, object]) -> None:
    """Raise ``TypeError`` when a value is not an instance of its plain-class annotation.

    Parameters
    ----------
    str_name : str
        Parameter name.
    value : object
        Argument bound to that parameter.
    dict_hints : dict[str, object]
        Resolved annotations of the decorated function.

    Returns
    -------
    None
        Nothing; the check either passes or raises.

    Raises
    ------
    TypeError
        If the annotation is a plain class and ``value`` is not an instance of it.
    """
    cls_expected = dict_hints.get(str_name)
    if isinstance(cls_expected, type) and not isinstance(value, cls_expected):
        raise TypeError(
            f"parameter {str_name}={value!r} violates type hint {cls_expected.__name__}, "
            f"got {type(value).__name__}"
        )


def _check_arguments(
    *,
    cls_signature: inspect.Signature,
    dict_hints: dict[str, object],
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    """Check every bound argument of one call against the resolved annotations.

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
        _check_argument(str_name=str_name, value=value, dict_hints=dict_hints)


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
    dict_hints = get_type_hints(fn_target)

    @functools.wraps(fn_target)
    def fn_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        """Check the bound arguments, then call the wrapped function."""
        _check_arguments(
            cls_signature=cls_signature, dict_hints=dict_hints, args=args, kwargs=kwargs
        )
        return fn_target(*args, **kwargs)

    return fn_wrapper
