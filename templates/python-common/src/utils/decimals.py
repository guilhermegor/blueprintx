"""Decimal helpers for precise numeric fields.

Money, percentages and measurements must never round-trip through ``float`` —
IEEE-754 cannot represent most decimal fractions exactly and the error
accumulates silently across thousands of rows. Build every precise value here as
a :class:`~decimal.Decimal` from its string form and quantise it to the number of
decimal places the domain mandates.

The default rounding is ``ROUND_DOWN`` (truncation): deterministic, never inflates
a value, and free of the directional bias that compounds when summing many rows.
Pass ``rounding`` explicitly when the domain demands a different mode — e.g.
``ROUND_HALF_UP`` for tax or regulatory reporting.

This is the ONLY place the truncation rule is implemented. A caller that needs a
default-on-bad-input contract (a bulk import, a report) uses :func:`to_decimal`; a
caller that needs a raise-on-bad-input contract (a Pydantic ``BeforeValidator``,
where bad input must surface as a validation error rather than launder into a
fallback) uses :func:`to_decimal_strict`, which delegates to :func:`to_decimal`
rather than re-deriving the quantisation.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal, InvalidOperation
import functools
from typing import TYPE_CHECKING

import pandas as pd


if TYPE_CHECKING:
    from utils.typing import type_checker
else:
    try:
        from utils.typing import type_checker
    except ModuleNotFoundError:
        from chassis.typing import type_checker


_DEFAULT_ROUNDING = ROUND_DOWN

NumericLike = str | int | float | bool | Decimal | None


@type_checker
def to_decimal(
    value: NumericLike,
    int_places: int,
    default: Decimal = Decimal("0"),
    rounding: str = _DEFAULT_ROUNDING,
) -> Decimal:
    """Coerce ``value`` to a quantised :class:`~decimal.Decimal`.

    Parameters
    ----------
    value : NumericLike
        Raw value. Strings may carry Brazilian formatting (``.`` thousands
        separator and ``,`` decimal separator); both are normalised. ``None``,
        empty strings, unparsable values and **non-finite** results (``NaN``/``±Inf``,
        including the strings ``"nan"``/``"inf"``) fall back to ``default``.
    int_places : int
        Number of decimal places to quantise to (non-negative).
    default : Decimal, optional
        Value returned when ``value`` is missing or unparsable, by default
        ``Decimal("0")``. ⚠️ Also returned when the quantise itself overflows the
        caller's ``decimal`` context precision — a finite, parsable value can hit
        that, and this function never raises a decimal exception.
    rounding : str, optional
        A :mod:`decimal` rounding mode (e.g. ``ROUND_DOWN``, ``ROUND_HALF_UP``);
        by default ``ROUND_DOWN`` (truncation).

    Returns
    -------
    Decimal
        ``value`` quantised to ``int_places`` decimal places using ``rounding``.

    Raises
    ------
    ValueError
        If ``int_places`` is negative.
    """
    if int_places < 0:
        raise ValueError("int_places must be non-negative")
    return _quantise(_parse(value, default), int_places, default, rounding)


@type_checker
def to_decimal_strict(
    value: NumericLike,
    int_places: int,
    rounding: str = _DEFAULT_ROUNDING,
) -> Decimal:
    """Coerce ``value`` to a quantised Decimal, raising instead of defaulting.

    The validator-friendly sibling of :func:`to_decimal`. A Pydantic
    ``BeforeValidator`` must surface bad input as a validation error, not launder
    it into a fallback value the way ``to_decimal``'s ``default`` does — so this
    rejects ``None`` and unparsable input with ``ValueError``. It delegates every
    parse and quantise step to :func:`to_decimal` (passing a sentinel ``NaN``
    default that is never returned to the caller), so there remains exactly one
    truncation implementation for both call sites to share.

    Parameters
    ----------
    value : NumericLike
        Raw value. See :func:`to_decimal` for the accepted shapes; unlike that
        function, ``None`` is rejected here rather than defaulted.
    int_places : int
        Number of decimal places to quantise to (non-negative).
    rounding : str, optional
        A :mod:`decimal` rounding mode (e.g. ``ROUND_DOWN``, ``ROUND_HALF_UP``);
        by default ``ROUND_DOWN`` (truncation), matching :func:`to_decimal`.

    Returns
    -------
    Decimal
        ``value`` quantised to ``int_places`` decimal places using ``rounding``.

    Raises
    ------
    ValueError
        If ``int_places`` is negative, if ``value`` is ``None`` or cannot be parsed
        as a finite decimal number, or if quantising it overflows the caller's
        ``decimal`` context precision.
    """
    cls_sentinel = Decimal("NaN")
    cls_result = to_decimal(value, int_places, default=cls_sentinel, rounding=rounding)
    if cls_result.is_nan():
        raise ValueError(f"cannot coerce {value!r} to Decimal")
    return cls_result


@type_checker
def _quantise(cls_raw: Decimal, int_places: int, default: Decimal, rounding: str) -> Decimal:
    """Quantise ``cls_raw``, falling back to ``default`` when the context is too narrow.

    Parameters
    ----------
    cls_raw : Decimal
        The already-parsed, unquantised value.
    int_places : int
        Number of decimal places to quantise to.
    default : Decimal
        Returned when the quantise overflows the active context precision.
    rounding : str
        A :mod:`decimal` rounding mode.

    Returns
    -------
    Decimal
        ``cls_raw`` quantised, or ``default``.

    Notes
    -----
    ``quantize`` raises on a finite value when the RESULT would exceed
    ``decimal.getcontext().prec`` — a property of the caller's context, not of the
    value, so the parse step cannot anticipate it.
    """
    try:
        return cls_raw.quantize(Decimal(1).scaleb(-int_places), rounding=rounding)
    except InvalidOperation:
        return default


@type_checker
def _parse(value: NumericLike, default: Decimal) -> Decimal:
    """Parse ``value`` into an unquantised Decimal, falling back to ``default``.

    Parameters
    ----------
    value : NumericLike
        Raw value to parse.
    default : Decimal
        Fallback for missing, unparsable, or non-finite (``NaN``/``±Inf``) input.

    Returns
    -------
    Decimal
        The parsed value, or ``default``.
    """
    return _parse_by_type(value, default)


@functools.singledispatch
@type_checker
def _parse_by_type(value: object, default: Decimal) -> Decimal:
    """Parse anything not handled by a registered type: normalise as text, else ``default``.

    Parameters
    ----------
    value : object
        Raw value to parse; stringified and normalised.
    default : Decimal
        Fallback for unparsable or non-finite input.

    Returns
    -------
    Decimal
        The parsed value, or ``default``.
    """
    str_clean = _normalise_br_number(str(value))
    try:
        return _finite_or(Decimal(str_clean), default)
    except InvalidOperation:
        return default


@_parse_by_type.register
@type_checker
def _parse_none(value: None, default: Decimal) -> Decimal:
    """Map a missing value to ``default``.

    Parameters
    ----------
    value : None
        The missing value.
    default : Decimal
        The fallback.

    Returns
    -------
    Decimal
        ``default``.
    """
    return default


@_parse_by_type.register
@type_checker
def _parse_decimal(value: Decimal, default: Decimal) -> Decimal:
    """Pass a Decimal through, mapping a non-finite one (NaN/Infinity) to ``default``.

    Parameters
    ----------
    value : Decimal
        The value to check.
    default : Decimal
        The fallback for a non-finite value.

    Returns
    -------
    Decimal
        ``value`` when finite, else ``default``.
    """
    return _finite_or(value, default)


@_parse_by_type.register
@type_checker
def _parse_bool(value: bool, default: Decimal) -> Decimal:
    """Reject a bool so ``True``/``False`` never become 1/0.

    ``bool`` is a subclass of ``int``; without its own handler it would inherit the int one.

    Parameters
    ----------
    value : bool
        The rejected value.
    default : Decimal
        The fallback.

    Returns
    -------
    Decimal
        ``default``.
    """
    return default


@_parse_by_type.register
@type_checker
def _parse_int(value: int, default: Decimal) -> Decimal:
    """Convert an int, which is always finite — no guard needed.

    Parameters
    ----------
    value : int
        The value to convert.
    default : Decimal
        Unused; present to satisfy the dispatch signature.

    Returns
    -------
    Decimal
        The converted value.
    """
    return Decimal(value)


@_parse_by_type.register
@type_checker
def _parse_float(value: float, default: Decimal) -> Decimal:
    """Convert a float via ``repr`` so the shortest round-tripping decimal is used.

    The full binary expansion would otherwise leak into the result. A float NaN/Inf maps
    to ``default``.

    Parameters
    ----------
    value : float
        The value to convert.
    default : Decimal
        The fallback for a non-finite value.

    Returns
    -------
    Decimal
        The converted value, or ``default``.
    """
    return _finite_or(Decimal(repr(value)), default)


@type_checker
def _finite_or(cls_value: Decimal, default: Decimal) -> Decimal:
    """Return ``cls_value`` when it is finite, else ``default``.

    Centralises the "non-finite is unusable" rule: a ``NaN`` or ``±Inf`` (from a float,
    a passed-in ``Decimal('NaN')``, or the string ``"nan"``/``"inf"`` which parses
    successfully) is semantically "missing", which is exactly what ``default`` is for.
    A leaked non-finite Decimal otherwise detonates downstream (``Decimal('NaN') > x``
    raises :class:`decimal.InvalidOperation`).

    Parameters
    ----------
    cls_value : Decimal
        The candidate parsed value.
    default : Decimal
        Fallback returned when ``cls_value`` is not finite.

    Returns
    -------
    Decimal
        ``cls_value`` if finite, otherwise ``default``.
    """
    return cls_value if cls_value.is_finite() else default


@type_checker
def _normalise_br_number(str_value: str) -> str:
    """Normalise a Brazilian-formatted numeric string to a Decimal-parseable form.

    Handles ``"2.084.960.022,76"`` -> ``"2084960022.76"`` and trims whitespace.
    A plain ``"1234.56"`` (no comma) is left untouched.

    Parameters
    ----------
    str_value : str
        Raw numeric string.

    Returns
    -------
    str
        A string Decimal can parse, or ``""`` when empty.
    """
    str_stripped = str_value.strip()
    if "," not in str_stripped:
        return str_stripped
    return str_stripped.replace(".", "").replace(",", ".")


@type_checker
def parse_br_number_series(series_value: pd.Series) -> pd.Series:
    """Vectorised parse of a Brazilian-formatted numeric column to ``float``.

    Handles thousands ``.``, decimal ``,`` and parenthesised negatives ``(x)`` ->
    ``-x``; non-numeric cells become ``NaN``. The vectorised sibling of
    :func:`_normalise_br_number` — and it MUST mirror that scalar rule:

    The ``.`` is treated as a **thousands separator only when the cell also carries a
    ``,`` decimal separator** (true BR formatting). A cell with no comma is left
    intact, so a value already read as a ``float`` (``5.0``) or a plain decimal
    string (``"1234.56"``) keeps its decimal point instead of being inflated tenfold
    (``5.0`` -> ``50``). pandas reads count columns as ``float64`` when NaNs are
    present, so an unconditional ``.str.replace(".", "")`` would silently corrupt
    them — the two helpers parsing one format must never diverge.

    ``pandas`` is imported lazily so this module stays importable in environments
    that ship the Decimal helpers without pandas.

    Parameters
    ----------
    series_value : pandas.Series
        The raw string (or mixed) column.

    Returns
    -------
    pandas.Series
        The parsed ``float`` column (``NaN`` where unparsable).
    """
    import pandas as pd

    series_str = series_value.astype(str)
    series_has_comma = series_str.str.contains(",", regex=False)
    series_br = series_str.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    series_clean = (
        series_str.where(~series_has_comma, series_br)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
    )
    return pd.to_numeric(series_clean, errors="coerce")
