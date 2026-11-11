"""Unit tests for ``bin/lib/missing_deps.py``, the venv pre-flight checker (blueprintx#1076)."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load() -> ModuleType:
    """Load the shipped checker by path so the real file is under test.

    Returns
    -------
    types.ModuleType
        The imported ``missing_deps`` module.
    """
    path_script = Path(__file__).resolve().parents[2] / "bin" / "lib" / "missing_deps.py"
    cls_spec = importlib.util.spec_from_file_location("missing_deps", path_script)
    cls_module = importlib.util.module_from_spec(cls_spec)
    cls_spec.loader.exec_module(cls_module)
    return cls_module


_MODULE = _load()


@pytest.mark.parametrize(
    ("dict_toml", "list_expected"),
    [
        ({"tool": {"poetry": {"dependencies": {"python": "^3.11", "pyyaml": "^6"}}}}, ["pyyaml"]),
        (
            {"tool": {"poetry": {"group": {"dev": {"dependencies": {"ruff": "^0.11"}}}}}},
            ["ruff"],
        ),
        (
            {"tool": {"poetry": {"group": {"docs": {"dependencies": {"mkdocs": "^1"}}}}}},
            ["mkdocs"],
        ),
        (
            {"tool": {"poetry": {"group": {"x": {"optional": True, "dependencies": {"y": "1"}}}}}},
            [],
        ),
        ({"dependency-groups": {"test": ["pytest>=8", {"include-group": "lint"}]}}, ["pytest"]),
        ({"project": {"dependencies": ["  requests>=2"]}}, ["requests"]),
        (
            {
                "project": {"dependencies": ["PyYAML>=6"]},
                "tool": {"poetry": {"dependencies": {"pyyaml": "^6"}}},
            },
            ["pyyaml"],
        ),
        ({"tool": {"poetry": {"dependencies": {"x": {"version": "1", "optional": True}}}}}, []),
        ({"tool": {"poetry": {"dependencies": {"x": {"version": "1", "markers": "a"}}}}}, []),
        ({"tool": {"poetry": {"dependencies": {"x": {"version": "1", "python": ">=3.8"}}}}}, []),
        (
            {"tool": {"poetry": {"dependencies": {"x": [{"version": "1", "markers": "a"}, "2"]}}}},
            ["x"],
        ),
        (
            {
                "project": {
                    "dependencies": ["requests[socks]>=2", "pywin32; sys_platform=='win32'"]
                }
            },
            ["requests"],
        ),
    ],
    ids=[
        "main-skips-python",
        "dev-group-read",
        "docs-group-required",
        "optional-group-skipped",
        "pep735-strings-kept-includes-dropped",
        "pep621-leading-whitespace-kept",
        "declared-twice-reported-once",
        "optional-skipped",
        "markers-skipped",
        "python-key-skipped",
        "list-with-unconditional-kept",
        "pep621-extras-kept-markers-skipped",
    ],
)
def test_declared_names_selects_unconditional_main_and_dev_deps(
    dict_toml: dict, list_expected: list[str]
) -> None:
    """Only unconditional main/dev dependencies are demanded of the venv."""
    assert _MODULE.declared_names(dict_toml) == list_expected


def test_missing_matches_installed_distributions_case_insensitively() -> None:
    """An installed distribution resolves whatever the case it is declared in."""
    assert _MODULE.missing(["PYTEST", "no-such-distribution-xyz"]) == ["no-such-distribution-xyz"]


def test_main_prints_one_sentinel_line_per_missing_dependency(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The shell reads ``missing: <name>`` lines, so nothing else may look like a name."""
    path_toml = tmp_path / "pyproject.toml"
    path_toml.write_text(
        '[project]\ndependencies = ["no-such-distribution-xyz"]\n', encoding="utf-8"
    )
    _MODULE.main([str(path_toml)])

    assert capsys.readouterr().out == "missing: no-such-distribution-xyz\n"


def test_main_without_a_path_is_a_usage_error() -> None:
    """A missing argument is reported as usage, never an ``IndexError`` traceback."""
    assert _MODULE.main([]) == 2
