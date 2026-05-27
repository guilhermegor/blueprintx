"""Storage handler factory for schema-less backends."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

from chassis.db.domain.ports import DatabaseHandler
from chassis.db_wschema.infrastructure import (
	CSVDatabaseHandler,
	JSONDatabaseHandler,
	JoblibHandler,
)


def build_storage_handler() -> DatabaseHandler:
	"""Build a schema-less storage handler based on environment configuration.

	Returns
	-------
	DatabaseHandler
		Configured backend handler ready for CRUD operations.

	Raises
	------
	ValueError
		If ``STORAGE_BACKEND`` does not match a supported backend.

	Notes
	-----
	Reads ``STORAGE_BACKEND`` (separate from ``DB_BACKEND``) to pick the backend.
	Supported values: ``json``, ``csv``, ``joblib``.
	Uses ``DATA_DIR`` as the base directory for all backends.
	Set ``JOBLIB_SECRET_KEY`` to enable HMAC tamper-detection for joblib artifacts.
	"""
	load_dotenv()
	str_backend = os.getenv("STORAGE_BACKEND", "json").lower()
	path_data_dir = Path(os.getenv("DATA_DIR", "./data"))
	path_data_dir.mkdir(parents=True, exist_ok=True)
	bytes_secret = os.getenv("JOBLIB_SECRET_KEY", "").encode() or None

	dict_builders: dict[str, Callable[[], DatabaseHandler]] = {
		"json": lambda: JSONDatabaseHandler(path_data_dir / os.getenv("DB_FILE_JSON", "records.json")),
		"csv": lambda: CSVDatabaseHandler(path_data_dir / os.getenv("DB_FILE_CSV", "records.csv")),
		"joblib": lambda: JoblibHandler(
			path_data_dir / os.getenv("JOBLIB_DIR", "artifacts"),
			secret_key=bytes_secret,
		),
	}

	if str_backend not in dict_builders:
		str_supported = ", ".join(dict_builders)
		raise ValueError(f"Unsupported STORAGE_BACKEND {str_backend!r}. Supported: {str_supported}")
	return dict_builders[str_backend]()
