"""Brazilian identifier helpers — re-exported from the ``pure-docs-br`` package.

The CNPJ/CPF mask, unmask and validate logic (including the 2026 alphanumeric CNPJ) lives in
``pure-docs-br``; this module only keeps the project's ``utils.br_identifiers`` import path
stable. See ``docs/decision-records.md`` in BlueprintX for the rationale.
"""

from __future__ import annotations

from pure_docs_br import (
    is_valid_cnpj,
    is_valid_cpf,
    mask_cnpj,
    mask_cpf,
    unmask_cnpj,
    unmask_cpf,
)


__all__ = [
    "is_valid_cnpj",
    "is_valid_cpf",
    "mask_cnpj",
    "mask_cpf",
    "unmask_cnpj",
    "unmask_cpf",
]
