"""DataFrame/Series relabelling helpers.

Small, total transformations over pandas objects. ``pandas`` is imported lazily so the
module stays importable in environments that ship the helpers without pandas. Deliberately
decoupled from ``utils.typing`` so it stays portable across the ``chassis.typing`` (DDD) and
``utils.typing`` (MVC) layouts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
	import pandas as pd


def map_with_default(series_value: pd.Series, dict_mapping: dict, default: object) -> pd.Series:
	"""Relabel a Series via a mapping, sending every unmapped value to ``default``.

	A **total** relabel: unlike ``series.map(dict_mapping)`` (which yields ``NaN`` for any
	key not in the mapping, silently leaking unmapped/garbage values downstream), this
	guarantees every output cell is either a mapped value or ``default`` — so an unexpected
	input (a typo, a new category, a sentinel) becomes a visible, controlled value instead
	of a hole. Use it whenever a column must be normalised to a closed set of labels.

	Parameters
	----------
	series_value : pandas.Series
		The column whose values are relabelled.
	dict_mapping : dict
		``{raw_value: label}`` mapping applied to each cell.
	default : Any
		The value assigned to any cell whose raw value is not a key in ``dict_mapping``.

	Returns
	-------
	pandas.Series
		A new Series of mapped values, with ``default`` wherever the input was unmapped.
	"""
	return series_value.map(dict_mapping).where(series_value.isin(dict_mapping), default)
