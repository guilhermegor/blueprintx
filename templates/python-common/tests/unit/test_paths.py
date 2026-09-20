"""Unit tests for OS-independent path resolution."""

from datetime import date
import os
from pathlib import Path, PureWindowsPath
import time

import pytest

from src.utils.paths import (
	copy_into,
	date_tokens,
	ensure_dir,
	is_windows_path,
	resolve_input,
	resolve_path,
	to_absolute,
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
	"""``ensure_dir`` creates the directory (and parents) on disk.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway directory.
	"""
	ensure_dir(tmp_path / "nested" / "out")

	assert (tmp_path / "nested" / "out").is_dir()


def test_ensure_dir_returns_the_directory_it_created(tmp_path: Path) -> None:
	"""Creating it and HANDING IT BACK are two claims (blueprintx#544).

	A helper that created the directory and returned ``None`` would satisfy its sibling
	above and break every caller that chains on the result.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway directory.
	"""
	path_target = tmp_path / "nested" / "out"

	assert ensure_dir(path_target) == path_target


# One reference date, one token map, three documented tokens — the same assertion over
# different keys, which is a parametrize rather than three asserts.
@pytest.mark.parametrize(
	("str_token", "str_value"),
	[("date", "2026-04-30"), ("ym", "202604"), ("month_pt", "abril")],
)
def test_date_tokens_builds_substitution_map(str_token: str, str_value: str) -> None:
	"""``date_tokens`` exposes the documented tokens for a reference date.

	Parameters
	----------
	str_token : str
		The documented token name.
	str_value : str
		Its value for 2026-04-30.
	"""
	assert date_tokens(date(2026, 4, 30))[str_token] == str_value


@pytest.fixture
def path_copied(tmp_path: Path) -> Path:
	"""Copy one stamped file, once, for the two tests that inspect the result.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway directory.

	Returns
	-------
	pathlib.Path
		The destination the copy landed at.
	"""
	path_src = tmp_path / "report.csv"
	path_src.write_text("a;b\n", encoding="utf-8")
	return copy_into(path_src, tmp_path / "archive", "20260430_120000")


def test_copy_into_stamps_the_destination_name(path_copied: Path) -> None:
	"""The stem is suffixed with the stamp, extension untouched.

	Parameters
	----------
	path_copied : pathlib.Path
		The shared copy destination.
	"""
	assert path_copied.name == "report_20260430_120000.csv"


def test_copy_into_copies_the_contents(path_copied: Path) -> None:
	"""Naming the destination correctly is not the same as writing anything to it.

	Split from the name claim (blueprintx#544): a helper that computed the stamped path and
	never copied would pass its sibling above.

	Parameters
	----------
	path_copied : pathlib.Path
		The shared copy destination.
	"""
	assert path_copied.read_text(encoding="utf-8") == "a;b\n"


@pytest.fixture
def path_resolved_input(tmp_path: Path) -> Path | None:
	"""Resolve a ``{dir, filename_pattern}`` spec over two files, once.

	The second file is stamped into the future so "newest match" has a deterministic answer
	rather than depending on filesystem timestamp resolution.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway directory.

	Returns
	-------
	pathlib.Path or None
		Whatever ``resolve_input`` returned.
	"""
	(tmp_path / "data_old.xlsx").write_text("", encoding="utf-8")
	path_new = tmp_path / "data_new.xlsx"
	path_new.write_text("", encoding="utf-8")
	os.utime(path_new, (time.time() + 10, time.time() + 10))
	dict_spec = {"dir": str(tmp_path), "filename_pattern": "data_*.xlsx"}
	return resolve_input(dict_spec, date(2026, 4, 30))


def test_resolve_input_finds_a_match_at_all(path_resolved_input: Path | None) -> None:
	"""``None`` would make both sibling claims below unaskable, so it is its own test.

	Parameters
	----------
	path_resolved_input : pathlib.Path or None
		The shared resolution result.
	"""
	assert path_resolved_input is not None


def test_resolve_input_picks_latest_match(path_resolved_input: Path) -> None:
	"""Of two matching files, the most recently modified one wins.

	Parameters
	----------
	path_resolved_input : pathlib.Path
		The shared resolution result.
	"""
	assert path_resolved_input.name == "data_new.xlsx"


def test_resolve_input_returns_an_absolute_path(path_resolved_input: Path) -> None:
	"""A relative result re-anchors in whichever process reads it next.

	Parameters
	----------
	path_resolved_input : pathlib.Path
		The shared resolution result.
	"""
	assert path_resolved_input.is_absolute()


def test_resolve_input_missing_returns_none(tmp_path: Path) -> None:
	"""A spec that matches nothing resolves to ``None``."""
	spec = {"dir": str(tmp_path), "filename_pattern": "absent_*.xlsx"}
	assert resolve_input(spec, date(2026, 4, 30)) is None


def test_to_absolute_relative_path_anchors_to_our_cwd(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A CWD-relative path is anchored here, so a foreign process cannot re-anchor it.

	⚠️ The companion ``is_absolute()`` assertion was folded in, not dropped
	(blueprintx#544): the right-hand side is a ``resolve()``-d path, so an equal result is
	absolute by construction and a separate test for it could not fail independently.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway directory, used as the anchor.
	monkeypatch : pytest.MonkeyPatch
		Used to move the working directory into it.
	"""
	monkeypatch.chdir(tmp_path)

	assert to_absolute(Path("out/report.xlsx")) == (Path.cwd() / "out" / "report.xlsx").resolve()


def test_to_absolute_absolute_path_is_returned_unchanged(tmp_path: Path) -> None:
	"""An already-absolute path is handed off verbatim — no resolve(), no symlink rewrite."""
	path_in = tmp_path / "report.xlsx"
	assert to_absolute(path_in) == path_in


# ⚠️ THE PREMISE AND THE BEHAVIOUR ARE FOUR SEPARATE CLAIMS, and the file's own reasoning
# says why they must not collapse into one test (blueprintx#544): asserting only the
# PureWindowsPath premise would pin the platform while leaving our own function untested — a
# regression handing the driveless input straight back would still pass. Keeping them as
# separate tests makes that argument mechanical instead of a comment.
#
# `/home/x/out` is rooted but carries no drive, so Windows anchors it to whichever drive the
# READING process sits on, and is_absolute() reports False. That verdict is the branch which
# must route through resolve(); on POSIX CI the verdict is simulated and the real function is
# then called under it.
@pytest.mark.parametrize(
	("str_path", "bool_absolute"),
	[("/home/x/out", False), ("C:/home/x/out", True)],
	ids=["rooted-but-driveless", "drive-qualified"],
)
def test_the_windows_premise_is_that_driveless_is_not_absolute(
	str_path: str, bool_absolute: bool
) -> None:
	"""The platform premise, on the pure flavour — the reason the branch exists at all.

	Parameters
	----------
	str_path : str
		A Windows-flavoured path.
	bool_absolute : bool
		What Windows says about it.
	"""
	assert PureWindowsPath(str_path).is_absolute() is bool_absolute


@pytest.fixture
def path_driveless_anchored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	"""Call ``to_absolute`` once under a simulated "not absolute" platform verdict.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway directory, used as the anchor.
	monkeypatch : pytest.MonkeyPatch
		Moves the working directory and simulates the Windows verdict.

	Returns
	-------
	pathlib.Path
		Whatever ``to_absolute`` produced.
	"""
	monkeypatch.chdir(tmp_path)
	monkeypatch.setattr(Path, "is_absolute", lambda _self: False)
	return to_absolute(Path("out/report.xlsx"))


def test_to_absolute_anchors_a_path_the_platform_calls_driveless(
	path_driveless_anchored: Path,
) -> None:
	"""Under that verdict ``to_absolute`` must anchor the path rather than pass it through.

	``os.path.isabs`` is used here because ``Path.is_absolute`` is the thing being simulated.

	Parameters
	----------
	path_driveless_anchored : pathlib.Path
		The shared result of the simulated call.
	"""
	assert os.path.isabs(str(path_driveless_anchored))


def test_the_anchored_path_lands_under_our_own_cwd(
	path_driveless_anchored: Path, tmp_path: Path
) -> None:
	"""Absolute is not enough — it has to be absolute against OUR working directory.

	Parameters
	----------
	path_driveless_anchored : pathlib.Path
		The shared result of the simulated call.
	tmp_path : pathlib.Path
		The directory the fixture anchored to.
	"""
	assert str(path_driveless_anchored).startswith(str(tmp_path.resolve()))
