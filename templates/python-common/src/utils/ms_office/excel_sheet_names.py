"""Excel worksheet-name validation — a runtime guard at the write boundary (blueprintx#118).

``openpyxl`` (and Excel itself) truncates or substitutes an invalid sheet name **silently** —
there is no exception to catch — and a tab name is often built from data no test enumerates
(a source key, a reference date). :func:`find_sheet_name_problems` is the guard: call it on
every name **before** it reaches a writer, so a bad name fails the run loudly instead of
landing in the workbook as something else. It never raises — like
:func:`utils.tabular_reader.find_file_problems`, it returns problems for the caller to act on.

Every rule is Excel's own, not ``openpyxl``'s: uniqueness is **case-insensitive** (``DADOS`` and
``Dados`` collide even though ``len(set(names))`` says they don't), every broken rule is
reported rather than only the first, and invisible/non-printable characters are named via
:func:`unicodedata.name` instead of vanishing from the message. The cell-reference rule is
strict about the grammar Excel itself checks, so it also rejects short, legitimate-looking
names such as ``Q1``, ``T1``, ``H2`` — that is Excel's rule, not a false positive here.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
import unicodedata


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


_INT_MAX_LEN = 31
_SET_INVALID_CHARS = frozenset("[]:*?/\\")
# "History" is a reserved worksheet name in every Excel version; matched case-insensitively,
# like every other Excel name comparison.
_SET_RESERVED_NAMES = frozenset({"history"})
# A cell reference: 1-3 letters (a column, up to "XFD") then 1-7 digits (a row, up to
# 1,048,576) — Excel's own grammar, which is why it also flags "Q1"/"T1"/"H2".
_RE_CELL_REFERENCE = re.compile(r"^[A-Za-z]{1,3}[0-9]{1,7}$")
# Unicode categories that print as nothing or as a control action: Cc (control), Cf (format,
# e.g. zero-width space). A sheet name built from scraped/OCR text can carry these invisibly.
_SET_INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf"})


@type_checker
def find_sheet_name_problems(  # complexity-ok: eight independent Excel naming rules
	str_name: str,
) -> list[str]:
	"""Validate one worksheet name against Excel's naming rules; return problems (never raises).

	Parameters
	----------
	str_name : str
		The candidate worksheet name.

	Returns
	-------
	list of str
		One message per broken rule; empty when the name is sound. A blank name short-circuits
		to a single problem, since none of the other rules say anything useful about it.
	"""
	if not str_name:
		return ["Sheet name is blank"]

	list_problems: list[str] = []
	if len(str_name) > _INT_MAX_LEN:
		list_problems.append(
			f"Sheet name {str_name!r} exceeds {_INT_MAX_LEN} characters ({len(str_name)})"
		)
	list_bad_chars = sorted({str_char for str_char in str_name if str_char in _SET_INVALID_CHARS})
	if list_bad_chars:
		list_problems.append(f"Sheet name {str_name!r} has forbidden characters: {list_bad_chars}")
	if str_name != str_name.strip():
		list_problems.append(f"Sheet name {str_name!r} has leading/trailing whitespace")
	if str_name.startswith("'") or str_name.endswith("'"):
		list_problems.append(f"Sheet name {str_name!r} starts or ends with an apostrophe")
	if str_name.casefold() in _SET_RESERVED_NAMES:
		list_problems.append(f"Sheet name {str_name!r} is a reserved Excel name")
	if _RE_CELL_REFERENCE.match(str_name):
		list_problems.append(f"Sheet name {str_name!r} looks like a cell reference")
	list_invisible = [
		unicodedata.name(str_char, f"U+{ord(str_char):04X}")
		for str_char in str_name
		if unicodedata.category(str_char) in _SET_INVISIBLE_CATEGORIES
	]
	if list_invisible:
		list_problems.append(f"Sheet name {str_name!r} has invisible characters: {list_invisible}")
	return list_problems


@type_checker
def find_workbook_sheet_name_problems(list_names: list[str]) -> list[str]:
	"""Validate every proposed sheet name for one workbook, plus cross-name uniqueness.

	Runs :func:`find_sheet_name_problems` on each name, then checks uniqueness
	**case-insensitively** across the whole set — ``"DADOS"`` and ``"Dados"`` collide in Excel
	even though ``len(set(list_names))`` says they do not, so that comparison alone would miss
	the collision this function exists to catch.

	Parameters
	----------
	list_names : list of str
		The proposed sheet names, in the order they would be written.

	Returns
	-------
	list of str
		Every broken rule across every name, followed by any case-insensitive duplicates;
		empty when the whole workbook is sound.
	"""
	list_problems = [
		str_problem
		for str_name in list_names
		for str_problem in find_sheet_name_problems(str_name)
	]
	list_lower = [str_name.casefold() for str_name in list_names]
	list_duplicates = sorted(
		{str_lower for str_lower in list_lower if list_lower.count(str_lower) > 1}
	)
	if list_duplicates:
		list_problems.append(f"Sheet names collide case-insensitively: {list_duplicates}")
	return list_problems
