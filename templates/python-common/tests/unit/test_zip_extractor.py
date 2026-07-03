"""Unit tests for the zip extraction seam."""

from pathlib import Path
import zipfile

from src.utils.zip_extractor import (
	extract_all,
	extract_all_to_memory,
	extract_member_to_memory,
	extract_members,
	extract_members_to_memory,
	unzip_if_needed,
)


def _make_zip(path_dir: Path) -> Path:
	"""Create a small two-member zip and return its path.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory in which to create the archive.

	Returns
	-------
	pathlib.Path
		Path to the created zip.
	"""
	path_zip = path_dir / "bundle.zip"
	with zipfile.ZipFile(path_zip, "w") as cls_zip:
		cls_zip.writestr("a.txt", "alpha")
		cls_zip.writestr("b.txt", "beta")
	return path_zip


def test_extract_all_writes_every_member(tmp_path: Path) -> None:
	"""Every archive member is written to the destination."""
	path_zip = _make_zip(tmp_path)
	path_dest = tmp_path / "out"
	list_out = extract_all(path_zip, path_dest)
	assert {p.name for p in list_out} == {"a.txt", "b.txt"}
	assert (path_dest / "a.txt").read_text() == "alpha"


def test_extract_members_selects_only_named(tmp_path: Path) -> None:
	"""Only the named members are extracted; absent ones are skipped."""
	path_zip = _make_zip(tmp_path)
	path_dest = tmp_path / "out"
	list_out = extract_members(path_zip, path_dest, ["a.txt", "missing.txt"])
	assert [p.name for p in list_out] == ["a.txt"]


def test_unzip_if_needed_is_idempotent(tmp_path: Path) -> None:
	"""Extraction is skipped when the target already exists or is disabled."""
	path_zip = _make_zip(tmp_path)
	path_target = tmp_path / "out" / "a.txt"
	# First run extracts; second run is a no-op because the target now exists.
	assert unzip_if_needed(path_zip, path_target, bool_enabled=True) is True
	assert unzip_if_needed(path_zip, path_target, bool_enabled=True) is False
	# Disabled never extracts.
	assert unzip_if_needed(path_zip, tmp_path / "other" / "a.txt", bool_enabled=False) is False


def test_extract_all_to_memory_returns_every_member(tmp_path: Path) -> None:
	"""Every file member is returned as bytes, and nothing is written to disk."""
	path_zip = _make_zip(tmp_path)
	dict_out = extract_all_to_memory(path_zip)
	assert dict_out == {"a.txt": b"alpha", "b.txt": b"beta"}
	assert list(tmp_path.iterdir()) == [path_zip]


def test_extract_members_to_memory_selects_only_named(tmp_path: Path) -> None:
	"""Only the named members are returned; absent ones are skipped."""
	path_zip = _make_zip(tmp_path)
	dict_out = extract_members_to_memory(path_zip, ["a.txt", "missing.txt"])
	assert dict_out == {"a.txt": b"alpha"}


def test_extract_member_to_memory_reads_single(tmp_path: Path) -> None:
	"""A single named member is returned as bytes."""
	path_zip = _make_zip(tmp_path)
	assert extract_member_to_memory(path_zip, "b.txt") == b"beta"
