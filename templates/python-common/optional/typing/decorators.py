"""Function decorator for opt-in per-function runtime type checking."""

from __future__ import annotations

from collections.abc import Callable
from typing import ParamSpec, TypeVar

from chassis.typing.validate import create_type_checked_method


P = ParamSpec("P")
R = TypeVar("R")


def type_checker(func: Callable[P, R]) -> Callable[P, R]:
    """Wrap ``func`` with runtime argument type checking from its annotations.

    Use on standalone module-level functions, or on a method whose class cannot
    use the :class:`~chassis.typing.type_checker.TypeChecker` metaclass.

    Parameters
    ----------
    func : Callable[P, R]
        Function to wrap.

    Returns
    -------
    Callable[P, R]
        Wrapped callable that validates argument types on every call.

    Examples
    --------
    >>> @type_checker
    ... def add(x: int, y: int) -> int:
    ...     return x + y
    >>> add(1, "two")  # raises TypeError
    """
    return create_type_checked_method(func)
