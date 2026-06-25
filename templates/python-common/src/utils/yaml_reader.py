"""YAML-reading seam over stpstone's parser.

Read YAML config through this one function rather than importing the vendor parser at each
call site, so a change of YAML library is confined here (the project's library-coupling rule).
Accepts a :class:`pathlib.Path` (the rest of the project speaks ``Path``) and returns the
parsed mapping.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from stpstone.utils.parsers.yaml import reading_yaml


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
def read_yaml(path_file: Path) -> dict:
	"""Parse a YAML file into a mapping.

	Parameters
	----------
	path_file : pathlib.Path
		Path to the YAML file.

	Returns
	-------
	dict
		The parsed YAML mapping.
	"""
	return reading_yaml(str(path_file))
