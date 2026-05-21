"""Shared pytest fixtures for the unit test suite."""

import pandas as pd
import pytest


@pytest.fixture
def df_sample() -> pd.DataFrame:
	"""Provide a small two-row DataFrame for rendering tests.

	Returns
	-------
	pd.DataFrame
		Sample data with an ``id`` and a ``title`` column.
	"""
	return pd.DataFrame({"id": [1, 2], "title": ["alpha", "beta"]})
