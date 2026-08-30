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
