"""Unit tests for the raw-artifact workspace seam."""

from pathlib import Path

import pytest

from src.utils.raw_workspace import raw_workspace


def test_raw_workspace_scratch_yields_existing_directory() -> None:
	"""The scratch branch yields a directory that already exists."""
	with raw_workspace() as path_dir:
		assert path_dir.is_dir()


def test_raw_workspace_scratch_leaves_no_residue() -> None:
	"""The scratch branch destroys the directory (and its contents) on exit."""
	# The acceptance criterion of the scratch branch is what is NOT on disk afterwards, so
	# the assertion has to run outside the block — asserting inside it proves nothing.
	with raw_workspace(None) as path_dir:
		(path_dir / "artifact.csv").write_bytes(b"col\n1\n")
		path_seen = path_dir
	assert not path_seen.exists()


def test_raw_workspace_bronze_keeps_the_artifact_byte_for_byte(tmp_path: Path) -> None:
	"""The bronze branch preserves the written bytes exactly."""
	bytes_payload = b"col;value\n\xc3\xa1;1\n"  # non-ASCII: a re-encode would change length
	path_bronze = tmp_path / "bronze" / "2026-08-17"
	with raw_workspace(path_bronze) as path_dir:
		(path_dir / "artifact.csv").write_bytes(bytes_payload)
	assert path_bronze.is_dir()
	assert (path_bronze / "artifact.csv").read_bytes() == bytes_payload


def test_raw_workspace_bronze_creates_missing_parents(tmp_path: Path) -> None:
	"""The bronze branch creates the whole tree, not just the leaf."""
	# The caller names a leaf inside a tree the archiver has not built yet; assuming the
	# parent exists is how a bronze write dies on the first run of a new dated folder.
	path_bronze = tmp_path / "a" / "b" / "c"
	with raw_workspace(path_bronze) as path_dir:
		assert path_dir == path_bronze
	assert path_bronze.is_dir()


def test_raw_workspace_bronze_accepts_an_existing_directory(tmp_path: Path) -> None:
	"""Re-entering an existing bronze directory keeps what is already there."""
	path_bronze = tmp_path / "already"
	path_bronze.mkdir()
	(path_bronze / "earlier.txt").write_text("kept")
	with raw_workspace(path_bronze):
		pass
	assert (path_bronze / "earlier.txt").read_text() == "kept"


def test_raw_workspace_rejects_a_non_path_destination(tmp_path: Path) -> None:
	"""A string destination is rejected at the seam, not deep inside a reader."""
	# The runtime checker is the guard against a caller passing the string form; without it
	# `str.mkdir` fails much later, inside whatever the reader was doing.
	with pytest.raises(TypeError), raw_workspace(str(tmp_path)):  # type: ignore[arg-type]
		pass
