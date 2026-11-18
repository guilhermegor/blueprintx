"""Standard-library metaclass that applies ``type_checker`` to a class's public methods."""

from __future__ import annotations

from .type_checker import type_checker


@type_checker
def _wrap_function(*, str_attr: str, obj_value: object) -> object:
    """Return ``obj_value`` wrapped in ``type_checker`` when it is a public, undecorated function.

    Dunders, nested classes, properties and already-decorated functions come back unchanged.

    Parameters
    ----------
    str_attr : str
        The attribute name in the class body.
    obj_value : object
        The attribute value.

    Returns
    -------
    object
        The wrapped function, or ``obj_value`` itself.
    """
    if (
        not callable(obj_value)
        or isinstance(obj_value, type)
        or (str_attr.startswith("__") and str_attr.endswith("__"))
        or hasattr(obj_value, "__wrapped__")
    ):
        return obj_value
    return type_checker(obj_value)


@type_checker
def _wrap_attribute(*, str_attr: str, obj_value: object) -> object:
    """Return ``obj_value`` with its underlying function wrapped, keeping the descriptor kind.

    ``staticmethod`` and ``classmethod`` objects are unwrapped to ``__func__``, wrapped, and
    rebuilt as the same descriptor type.

    Parameters
    ----------
    str_attr : str
        The attribute name in the class body.
    obj_value : object
        The attribute value.

    Returns
    -------
    object
        The wrapped attribute, or ``obj_value`` itself.
    """
    if isinstance(obj_value, (staticmethod, classmethod)):
        fn_wrapped = _wrap_function(str_attr=str_attr, obj_value=obj_value.__func__)
        return type(obj_value)(fn_wrapped)  # type: ignore[arg-type]
    return _wrap_function(str_attr=str_attr, obj_value=obj_value)


class TypeChecker(type):
    """Wrap every public, non-dunder method of the class in ``type_checker``.

    Mirrors the third-party-backed ``TypeChecker`` the other BlueprintX tiers ship, so the
    ``check_typing`` gate holds in zero-dependency mode too.
    """

    def __new__(  # noqa: PLR0917 - type.__new__ fixes this positional signature
        mcs, str_name: str, tuple_bases: tuple[type, ...], dict_namespace: dict[str, object]
    ) -> TypeChecker:
        """Build the class with its public methods wrapped.

        Parameters
        ----------
        str_name : str
            The class name.
        tuple_bases : tuple[type, ...]
            The base classes.
        dict_namespace : dict[str, object]
            The class body namespace.

        Returns
        -------
        TypeChecker
            The new class.
        """
        dict_wrapped = {
            str_attr: _wrap_attribute(str_attr=str_attr, obj_value=obj_value)
            for str_attr, obj_value in dict_namespace.items()
        }
        return super().__new__(mcs, str_name, tuple_bases, dict_wrapped)
