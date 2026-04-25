"""Metaclass combining Protocol's metaclass with TypeChecker for typed protocols."""

from __future__ import annotations

from typing import Protocol

from chassis.typing.type_checker import TypeChecker


_ProtocolMeta = type(Protocol)


class ProtocolTypeCheckerMeta(_ProtocolMeta, TypeChecker):
    """Metaclass for Protocol classes with automatic runtime type checking.

    Combines Python's internal Protocol metaclass (structural subtyping) with
    :class:`~chassis.typing.type_checker.TypeChecker` (argument type validation).

    Use as ``metaclass=ProtocolTypeCheckerMeta`` when defining a Protocol port
    to enforce annotated argument types on direct calls to the stub.  Structural
    implementors that do not explicitly inherit must apply
    :class:`~chassis.typing.type_checker.TypeChecker` or the
    :func:`~chassis.typing.decorators.type_checker` decorator independently.

    Examples
    --------
    >>> from typing import Protocol
    >>> from chassis.typing import ProtocolTypeCheckerMeta
    >>>
    >>> class Storage(Protocol, metaclass=ProtocolTypeCheckerMeta):
    ...     def save(self, record: dict) -> str: ...
    """
