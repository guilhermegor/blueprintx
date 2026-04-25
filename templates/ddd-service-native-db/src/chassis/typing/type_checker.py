"""Metaclass that applies runtime type checking to every method in a class."""

from __future__ import annotations

from typing import Any

from chassis.typing.validate import _create_type_checked_method


class TypeChecker(type):
    """Metaclass for automatic runtime type checking of all public methods.

    Apply as ``metaclass=TypeChecker`` to enforce annotated argument types on
    every call, including ``__init__``. Dunder methods (except ``__init__``)
    are left untouched to avoid interfering with Python internals.

    Examples
    --------
    >>> from chassis.typing import TypeChecker
    >>>
    >>> class Calculator(metaclass=TypeChecker):
    ...     def add(self, x: int, y: int) -> int:
    ...         return x + y
    >>>
    >>> Calculator().add(1, "two")  # raises TypeError
    """

    def __new__(
        cls: TypeChecker,
        str_name: str,
        tuple_bases: tuple,
        dict_attrs: dict[str, Any],
    ) -> TypeChecker:
        """Wrap all public methods with type-checking before class creation.

        Parameters
        ----------
        str_name : str
            Name of the class being created.
        tuple_bases : tuple
            Base classes.
        dict_attrs : dict[str, Any]
            Class namespace dictionary.

        Returns
        -------
        TypeChecker
            New class with type-checked methods.
        """
        for str_attr, attr_value in dict_attrs.items():
            if callable(attr_value) and not str_attr.startswith("__"):
                dict_attrs[str_attr] = _create_type_checked_method(attr_value)

        if "__init__" in dict_attrs:
            dict_attrs["__init__"] = _create_type_checked_method(dict_attrs["__init__"])

        return super().__new__(cls, str_name, tuple_bases, dict_attrs)
