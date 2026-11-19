"""Per-regime schema adapters — re-exported from the ``pure-schema-regimes`` package.

The regime window, registry, bound adapter and spec-gap logic lives in ``pure-schema-regimes``;
this module only keeps the project's ``utils.schema_regimes`` import path stable.
"""

from __future__ import annotations

from pure_schema_regimes import (
    RegimeBoundAdapter,
    RegimeRegistry,
    RegimeWindow,
    SpecGapRegistry,
)


__all__ = [
    "RegimeBoundAdapter",
    "RegimeRegistry",
    "RegimeWindow",
    "SpecGapRegistry",
]
