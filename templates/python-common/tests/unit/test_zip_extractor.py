"""Unit tests for the zip extraction seam."""

from pathlib import Path
import zipfile

import pytest

from src.utils.zip_extractor import (
    extract_all,
    extract_all_to_memory,
    extract_member_to_memory,
    extract_members,
    extract_members_to_memory,
    find_member,
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


def test_extract_all_writes_the_member_contents(tmp_path: Path) -> None:
    """A written member holds the archived bytes."""
    path_zip = _make_zip(tmp_path)
    path_dest = tmp_path / "out"
    extract_all(path_zip, path_dest)
    assert (path_dest / "a.txt").read_text() == "alpha"


def test_extract_members_selects_only_named(tmp_path: Path) -> None:
    """Only the named members are extracted; absent ones are skipped."""
    path_zip = _make_zip(tmp_path)
    path_dest = tmp_path / "out"
    list_out = extract_members(path_zip, path_dest, ["a.txt", "missing.txt"])
    assert [p.name for p in list_out] == ["a.txt"]


def test_find_member_selects_exact_name_never_a_prefix(tmp_path: Path) -> None:
    """A member whose name prefixes another is never selected by accident.

    The archive is written so that a ``startswith("lamina_fi_")`` scan would return the
    WRONG member first — which is exactly the silent bug this helper removes.
    """
    path_zip = tmp_path / "lamina.zip"
    with zipfile.ZipFile(path_zip, "w") as cls_zip:
        cls_zip.writestr("lamina_fi_carteira_202601.csv", "carteira")
        cls_zip.writestr("lamina_fi_202601.csv", "principal")
    list_out = extract_all(path_zip, tmp_path / "out")

    assert find_member(list_out, "lamina_fi_202601.csv").read_text() == "principal"


def test_find_member_selects_the_longer_name_when_asked_for_it(tmp_path: Path) -> None:
    """The member with the longer name is found by its own exact name too."""
    path_zip = tmp_path / "lamina.zip"
    with zipfile.ZipFile(path_zip, "w") as cls_zip:
        cls_zip.writestr("lamina_fi_carteira_202601.csv", "carteira")
        cls_zip.writestr("lamina_fi_202601.csv", "principal")
    list_out = extract_all(path_zip, tmp_path / "out")

    assert find_member(list_out, "lamina_fi_carteira_202601.csv").read_text() == "carteira"


def test_find_member_missing_raises_value_error_naming_the_member(tmp_path: Path) -> None:
    """A missing member fails loudly, naming what was wanted."""
    path_zip = _make_zip(tmp_path)
    list_out = extract_all(path_zip, tmp_path / "out")
    with pytest.raises(ValueError, match="not found"):
        find_member(list_out, "absent.csv")


def test_unzip_if_needed_is_idempotent(tmp_path: Path) -> None:
    """Extraction is skipped when the target already exists or is disabled."""
    path_zip = _make_zip(tmp_path)
    path_target = tmp_path / "out" / "a.txt"
    assert unzip_if_needed(path_zip, path_target, bool_enabled=True) is True


def test_unzip_if_needed_is_a_no_op_when_the_target_exists(tmp_path: Path) -> None:
    """The second run is a no-op because the target now exists."""
    path_zip = _make_zip(tmp_path)
    path_target = tmp_path / "out" / "a.txt"
    unzip_if_needed(path_zip, path_target, bool_enabled=True)
    assert unzip_if_needed(path_zip, path_target, bool_enabled=True) is False


def test_unzip_if_needed_never_extracts_when_disabled(tmp_path: Path) -> None:
    """Disabled never extracts."""
    path_zip = _make_zip(tmp_path)
    assert unzip_if_needed(path_zip, tmp_path / "other" / "a.txt", bool_enabled=False) is False


def test_extract_all_to_memory_returns_every_member(tmp_path: Path) -> None:
    """Every file member is returned as bytes, and nothing is written to disk."""
    path_zip = _make_zip(tmp_path)
    dict_out = extract_all_to_memory(path_zip)
    assert dict_out == {"a.txt": b"alpha", "b.txt": b"beta"}


def test_extract_all_to_memory_writes_nothing_to_disk(tmp_path: Path) -> None:
    """In-memory extraction leaves the directory holding only the archive."""
    path_zip = _make_zip(tmp_path)
    extract_all_to_memory(path_zip)
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
