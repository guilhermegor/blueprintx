"""Read SQL text from the engine directory the configured backend selects.

The thin caller for :func:`utils.queries.load_query`: it supplies the two things only this
project knows — where ``config/queries`` lives, and which engine is active — and keeps the
resolution rule itself pure and shared.

Config owns SQL **text**; the model owns its **execution**. This module stays on the text
side of that border: it opens no connection and runs no statement.
"""

from __future__ import annotations

from pathlib import Path

from config.connection_db import active_backend
from utils.queries import load_query as _load_query_from
from utils.typing import type_checker


# Anchored to this module, never to the working directory — a pipeline launched from cron,
# a VS Code task or a different drive must resolve the same queries as one launched from the
# project root.
_PATH_QUERIES_ROOT = Path(__file__).resolve().parent / "queries"


@type_checker
def load_query(str_filename: str) -> str:
	"""Return the SQL text filed for the active engine.

	Parameters
	----------
	str_filename : str
		Bare query filename, e.g. ``example_entity__select_active.sql``. Never spell the
		engine here — it is derived from ``DB_BACKEND``, which is the whole point.

	Returns
	-------
	str
		The SQL text.

	Raises
	------
	FileNotFoundError
		If no query of that name is filed for the active engine. The message names the
		engines that do carry it, so a misconfigured ``DB_BACKEND`` and a misspelled
		filename do not read identically.
	"""
	return _load_query_from(str_filename, active_backend(), _PATH_QUERIES_ROOT)
