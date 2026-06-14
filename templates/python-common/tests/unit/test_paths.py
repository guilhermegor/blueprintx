"""Unit tests for OS-independent path resolution."""

from pathlib import Path, PureWindowsPath

from src.utils.paths import ensure_dir, is_windows_path, resolve_path


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
	"""``ensure_dir`` creates the directory (and parents) and returns it.

	Parameters
	----------
	tmp_path : Path
		Pytest temporary directory.
	"""
	path_target = tmp_path / "nested" / "out"
	path_returned = ensure_dir(path_target)
	assert path_returned == path_target
	assert path_target.is_dir()
