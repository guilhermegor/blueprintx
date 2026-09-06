"""Shared Pydantic v2 field types for ``config/schemas/`` models.

The reusable "Annotated type kit": field types every schema model can reach for, so a new
model author never re-implements CNPJ/CPF check-digit arithmetic inline. Each type
**delegates** to the existing ``utils`` seam — this module owns zero validation logic of its
own, only the Pydantic wiring around it. See ``src/config/CLAUDE.md`` for the contracts-vs-
schemas split this package sits inside.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import AfterValidator

from utils.br_identifiers import is_valid_cnpj, is_valid_cpf


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). TYPE_CHECKING stubs the decorator's shape
# locally instead of importing: mypy treats a try/except import as executed code and flags
# the redefinition once actually checked, so this branch can't pick either layout
# (blueprintx#360). Runtime still resolves the real engine via try/except below.
if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    _F = TypeVar("_F", bound=Callable[..., object])

    def type_checker(fn: _F) -> _F:
        """Type-only stub — see src/utils/CLAUDE.md."""
else:
    try:
        from utils.typing import type_checker
    except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
        from chassis.typing import type_checker


@type_checker
def _validate_cnpj(str_value: str) -> str:
    """Raise when ``str_value`` is not a valid CNPJ; otherwise pass it through unchanged.

    Parameters
    ----------
    str_value : str
            Candidate CNPJ, already coerced to ``str`` by the field's base type.

    Returns
    -------
    str
            ``str_value``, once validated.

    Raises
    ------
    ValueError
            When ``utils.br_identifiers.is_valid_cnpj`` rejects ``str_value`` — Pydantic turns
            this into a ``ValidationError`` naming the field.
    """
    if not is_valid_cnpj(str_value):
        raise ValueError(f"invalid CNPJ: {str_value!r}")
    return str_value


@type_checker
def _validate_cpf(str_value: str) -> str:
    """Raise when ``str_value`` is not a valid CPF; otherwise pass it through unchanged.

    Parameters
    ----------
    str_value : str
            Candidate CPF, already coerced to ``str`` by the field's base type.

    Returns
    -------
    str
            ``str_value``, once validated.

    Raises
    ------
    ValueError
            When ``utils.br_identifiers.is_valid_cpf`` rejects ``str_value`` — Pydantic turns
            this into a ``ValidationError`` naming the field.
    """
    if not is_valid_cpf(str_value):
        raise ValueError(f"invalid CPF: {str_value!r}")
    return str_value


CnpjStr = Annotated[str, AfterValidator(_validate_cnpj)]
"""A ``str`` field Pydantic accepts only when ``utils.br_identifiers.is_valid_cnpj`` passes."""

CpfStr = Annotated[str, AfterValidator(_validate_cpf)]
"""The CPF sibling of :data:`CnpjStr`, delegating to ``utils.br_identifiers.is_valid_cpf``."""


__all__ = ["CnpjStr", "CpfStr"]
