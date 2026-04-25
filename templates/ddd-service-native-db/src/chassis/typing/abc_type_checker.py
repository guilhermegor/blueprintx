"""Metaclass combining ABCMeta with TypeChecker for typed abstract base classes."""

from __future__ import annotations

from abc import ABCMeta

from chassis.typing.type_checker import TypeChecker


class ABCTypeCheckerMeta(ABCMeta, TypeChecker):
    """Metaclass for abstract base classes with automatic runtime type checking.

    Combines :class:`abc.ABCMeta` (abstract method enforcement) with
    :class:`~chassis.typing.type_checker.TypeChecker` (argument type validation).

    Use as ``metaclass=ABCTypeCheckerMeta`` on any ABC instead of inheriting
    from :class:`abc.ABC` directly.

    Examples
    --------
    >>> from abc import abstractmethod
    >>> from chassis.typing import ABCTypeCheckerMeta
    >>>
    >>> class Storage(metaclass=ABCTypeCheckerMeta):
    ...     @abstractmethod
    ...     def save(self, record: dict) -> str: ...
    """
