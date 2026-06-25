"""DataFrame/Series relabelling helpers.

Small, total transformations over pandas objects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). mypy reads the single TYPE_CHECKING
# import (no redefinition); at runtime the try/except picks whichever layout shipped.
if TYPE_CHECKING:
	from utils.typing import type_checker
else:
	try:
		from utils.typing import type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from chassis.typing import type_checker


@type_checker
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
