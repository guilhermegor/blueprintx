"""Base reader bound to exactly one schema regime.

Part of the per-regime adapter pattern (issue #148). Motivating case (measured, not
invented): a monthly fund-profile series published 106 columns keyed ``CNPJ_FUNDO`` through
period ``202311``, then 107 columns keyed ``TP_FUNDO_CLASSE``/``CNPJ_FUNDO_CLASSE`` from
``202312`` on — the other 105 columns identical, position for position. Deriving one
contract from the other is right about 105 of 106 names and silently wrong about the one
that matters, so each regime gets its own reader, each pinned to its own regime window
rather than to the sibling's.

This module implements only the regime-**selection** half of the pattern: which window a
period belongs to, and refusing one that does not belong to this reader's regime. The actual
per-regime pinned-header fixture and file read live in ``src/config/`` (contracts) and a
concrete ``read()`` implementation — both project-specific, so out of this file's scope.
"""

from __future__ import annotations

from model.regime_registry import RegimeRegistry
from utils.typing import TypeChecker


class RegimeReader(metaclass=TypeChecker):
    """One reader instance bound to exactly one regime.

    Construct it with the regime's name; it refuses any period the registry resolves to a
    *different* regime, naming the one that actually covers it — so a reader for the
    superseded schema can never silently read a period published under the new one, or vice
    versa. A ``None`` period resolves through :meth:`RegimeRegistry.default_period`, so a
    CLOSED regime's no-args default is its own newest covered period, never wall-clock
    "today" (see that method's docstring for why "today" would be the wrong default here —
    sweeping every registered regime with no-args defaults is exactly the caller that
    surfaces the bug, not a targeted test of one reader).

    Parameters
    ----------
    cls_registry : RegimeRegistry
            The registry holding every known regime window, this reader's included.
    str_regime_name : str
            Which regime THIS reader instance is bound to.
    int_period : int | None, optional
            The competency period, ``YYYYMM``; ``None`` resolves via
            :meth:`RegimeRegistry.default_period`.
    """

    def __init__(  # complexity-ok: default + refuse-wrong-regime IS the constructor contract
        self,
        cls_registry: RegimeRegistry,
        str_regime_name: str,
        int_period: int | None = None,
    ) -> None:
        if int_period is None:
            int_period = cls_registry.default_period(str_regime_name)
        cls_window = cls_registry.resolve(int_period)
        if cls_window.str_name != str_regime_name:
            raise ValueError(
                f"Period {int_period} belongs to regime {cls_window.str_name!r}, "
                f"not {str_regime_name!r}."
            )
        self.cls_registry = cls_registry
        self.cls_window = cls_window
        self.int_period = int_period
