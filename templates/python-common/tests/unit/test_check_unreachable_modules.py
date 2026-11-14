"""Unit tests for the unreachable-modules gate (offline; no git, no network).

Every test either proves the gate FIRES on a tree with a dead module, or pins one way a
module counts as reachable that a naive import walk would miss.
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


_BIN = Path(__file__).resolve().parents[2] / "bin"


def _load(str_name: str) -> ModuleType:
    """Load a ``bin/`` script by path (``bin/`` is not a package).

    Parameters
    ----------
    str_name : str
        Module stem under ``bin/``.

    Returns
    -------
    ModuleType
        The imported module.
    """
    cls_spec = importlib.util.spec_from_file_location(str_name, _BIN / f"{str_name}.py")
    cls_module = importlib.util.module_from_spec(cls_spec)
    sys.modules[str_name] = cls_module
    cls_spec.loader.exec_module(cls_module)
    return cls_module


gate = _load("check_unreachable_modules")


def _write(path_root: Path, str_rel: str, str_source: str = "") -> None:
    """Write one file under a project root, creating its directories.

    Parameters
    ----------
    path_root : pathlib.Path
        Project root.
    str_rel : str
        Path relative to the root.
    str_source : str
        File contents.
    """
    path_file = path_root / str_rel
    path_file.parent.mkdir(parents=True, exist_ok=True)
    path_file.write_text(str_source, encoding="utf-8")


def _run(path_root: Path) -> int:
    """Run the gate over a project root.

    Parameters
    ----------
    path_root : pathlib.Path
        Project root.

    Returns
    -------
    int
        The gate's exit code.
    """
    return gate.main(["--root", str(path_root)])


@pytest.fixture
def path_dead_tree(tmp_path: Path) -> Path:
    """Build a package whose ``_dead`` module nothing imports.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.

    Returns
    -------
    pathlib.Path
        The project root.
    """
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/api.py", "import json\n")
    _write(tmp_path, "src/pkg/_dead.py", "import json\n")
    return tmp_path


def test_a_module_no_public_module_reaches_fails_the_gate(path_dead_tree: Path) -> None:
    """A tree with a dead module exits non-zero.

    Parameters
    ----------
    path_dead_tree : pathlib.Path
        A project with one unreachable module.
    """
    assert _run(path_dead_tree) == 1


def test_the_finding_names_the_dead_module(
    path_dead_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The finding names the module, so the reader knows what to delete.

    Parameters
    ----------
    path_dead_tree : pathlib.Path
        A project with one unreachable module.
    capsys : pytest.CaptureFixture[str]
        Output capture.
    """
    _run(path_dead_tree)

    assert "pkg._dead is unreachable" in capsys.readouterr().out


def test_a_module_imported_by_a_public_module_is_reachable(tmp_path: Path) -> None:
    """An absolute import from a public module reaches a private one."""
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/api.py", "from pkg import _impl\n")
    _write(tmp_path, "src/pkg/_impl.py")

    assert _run(tmp_path) == 0


def test_a_relative_import_is_resolved(tmp_path: Path) -> None:
    """``from ._impl import x`` reaches the sibling private module."""
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/api.py", "from ._impl import value\n")
    _write(tmp_path, "src/pkg/_impl.py", "value = 1\n")

    assert _run(tmp_path) == 0


def test_a_parent_relative_import_is_resolved(tmp_path: Path) -> None:
    """``from .. import x`` climbs one package and reaches a private module there."""
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/sub/__init__.py")
    _write(tmp_path, "src/pkg/sub/api.py", "from .. import _impl\n")
    _write(tmp_path, "src/pkg/_impl.py")

    assert _run(tmp_path) == 0


def test_a_reached_module_reaches_its_parent_package_init(tmp_path: Path) -> None:
    """Importing ``pkg._deep.mod`` also runs ``pkg/_deep/__init__.py``."""
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/api.py", "import pkg._deep.mod\n")
    _write(tmp_path, "src/pkg/_deep/__init__.py")
    _write(tmp_path, "src/pkg/_deep/mod.py")

    assert _run(tmp_path) == 0


def test_two_private_modules_importing_each_other_stay_dead(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A private cluster no public module enters is reported in full.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture[str]
        Output capture.
    """
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/_a.py", "from pkg import _b\n")
    _write(tmp_path, "src/pkg/_b.py", "from pkg import _a\n")

    _run(tmp_path)

    assert "2 finding(s)" in capsys.readouterr().out


def test_an_allowlisted_module_with_a_reason_passes(path_dead_tree: Path) -> None:
    """A dead module is accepted when the allowlist gives a reason.

    Parameters
    ----------
    path_dead_tree : pathlib.Path
        A project with one unreachable module.
    """
    _write(path_dead_tree, ".unreachable-modules.txt", "pkg._dead | loaded by entry point\n")

    assert _run(path_dead_tree) == 0


def test_an_allowlist_entry_without_a_reason_fails(path_dead_tree: Path) -> None:
    """An entry with no written reason is itself a finding.

    Parameters
    ----------
    path_dead_tree : pathlib.Path
        A project with one unreachable module.
    """
    _write(path_dead_tree, ".unreachable-modules.txt", "pkg._dead\n")

    assert _run(path_dead_tree) == 1


def test_a_stale_allowlist_entry_fails(tmp_path: Path) -> None:
    """An entry that matches no unreachable module is reported, so the list cannot rot."""
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, ".unreachable-modules.txt", "pkg._gone | loaded by entry point\n")

    assert _run(tmp_path) == 1


def test_an_allowlist_glob_covers_a_family_of_modules(tmp_path: Path) -> None:
    """A glob entry covers every dead module it matches."""
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/_plugins/__init__.py")
    _write(tmp_path, "src/pkg/_plugins/a.py")
    _write(tmp_path, ".unreachable-modules.txt", "pkg._plugins* | plugins loaded by name\n")

    assert _run(tmp_path) == 0


def test_a_tree_with_no_module_fails_instead_of_passing_vacuously(tmp_path: Path) -> None:
    """Zero modules found is a failure: a gate that checked nothing must not report OK."""
    (tmp_path / "src").mkdir()

    assert _run(tmp_path) == 1


def test_a_syntax_error_fails_the_gate(tmp_path: Path) -> None:
    """A file the gate cannot parse is a finding, not a pass."""
    _write(tmp_path, "src/pkg/__init__.py", "def broken(:\n")

    assert _run(tmp_path) == 1
