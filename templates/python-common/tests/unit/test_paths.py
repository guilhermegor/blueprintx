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


def test_to_absolute_relative_path_anchors_to_our_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CWD-relative path is anchored here, so a foreign process cannot re-anchor it."""
    monkeypatch.chdir(tmp_path)
    path_out = to_absolute(Path("out/report.xlsx"))
    assert path_out.is_absolute()
    assert path_out == (Path.cwd() / "out" / "report.xlsx").resolve()


def test_to_absolute_absolute_path_is_returned_unchanged(tmp_path: Path) -> None:
    """An already-absolute path is handed off verbatim — no resolve(), no symlink rewrite."""
    path_in = tmp_path / "report.xlsx"
    assert to_absolute(path_in) == path_in


def test_to_absolute_anchors_a_path_the_platform_calls_driveless(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pin the Windows half on POSIX CI, exercising ``to_absolute`` and not only the stdlib.

    ``/home/x/out`` is rooted but carries no drive, so Windows anchors it to whichever drive
    the *reading* process sits on, and ``is_absolute()`` reports ``False``. That verdict is the
    branch that must route through ``resolve()``. Asserting only ``PureWindowsPath`` would pin
    the premise while leaving our own function untested — a regression handing the driveless
    input straight back would still pass. So the platform verdict is simulated and the real
    function is called.
    """
    # The premise, on the pure flavour, is that a rooted but driveless path is NOT absolute.
    assert PureWindowsPath("/home/x/out").is_absolute() is False
    assert PureWindowsPath("C:/home/x/out").is_absolute() is True

    # Under that same verdict, to_absolute must anchor the path rather than pass it through.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "is_absolute", lambda _self: False)
    path_out = to_absolute(Path("out/report.xlsx"))
    # os.path.isabs is used here because Path.is_absolute is the thing being simulated.
    assert os.path.isabs(str(path_out))
    assert str(path_out).startswith(str(tmp_path.resolve()))
