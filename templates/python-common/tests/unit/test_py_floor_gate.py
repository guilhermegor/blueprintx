"""Witness for the Python-floor mypy gate (blueprintx#943).

``mypy.ini`` pins ``python_version`` to the floor declared in ``pyproject.toml``, so a
stdlib name that only exists on a newer interpreter fails locally and not on a CI matrix leg.
"""

import configparser
from pathlib import Path
import re
import tomllib

from mypy import api
import pytest


_PATH_ROOT = Path(__file__).parents[2]
_PATH_MYPY_INI = _PATH_ROOT / "mypy.ini"
_DICT_FIRST_NAME_AFTER_FLOOR = {
    "3.11": "from itertools import batched",
    "3.12": "from typing import ReadOnly",
    "3.13": "from functools import Placeholder",
}


def _import_after(str_floor: str) -> str:
    """Return a fixture import that only exists on interpreters newer than the floor.

    Parameters
    ----------
    str_floor : str
        The declared ``MAJOR.MINOR`` floor.

    Returns
    -------
    str
        An import statement naming a stdlib attribute added after ``str_floor``.
    """
    assert str_floor in _DICT_FIRST_NAME_AFTER_FLOOR, (
        f"no post-floor stdlib name for floor {str_floor}: add one to "
        "_DICT_FIRST_NAME_AFTER_FLOOR (the first name its docs mark 'Added in' the next minor)"
    )
    return _DICT_FIRST_NAME_AFTER_FLOOR[str_floor]


def _mypy_stdout(path_fixture: Path, tmp_path: Path, list_extra: list) -> str:
    """Run mypy with the shipped config on a fixture module.

    Parameters
    ----------
    path_fixture : pathlib.Path
        Module to check.
    tmp_path : pathlib.Path
        Directory for the mypy cache.
    list_extra : list
        Extra mypy arguments, e.g. a ``--python-version`` override.

    Returns
    -------
    str
        mypy's standard output.
    """
    str_stdout, _, _ = api.run(
        [
            "--config-file",
            str(_PATH_MYPY_INI),
            "--cache-dir",
            str(tmp_path / ".mypy_cache"),
            *list_extra,
            str(path_fixture),
        ]
    )
    return str_stdout


def _declared_floor() -> str:
    """Return the ``MAJOR.MINOR`` floor from the ``python`` constraint of ``pyproject.toml``.

    Returns
    -------
    str
        The lower bound of the declared Python constraint.
    """
    dict_toml = tomllib.loads((_PATH_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    str_spec = dict_toml["tool"]["poetry"]["dependencies"]["python"]
    return re.match(r"\D*(\d+\.\d+)", str_spec).group(1)


def test_mypy_python_version_matches_declared_floor() -> None:
    """``mypy.ini`` ``python_version`` must equal the floor in ``pyproject.toml``."""
    cls_parser = configparser.ConfigParser()
    cls_parser.read(_PATH_MYPY_INI, encoding="utf-8")
    assert cls_parser["mypy"]["python_version"] == _declared_floor()


def test_mypy_rejects_post_floor_stdlib_name(tmp_path: Path) -> None:
    """A stdlib name added after the floor must fail under the shipped ``mypy.ini``.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Disposable directory holding the fixture module and the mypy cache.
    """
    path_fixture = tmp_path / "uses_post_floor_name.py"
    path_fixture.write_text(f"{_import_after(_declared_floor())}\n", encoding="utf-8")
    assert "has no attribute" in _mypy_stdout(path_fixture, tmp_path, [])


@pytest.mark.parametrize("str_floor", list(_DICT_FIRST_NAME_AFTER_FLOOR))
def test_each_table_name_is_new_after_its_floor(str_floor: str, tmp_path: Path) -> None:
    """Every table entry must fail on its own floor and resolve one minor later.

    Parameters
    ----------
    str_floor : str
        A floor the table has a fixture import for.
    tmp_path : pathlib.Path
        Disposable directory holding the fixture module and the mypy cache.
    """
    path_fixture = tmp_path / "uses_post_floor_name.py"
    path_fixture.write_text(f"{_import_after(str_floor)}\n", encoding="utf-8")
    str_next = f"3.{int(str_floor.split('.')[1]) + 1}"
    assert "has no attribute" in _mypy_stdout(
        path_fixture, tmp_path, ["--python-version", str_floor]
    )
    assert "Success" in _mypy_stdout(path_fixture, tmp_path, ["--python-version", str_next])


def test_a_floor_without_a_fixture_import_fails_with_a_clear_message() -> None:
    """A floor the table lacks must say what to add, not raise a bare ``KeyError``."""
    with pytest.raises(AssertionError, match="no post-floor stdlib name for floor 3.99"):
        _import_after("3.99")
