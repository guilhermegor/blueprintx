"""Witness for the Python-floor mypy gate (blueprintx#943).

``mypy.ini`` pins ``python_version`` to the floor declared in ``pyproject.toml``, so a
stdlib name that only exists on a newer interpreter fails locally and not on a CI matrix leg.
"""

import configparser
from pathlib import Path
import re
import tomllib

from mypy import api


_PATH_ROOT = Path(__file__).parents[2]
_PATH_MYPY_INI = _PATH_ROOT / "mypy.ini"


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
    """An ``itertools.batched`` import (3.12+) must fail under the shipped ``mypy.ini``.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Disposable directory holding the fixture module and the mypy cache.
    """
    path_fixture = tmp_path / "uses_batched.py"
    path_fixture.write_text("from itertools import batched\n\nprint(batched)\n", encoding="utf-8")
    str_stdout, _, _ = api.run(
        [
            "--config-file",
            str(_PATH_MYPY_INI),
            "--cache-dir",
            str(tmp_path / ".mypy_cache"),
            str(path_fixture),
        ]
    )
    assert "has no attribute" in str_stdout
