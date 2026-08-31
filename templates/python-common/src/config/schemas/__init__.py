"""Structured-payload schemas for the project's external data (config layer).

A schema is **declarative configuration** of a structured (XML/JSON) external payload's
shape — field types, decimal scales, cross-field rules — *not* data access, so schemas live
in ``config`` beside ``config/contracts`` (the tabular sibling) and the rest of the
declarative config (``inputs.yaml``, ``connection_db``).

Convention: **one file per external format** under this package (``example_source.py``, …),
each defining one or more Pydantic v2 ``BaseModel`` classes; this aggregator re-exports them
(plus the shared field kit from ``_fields``) so callers import from one place:
``from config.schemas import ExampleSchema, CnpjStr``.

``ExampleSchema`` is a reference model — copy ``example_source.py`` per real external format
and delete the example once your own schemas exist.
"""

from __future__ import annotations

from config.schemas._fields import CnpjStr, CpfStr
from config.schemas.example_source import ExampleSchema


__all__ = ["CnpjStr", "CpfStr", "ExampleSchema"]
