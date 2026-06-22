"""YAML-reading seam over stpstone's parser.

Read YAML config through this one function rather than importing the vendor parser at each
call site, so a change of YAML library is confined here (the project's library-coupling rule).
Accepts a :class:`pathlib.Path` (the rest of the project speaks ``Path``) and returns the
parsed mapping. Deliberately decoupled from ``utils.typing`` so it stays portable across the
``chassis.typing`` (DDD) and ``utils.typing`` (MVC) layouts.
"""

from __future__ import annotations

from pathlib import Path

from stpstone.utils.parsers.yaml import reading_yaml


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
