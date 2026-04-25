"""Core type-validation engine: validate_type and its method-wrapping helper."""

from __future__ import annotations

import inspect
from functools import wraps
from typing import (
    Any,
    Callable,
    Literal,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)
from unittest.mock import Mock

try:
    from typing import _TypedDictMeta  # private CPython API; may be absent elsewhere
    _TYPED_DICT_META: type | None = _TypedDictMeta
except AttributeError:
    _TYPED_DICT_META = None


def validate_type(
    value: Any,
    expected_type: type,
    param_name: str,
) -> None:
    """Raise TypeError when *value* does not satisfy *expected_type*.

    Parameters
    ----------
    value : Any
        Value to validate.
    expected_type : type
        Annotation to check against.
    param_name : str
        Parameter name shown in the error message.

    Raises
    ------
    TypeError
        When the value does not match the expected type.
    """
    if expected_type is Any:
        return

    if isinstance(value, Mock):
        return

    # TypedDict: check via __annotations__ + __total__ heuristic
    if (
        isinstance(expected_type, type)
        and hasattr(expected_type, "__annotations__")
        and hasattr(expected_type, "__total__")
    ):
        if not isinstance(value, dict):
            raise TypeError(
                f"{param_name} must be a dict for TypedDict, "
                f"got {type(value).__name__}"
            )
        return

    # TypedDict: fallback via private metaclass API
    if _TYPED_DICT_META is not None:
        try:
            if isinstance(expected_type, type) and issubclass(
                type(expected_type), _TYPED_DICT_META
            ):
                if not isinstance(value, dict):
                    raise TypeError(
                        f"{param_name} must be a dict for TypedDict, "
                        f"got {type(value).__name__}"
                    )
                return
        except (TypeError, AttributeError):
            pass

    # bool is a subclass of int — reject it when int or float is expected
    if isinstance(value, bool) and expected_type in (int, float):
        raise TypeError(
            f"{param_name} must be of type {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )

    # numpy integers satisfy int annotations (no numpy import required)
    if expected_type is int and hasattr(value, "dtype") and value.dtype.kind in ("i", "u"):
        return

    # strict float: only accept float, not int
    if expected_type is float and not isinstance(value, float):
        raise TypeError(
            f"{param_name} must be of type {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )

    origin = get_origin(expected_type)

    if origin is Literal:
        args = get_args(expected_type)
        if value not in args:
            str_allowed = ", ".join(repr(a) for a in args)
            raise TypeError(
                f"{param_name} must be one of: {str_allowed}, got {repr(value)}"
            )
        return

    if origin is Union:
        args = get_args(expected_type)
        for arg in args:
            if arg is type(None) and value is None:
                return
            try:
                validate_type(value, arg, param_name)
                return
            except TypeError:
                continue
        list_type_names = [getattr(a, "__name__", str(a)) for a in args]
        raise TypeError(
            f"{param_name} must be one of types: {', '.join(list_type_names)}, "
            f"got {type(value).__name__}"
        )

    if origin is list:
        if not isinstance(value, list):
            raise TypeError(
                f"{param_name} must be of type list, got {type(value).__name__}"
            )
        element_type = get_args(expected_type)[0] if get_args(expected_type) else Any
        for int_i, elem in enumerate(value):
            if get_origin(element_type) is Callable:
                if not callable(elem):
                    raise TypeError(
                        f"{param_name}[{int_i}] must be callable, "
                        f"got {type(elem).__name__}"
                    )
            else:
                validate_type(elem, element_type, f"{param_name}[{int_i}]")
        return

    if origin is not None:
        if not isinstance(value, origin):
            raise TypeError(
                f"{param_name} must be of type {expected_type}, "
                f"got {type(value).__name__}"
            )
        return

    if isinstance(expected_type, type):
        if not isinstance(value, expected_type):
            raise TypeError(
                f"{param_name} must be of type {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )
        return

    try:
        if not isinstance(value, expected_type):
            raise TypeError(
                f"{param_name} must be of type {expected_type}, "
                f"got {type(value).__name__}"
            )
    except TypeError:
        pass


def _create_type_checked_method(
    original_method: Callable[..., Any],
) -> Callable[..., Any]:
    """Wrap *original_method* so every call validates argument types.

    Parameters
    ----------
    original_method : Callable[..., Any]
        Method to wrap.

    Returns
    -------
    Callable[..., Any]
        Wrapper that validates argument types before delegating.
    """

    @wraps(original_method)
    def wrapper(
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        try:
            dict_hints = get_type_hints(original_method)
        except (NameError, AttributeError):
            return original_method(*args, **kwargs)

        sig = inspect.signature(original_method)
        params = sig.parameters

        int_pos = 0
        for str_param, param in params.items():
            if str_param == "self":
                int_pos += 1
                continue
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                varargs_type = dict_hints.get(str_param, Any)
                varargs_type = (
                    get_args(varargs_type)[0]
                    if get_origin(varargs_type) is list
                    else varargs_type
                )
                while int_pos < len(args):
                    validate_type(args[int_pos], varargs_type, f"{str_param}[{int_pos}]")
                    int_pos += 1
            elif param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                if int_pos < len(args) and str_param in dict_hints:
                    validate_type(args[int_pos], dict_hints[str_param], str_param)
                int_pos += 1

        for str_param, value in kwargs.items():
            if str_param in dict_hints:
                validate_type(value, dict_hints[str_param], str_param)

        return original_method(*args, **kwargs)

    return wrapper
