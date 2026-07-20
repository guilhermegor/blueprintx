"""Unit tests for the ingestion provenance seam (hash + stamp).

Doubles as the worked example of the seam: a reader hashes the downloaded artifact with
:func:`hash_artifact` inside its workspace, resolves its package version, then stamps the typed
frame with :func:`stamp_provenance` after the contract check.
"""

import hashlib
from pathlib import Path

import pytest

# Bare ``utils.`` prefix (not ``src.utils.``) — like test_logs_emitter/test_retry: a
# beartype-checked function that annotates a param with a class it imports bare must be given an
# instance from that *same* module object. Under pytest's ``pythonpath = . src`` a ``src.utils.``
# import loads a *second* copy of the module with distinct class identities, which beartype
# (correctly) rejects. Importing both names bare keeps stamp_provenance and FileContract on one
# module object.
from utils.provenance import hash_artifact, resolve_package_version, stamp_provenance
from utils.tabular_reader import FileContract


_CONTRACT = FileContract("Example Source", "example_source", ("code", "amount"), ())


def _frame():  # noqa: ANN202 — pandas imported lazily so a pandas-less env still collects
	"""Return a small two-row source frame for stamping.

	Returns
	-------
	pd.DataFrame
		Two rows with the contract's source columns.
	"""
	pd = pytest.importorskip("pandas")
	return pd.DataFrame({"code": ["ABC", "DEF"], "amount": [10, 20]})


def test_hash_artifact_matches_sha256_of_bytes(tmp_path: Path) -> None:
	"""``hash_artifact`` returns the sha256 hex digest of the file's raw bytes."""
	path_file = tmp_path / "artifact.csv"
	bytes_payload = b"code;amount\nABC;10\n"
	path_file.write_bytes(bytes_payload)
	assert hash_artifact(path_file) == hashlib.sha256(bytes_payload).hexdigest()


def test_hash_artifact_missing_file_raises(tmp_path: Path) -> None:
	"""Hashing an absent artifact fails fast (no silent empty digest)."""
	with pytest.raises(FileNotFoundError):
		hash_artifact(tmp_path / "nope.csv")


def test_stamp_provenance_appends_columns_in_output_shape() -> None:
	"""The six provenance columns are appended after the source columns, in contract order."""
	df_stamped = stamp_provenance(_frame(), "https://x/y.csv", _CONTRACT, "deadbeef", "1.2.3")
	assert list(df_stamped.columns) == list(_CONTRACT.output_columns)
	assert _CONTRACT.output_columns == ("code", "amount", *_CONTRACT.PROVENANCE_COLUMNS)


def test_stamp_provenance_values_and_dtypes() -> None:
	"""Text provenance is nullable ``string``; ``updated_at`` is tz-aware UTC; values propagate."""
	df_stamped = stamp_provenance(_frame(), "https://x/y.csv", _CONTRACT, "deadbeef", "1.2.3")
	assert (df_stamped["url"] == "https://x/y.csv").all()
	assert (df_stamped["source_key"] == "example_source").all()
	assert (df_stamped["package_version"] == "1.2.3").all()
	assert (df_stamped["content_hash"] == "deadbeef").all()
	assert str(df_stamped["url"].dtype) == "string"
	assert str(df_stamped["content_hash"].dtype) == "string"
	assert str(df_stamped["updated_at"].dtype) == "datetime64[ns, UTC]"
	assert df_stamped["updated_at"].dt.tz is not None


def test_stamp_provenance_shares_one_run_id_across_rows() -> None:
	"""Every row of one read shares a single ``ingestion_run_id`` (one UUID per stamp call)."""
	df_stamped = stamp_provenance(_frame(), "https://x/y.csv", _CONTRACT, "deadbeef", "1.2.3")
	assert df_stamped["ingestion_run_id"].nunique() == 1


def test_stamp_provenance_generates_a_fresh_run_id_per_call() -> None:
	"""Two reads get distinct run ids (the UUID is generated per call, not module-level)."""
	str_id_a = stamp_provenance(_frame(), "u", _CONTRACT, "h", "v")["ingestion_run_id"].iloc[0]
	str_id_b = stamp_provenance(_frame(), "u", _CONTRACT, "h", "v")["ingestion_run_id"].iloc[0]
	assert str_id_a != str_id_b


def test_stamp_provenance_does_not_mutate_input() -> None:
	"""Stamping returns a new frame; the caller's source frame is untouched."""
	df_source = _frame()
	stamp_provenance(df_source, "https://x/y.csv", _CONTRACT, "deadbeef", "1.2.3")
	assert list(df_source.columns) == ["code", "amount"]


def test_resolve_package_version_missing_distribution_returns_stub() -> None:
	"""An uninstalled distribution resolves to the ``0.0.0`` stub, never raises."""
	assert resolve_package_version("a-distribution-that-is-not-installed-xyz") == "0.0.0"
