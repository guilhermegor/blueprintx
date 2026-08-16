"""DataFrame construction and relabelling helpers.

Small, total transformations over pandas objects, plus the **construction seam**: the one
place a DataFrame is built from a DB-API cursor.

The construction half exists so a `model/` entity never calls the pandas API. It keeps the
layer's pandas usage to the return ANNOTATION (`-> pd.DataFrame`), which is the vocabulary
the layers agree on, while the calls that actually depend on pandas' surface live here. That
also removes the shaping code every copied entity would otherwise carry, along with its
empty-result edge case.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

import pandas as pd

from utils.dtypes import apply_dtypes


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
def _empty_frame(
	dict_dtypes: dict[str, str], list_date_cols: list[str] | None = None
) -> pd.DataFrame:
	"""Build the zero-row frame both construction seams return when there is nothing to read.

	Carries **every declared column** — those named in ``dict_dtypes`` and those named in
	``list_date_cols`` — and runs the same coercion the populated path runs. Both halves
	matter and both were wrong at some point: dropping the date columns makes an empty result
	structurally different from a populated one, and skipping the coercion makes it
	differently *typed*. Either way a caller that concatenates or renders the result starts
	behaving differently depending on whether rows happened to exist, which is the entire
	reason this branch returns a shaped frame rather than a bare one.

	Parameters
	----------
	dict_dtypes : dict of {str: str}
		Column→dtype mapping declared by the caller.
	list_date_cols : list of str, optional
		Columns coerced to dates. Disjoint from ``dict_dtypes`` (``apply_dtypes`` requires it).

	Returns
	-------
	pandas.DataFrame
		An empty frame holding every declared column, typed.
	"""
	list_columns = list(dict_dtypes) + list(list_date_cols or [])
	return apply_dtypes(
		pd.DataFrame(columns=list_columns),
		dict_dtypes=dict_dtypes,
		list_date_cols=list_date_cols,
	)


@type_checker
def from_cursor(
	cls_cursor: Any,  # noqa: ANN401 — opaque DB-API cursor; any driver's object is valid
	dict_dtypes: dict[str, str],
	list_date_cols: list[str] | None = None,
) -> pd.DataFrame:
	"""Build a typed DataFrame from an executed DB-API cursor.

	The construction seam for the model layer: it takes the cursor the entity already
	executed, reads the column names from ``cursor.description``, fetches the rows, and
	applies the declared dtypes. The caller never touches the pandas API.

	An exhausted or non-returning cursor (``description is None``) yields an **empty frame
	with the declared columns**, not a shapeless one — a caller that concatenates or renders
	the result then behaves identically whether or not there were rows, which a bare empty
	frame does not give you.

	The cursor is **not** closed here: the entity owns it and its lifecycle.

	Parameters
	----------
	cls_cursor : Any
		A DB-API 2.0 cursor on which ``execute`` has already been called.
	dict_dtypes : dict of {str: str}
		Column→dtype mapping enforced via :func:`utils.dtypes.apply_dtypes`.
	list_date_cols : list of str, optional
		Columns coerced to dates, forwarded to :func:`utils.dtypes.apply_dtypes`.

	Returns
	-------
	pandas.DataFrame
		One row per record, every declared column typed.
	"""
	if cls_cursor.description is None:
		return _empty_frame(dict_dtypes, list_date_cols)

	list_cols = [col[0] for col in cls_cursor.description]
	df_records = pd.DataFrame.from_records(cls_cursor.fetchall(), columns=list_cols)
	return apply_dtypes(df_records, dict_dtypes=dict_dtypes, list_date_cols=list_date_cols)


@type_checker
def from_records(
	list_records: Sequence[Mapping[str, Any]],
	dict_dtypes: dict[str, str],
	list_date_cols: list[str] | None = None,
) -> pd.DataFrame:
	"""Build a typed DataFrame from already-materialised row mappings.

	The ORM sibling of :func:`from_cursor`: an entity turns its mapped objects into plain
	dicts (``{"id": row.id, "title": row.title}``) and hands them here, so the model layer
	never calls the pandas API. Keeping the projection in the entity is deliberate — it is the
	only place that knows which attributes belong in the frame.

	Like :func:`from_cursor`, an empty input yields an empty frame carrying the **declared
	columns**, so the result's shape does not depend on whether rows happened to exist.

	Parameters
	----------
	list_records : sequence of mapping
		One mapping per row, keyed by column name.
	dict_dtypes : dict of {str: str}
		Column→dtype mapping enforced via :func:`utils.dtypes.apply_dtypes`.
	list_date_cols : list of str, optional
		Columns coerced to dates, forwarded to :func:`utils.dtypes.apply_dtypes`.

	Returns
	-------
	pandas.DataFrame
		One row per record, every declared column typed.
	"""
	if not list_records:
		return _empty_frame(dict_dtypes, list_date_cols)

	df_records = pd.DataFrame(list(list_records))
	return apply_dtypes(df_records, dict_dtypes=dict_dtypes, list_date_cols=list_date_cols)


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
