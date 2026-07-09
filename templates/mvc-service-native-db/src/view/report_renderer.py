"""View layer: render model output to disk.

The view is output-only — it never touches the database or business logic. It
receives a pandas DataFrame from the controller and writes it somewhere. Add
sibling renderers (JSON, CSV, HTML) following this same shape.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils.typing import TypeChecker


class RenderToExcel(metaclass=TypeChecker):
	"""Write a pandas DataFrame to an ``.xlsx`` file via the openpyxl engine.

	Parameters
	----------
	path_out : pathlib.Path
		Destination ``.xlsx`` path. Parent directories are created on render.
	str_sheet_name : str, optional
		Worksheet name, by default ``"report"``.
	"""

	def __init__(self, path_out: Path, str_sheet_name: str = "report") -> None:
		self.path_out = path_out
		self.str_sheet_name = str_sheet_name

	def render(self, df_report: pd.DataFrame) -> Path:
		"""Write ``df_report`` to the configured ``.xlsx`` path.

		Parameters
		----------
		df_report : pd.DataFrame
			Data to write.

		Returns
		-------
		pathlib.Path
			The path that was written.
		"""
		self.path_out.parent.mkdir(parents=True, exist_ok=True)
		df_report.to_excel(
			self.path_out,
			sheet_name=self.str_sheet_name,
			index=False,
			engine="openpyxl",
		)
		return self.path_out
