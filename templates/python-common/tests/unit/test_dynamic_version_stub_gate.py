"""Unit tests for the dynamic-version stub gate (offline; no git, no network).

Each case pins one decision: the stub passes, a hand-bump fails, and a project that does not
enable dynamic versioning is ignored whatever its version.
"""

import importlib.util
from pathlib import Path
import sys
import tomllib
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


gate = _load("check_dynamic_version_stub")

STR_DYNAMIC = '[tool.poetry-dynamic-versioning]\nenable = true\nvcs = "git"\n\n'


def _pyproject(str_version: str, *, str_dynamic: str) -> str:
    """Build a minimal ``pyproject.toml`` body.

    Parameters
    ----------
    str_version : str
        Value of ``[tool.poetry] version``.
    str_dynamic : str
        Optional dynamic-versioning section, placed after ``[tool.poetry]``.

    Returns
    -------
    str
        The document text.
    """
    return f'[tool.poetry]\nname = "demo"\nversion = "{str_version}"\n\n{str_dynamic}'


def _run(path_dir: Path, *, str_text: str) -> int:
    """Write ``pyproject.toml`` under ``path_dir`` and run the gate on it.

    Parameters
    ----------
    path_dir : pathlib.Path
        Project root.
    str_text : str
        ``pyproject.toml`` contents.

    Returns
    -------
    int
        The gate's exit code.
    """
    (path_dir / "pyproject.toml").write_text(str_text, encoding="utf-8")
    return gate.main(["--root", str(path_dir)])


@pytest.mark.parametrize(
    ("str_version", "str_dynamic", "int_expected"),
    [
        ("0.0.0", STR_DYNAMIC, 0),
        ("1.0.0", STR_DYNAMIC, 1),
        ("1.0.0", "", 0),
        ("1.0.0", STR_DYNAMIC.replace("true", "false"), 0),
    ],
    ids=["stub-passes", "hand-bump-fails", "static-ignored", "disabled-ignored"],
)
def test_exit_code(
    tmp_path: Path, *, str_version: str, str_dynamic: str, int_expected: int
) -> None:
    """Pin the exit code for the stub, hand-bump and ignored-project cases.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided project root.
    str_version : str
        Value of ``[tool.poetry] version``.
    str_dynamic : str
        Optional dynamic-versioning section.
    int_expected : int
        Expected exit code.
    """
    assert (
        _run(tmp_path, str_text=_pyproject(str_version, str_dynamic=str_dynamic)) == int_expected
    )


def test_finding_names_the_found_version() -> None:
    """A hand-bump finding names the offending version."""
    assert "'1.0.0'" in gate.find_problem(
        tomllib.loads(_pyproject("1.0.0", str_dynamic=STR_DYNAMIC))
    )


def test_missing_version_is_a_finding() -> None:
    """A tag-versioned project with no version at all is still a finding."""
    assert "<missing>" in gate.find_problem(
        tomllib.loads("[tool.poetry]\nname = 'x'\n\n" + STR_DYNAMIC)
    )


def test_missing_pyproject_is_a_noop(tmp_path: Path) -> None:
    """A root with no ``pyproject.toml`` exits 0.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided empty directory.
    """
    assert gate.main(["--root", str(tmp_path)]) == 0


def test_quoted_enable_key_is_still_enabled(tmp_path: Path) -> None:
    """``"enable" = true`` is valid TOML and a hand-bump under it must fail.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided project root.
    """
    str_dynamic = '[tool.poetry-dynamic-versioning]\n"enable" = true\n\n'
    assert _run(tmp_path, str_text=_pyproject("1.0.0", str_dynamic=str_dynamic)) == 1


def test_section_header_inside_multiline_string_is_not_a_section(tmp_path: Path) -> None:
    """A ``[example]`` line inside a ``\"\"\"`` string must not hide the real version.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided project root.
    """
    str_text = (
        '[tool.poetry]\nname = "demo"\ndescription = """\n[example]\n"""\n'
        'version = "0.0.0"\n\n' + STR_DYNAMIC
    )
    assert _run(tmp_path, str_text=str_text) == 0


def test_invalid_toml_is_its_own_error(tmp_path: Path, *, capsys: pytest.CaptureFixture) -> None:
    """Malformed TOML exits 1 with a message naming the parse failure.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided project root.
    capsys : pytest.CaptureFixture
        Captures the gate's output.
    """
    _run(tmp_path, str_text="[tool.poetry\nversion = ")
    assert "invalid TOML" in capsys.readouterr().out


def test_invalid_toml_exits_nonzero(tmp_path: Path) -> None:
    """Malformed TOML is a failure, never a silent pass.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided project root.
    """
    assert _run(tmp_path, str_text="[tool.poetry\nversion = ") == 1


def test_non_table_tool_value_is_a_noop(tmp_path: Path) -> None:
    """``tool = "x"`` is valid TOML with no plugin table; the gate must not crash.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided project root.
    """
    assert _run(tmp_path, str_text='tool = "x"\n') == 0
