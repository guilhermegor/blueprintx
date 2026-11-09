"""Guard: the code under test is imported from the tree pytest runs in."""

from pathlib import Path

import pytest

import src as module_src


def is_inside(path_file: Path, path_root: Path) -> bool:
    """Tell whether a file lives under a root directory.

    Parameters
    ----------
    path_file : Path
        File to locate.
    path_root : Path
        Directory it must live under.

    Returns
    -------
    bool
        True when ``path_file`` resolves inside ``path_root``.
    """
    return path_file.resolve().is_relative_to(path_root.resolve())


def test_src_is_imported_from_the_rootdir(pytestconfig: pytest.Config) -> None:
    """Fail when ``src`` resolves to another checkout (e.g. an editable install)."""
    assert all(is_inside(Path(str_dir), pytestconfig.rootpath) for str_dir in module_src.__path__)


def test_is_inside_rejects_a_path_outside_the_root(tmp_path: Path) -> None:
    """Should-fail witness: a file in another tree must be reported as outside."""
    path_root = tmp_path / "worktree"
    path_other = tmp_path / "primary" / "src" / "paths.py"
    assert not is_inside(path_other, path_root)
