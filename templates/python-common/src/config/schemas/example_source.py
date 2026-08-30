"""Reference structured-payload schema — copy this per real external format, then delete
the example.

A ``config/schemas`` model is the **anti-corruption shape** for a structured (XML/JSON)
external payload: it pins field types, decimal scales and cross-field rules to *someone
else's* published format — the typed sibling of ``config/contracts``, which pins the shape
of a *tabular* (CSV/XLSX) source instead. See ``src/config/CLAUDE.md``.

🔴 A schema mirrors a vendor's wire format. Putting it in ``domain/`` couples your domain to
that vendor's format and makes it churn when they publish V5. ``domain/`` holds concepts you
own and can rename freely; ``config/schemas`` holds shapes someone else owns and you must
mirror exactly. The mapping between them is the anti-corruption layer, and it lives in
``infrastructure/`` — never import this module from ``domain/`` (DDD tiers).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, field_validator, model_validator

from config.schemas._fields import CnpjStr
from utils.decimals import to_decimal


class ExampleSchema(BaseModel):
	"""One record of the example external structured payload.

	Parameters
	----------
	cnpj : CnpjStr
		Reporting entity's CNPJ, validated via ``utils.br_identifiers.is_valid_cnpj``.
	valor : Decimal
		Monetary amount, quantised to 2 decimal places via ``utils.decimals.to_decimal`` —
		never re-implemented here.
	cod_fundo : str, optional
		Fund code. The published standard names either a fund or one of its subclasses,
		never both — see :meth:`_check_exactly_one_fund_reference`.
	cod_subclasse : str, optional
		Subclass code. See ``cod_fundo``.

	Field names are **not** type-prefixed on purpose: they mirror the external payload's
	own tag names, which is the entire point of an anti-corruption schema.
	"""

	cnpj: CnpjStr
	valor: Decimal
	cod_fundo: str | None = None
	cod_subclasse: str | None = None

	@field_validator("valor", mode="before")
	@classmethod
	def _quantise_valor(cls, value: object) -> Decimal:
		"""Quantise ``valor`` to 2 decimal places via the shared Decimal helper.

		Parameters
		----------
		value : object
			Raw value as read from the payload.

		Returns
		-------
		Decimal
			``value`` quantised to 2 places, ``ROUND_DOWN`` (``to_decimal``'s default).
		"""
		return to_decimal(value, 2)

	@model_validator(mode="after")
	def _check_exactly_one_fund_reference(self) -> ExampleSchema:
		"""Enforce that exactly one of ``cod_fundo`` / ``cod_subclasse`` is set.

		Mirrors the CVM ``PadrãoXMLInfoDiarioNet`` rule this package is modelled on: a
		record names either a fund or one of its subclasses, never both and never neither.

		Returns
		-------
		ExampleSchema
			``self``, once the invariant is confirmed.

		Raises
		------
		ValueError
			When both or neither of ``cod_fundo`` / ``cod_subclasse`` are set.
		"""
		if (self.cod_fundo is None) == (self.cod_subclasse is None):
			raise ValueError("exactly one of cod_fundo or cod_subclasse must be set")
		return self
