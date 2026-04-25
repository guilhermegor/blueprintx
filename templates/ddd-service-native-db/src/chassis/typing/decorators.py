"""Function decorator for opt-in per-method runtime type checking."""

from __future__ import annotations

from typing import Any, Callable

from chassis.typing.validate import _create_type_checked_method


def type_checker(func: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap *func* with runtime argument type checking derived from annotations.

    Use this when a class already has a metaclass that prevents using
    :class:`~chassis.typing.type_checker.TypeChecker`, or when you only want
    to enforce types on specific methods rather than an entire class.

    Parameters
    ----------
    func : Callable[..., Any]
        Function or method to wrap.

    Returns
    -------
    Callable[..., Any]
        Wrapped callable that validates argument types on every call.

    Examples
    --------
    >>> from chassis.typing import type_checker
    >>>
    >>> @type_checker
    ... def add(x: int, y: int) -> int:
    ...     return x + y
    >>>
    >>> add(1, "two")  # raises TypeError
    """
    return _create_type_checked_method(func)
