"""Label enrichment — load the label map and merge it into a report.

Business logic for the enrichment phase, kept out of ``controller/_pipeline.py``: the
orchestrator sequences phases and owns the DEGRADED result, this class owns *what
enrichment means* (blueprintx#151).

⚠️ This class raises. It does not degrade, and that split is deliberate — a collaborator
that swallowed its own failures would give the orchestrator nothing to route, and the
documented degradation would stop being reachable from every failure mode, which is the
exact defect #151 exists to close.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from utils.typing import TypeChecker


class LabelEnricher(metaclass=TypeChecker):
	"""Merge a JSON label map into a report, keyed by ``id``.

	Parameters
	----------
	path_labels : pathlib.Path
		The JSON file mapping a stringified ``id`` to its label.
	"""

	def __init__(self, path_labels: Path) -> None:
		self.path_labels = path_labels

	def enrich(self, df_report: pd.DataFrame) -> pd.DataFrame:
		"""Return ``df_report`` with a ``label`` column merged in.

		Parameters
		----------
		df_report : pandas.DataFrame
			The already-fetched report. Never re-read here.

		Returns
		-------
		pandas.DataFrame
			A copy of ``df_report`` carrying the ``label`` column.

		Raises
		------
		OSError
			The label file cannot be opened or read.
		json.JSONDecodeError
			The label file is not valid JSON.
		KeyError
			``df_report`` has no ``id`` column to key on.
		"""
		dict_labels = self._load_labels()
		df_enriched = df_report.copy()
		df_enriched["label"] = df_enriched["id"].astype(str).map(dict_labels)
		return df_enriched

	def _load_labels(self) -> dict:
		"""Read the label map from disk.

		Returns
		-------
		dict
			The parsed label map.
		"""
		with self.path_labels.open(encoding="utf-8") as file_labels:
			return json.load(file_labels)
