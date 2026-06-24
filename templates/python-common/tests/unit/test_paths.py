"""Unit tests for OS-independent path resolution."""

from datetime import date
import os
from pathlib import Path, PureWindowsPath
import time

from src.utils.paths import (
	copy_into,
	date_tokens,
	ensure_dir,
	is_windows_path,
	resolve_input,
	resolve_path,
)


def test_is_windows_path_detects_drive_letter() -> None:
	r"""A ``X:\...`` drive path is recognised as a Windows path."""
	assert is_windows_path("A:\\daily_infos\\in") is True


def test_is_windows_path_detects_unc_share() -> None:
	r"""A ``\\server\share`` UNC path is recognised as a Windows path."""
	assert is_windows_path("\\\\xpdocs\\share") is True


def test_is_windows_path_rejects_posix_path() -> None:
	"""A POSIX path is not a Windows path."""
	assert is_windows_path("/var/data/in") is False


def test_resolve_path_posix_expands_user() -> None:
	"""A ``~``-prefixed POSIX path expands to the user's home."""
	path_resolved = resolve_path("~/data")
	assert path_resolved == Path.home() / "data"


def test_resolve_path_windows_on_posix_parses_parts() -> None:
	r"""A Windows path is parsed via PureWindowsPath even on POSIX hosts."""
	path_resolved = resolve_path("A:\\daily_infos\\in")
	assert path_resolved == Path(PureWindowsPath("A:\\daily_infos\\in"))


def test_ensure_dir_creates_directory(tmp_path: Path) -> None:
	"""``ensure_dir`` creates the directory (and parents) and returns it."""
	path_target = tmp_path / "nested" / "out"
	path_returned = ensure_dir(path_target)
	assert path_returned == path_target
	assert path_target.is_dir()


def test_date_tokens_builds_substitution_map() -> None:
	"""``date_tokens`` exposes the documented tokens for a reference date."""
	dict_tokens = date_tokens(date(2026, 4, 30))
	assert dict_tokens["date"] == "2026-04-30"
	assert dict_tokens["ym"] == "202604"
	assert dict_tokens["month_pt"] == "abril"


def test_copy_into_stamps_and_copies(tmp_path: Path) -> None:
	"""``copy_into`` copies the file and suffixes the stem with the stamp."""
	path_src = tmp_path / "report.csv"
	path_src.write_text("a;b\n", encoding="utf-8")
	path_dest = copy_into(path_src, tmp_path / "archive", "20260430_120000")
	assert path_dest.name == "report_20260430_120000.csv"
	assert path_dest.read_text(encoding="utf-8") == "a;b\n"


def test_resolve_input_picks_latest_match_absolute(tmp_path: Path) -> None:
	"""A ``{dir, filename_pattern}`` spec resolves to the newest match, made absolute."""
	(tmp_path / "data_old.xlsx").write_text("", encoding="utf-8")
	path_new = tmp_path / "data_new.xlsx"
	path_new.write_text("", encoding="utf-8")
	# Make the second file the most recently modified.
	os.utime(path_new, (time.time() + 10, time.time() + 10))
	spec = {"dir": str(tmp_path), "filename_pattern": "data_*.xlsx"}
	path_resolved = resolve_input(spec, date(2026, 4, 30))
	assert path_resolved is not None
	assert path_resolved.is_absolute()
	assert path_resolved.name == "data_new.xlsx"


def test_resolve_input_missing_returns_none(tmp_path: Path) -> None:
	"""A spec that matches nothing resolves to ``None``."""
	spec = {"dir": str(tmp_path), "filename_pattern": "absent_*.xlsx"}
	assert resolve_input(spec, date(2026, 4, 30)) is None
