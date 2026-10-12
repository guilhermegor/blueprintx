"""Worked example for ``config/schemas/`` — the Pydantic v2 sibling of
``config/contracts/``'s worked example (``test_contract_oracle_example.py``). Copy per real
schema, then delete.

Two witness directions, per ``src/config/CLAUDE.md``'s contracts-vs-schemas split: a payload
violating the schema is rejected with a message naming the field / rule; a valid one passes.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

# Bare ``config.`` prefix (not ``src.config.``) — matches the cross-module test convention
# (see test_contract_oracle_example.py / test_provenance).
from config.schemas import ExampleSchema


_VALID_CNPJ = "11222333000181"  # legacy-numeric, correct check digits


def test_valid_payload_passes_and_quantises_decimal() -> None:
    """A well-formed payload passes and ``valor`` is quantised to 2 decimal places."""
    cls_schema = ExampleSchema(cnpj=_VALID_CNPJ, valor="12.3456", cod_fundo="F1")
    assert cls_schema.valor == Decimal("12.34")


def test_invalid_cnpj_is_rejected_naming_the_field() -> None:
    """An invalid CNPJ is rejected, and the error names the ``cnpj`` field."""
    with pytest.raises(ValidationError, match="cnpj"):
        ExampleSchema(cnpj="00000000000000", valor="1", cod_fundo="F1")


def test_both_fund_references_set_is_rejected() -> None:
    """Setting BOTH ``cod_fundo`` and ``cod_subclasse`` violates the cross-field rule."""
    with pytest.raises(ValidationError, match="exactly one"):
        ExampleSchema(cnpj=_VALID_CNPJ, valor="1", cod_fundo="F1", cod_subclasse="S1")


def test_neither_fund_reference_set_is_rejected() -> None:
    """Setting NEITHER ``cod_fundo`` nor ``cod_subclasse`` violates the cross-field rule."""
    with pytest.raises(ValidationError, match="exactly one"):
        ExampleSchema(cnpj=_VALID_CNPJ, valor="1")


@pytest.mark.parametrize(
    "value",
    [None, "", "   ", "abc", "12,34,56", float("nan"), float("inf"), float("-inf"), "nan", "inf"],
)
def test_unparsable_valor_is_rejected_not_silently_zeroed(value: object) -> None:
    """``valor`` that ``to_decimal`` cannot parse is REJECTED, never coerced to zero.

    The regression this pins: ``to_decimal``'s ``default`` is ``Decimal("0")``, so a malformed
    payload used to validate as a real zero and no downstream reader could tell the two apart.
    """
    with pytest.raises(ValidationError, match="valor"):
        ExampleSchema(cnpj=_VALID_CNPJ, valor=value, cod_fundo="F1")


@pytest.mark.parametrize("value", ["0", "0.00", 0, Decimal("0"), "0,004"])
def test_genuine_zero_valor_is_still_accepted(value: object) -> None:
    """A payload that really reports zero still passes — the other half of the witness.

    Without this direction the rejection above would also be satisfied by a validator that
    rejects every zero, which would be a different bug with the same green test.
    """
    cls_schema = ExampleSchema(cnpj=_VALID_CNPJ, valor=value, cod_fundo="F1")
    assert cls_schema.valor == Decimal("0.00")
