"""Unit tests for the pip-fallback requirement translator (offline; no pip, no network).

**No shipped tier exercises the case these tests exist for**, and that is exactly why they
are here. Every skeleton declares ``[tool.poetry]``, so the equivalence probe that guarded
the heredoc extraction — five tiers x four group selections — could not see a PEP 621
project at all, let alone one declaring *only* ``[project.optional-dependencies]``. That
shape sent the selector down the Poetry path and emitted nothing, and the caller wrote the
nothing to ``requirements-lock.txt`` where it reads as "this project has no dependencies"
(blueprintx#211).

So the fixtures below are hand-built rather than lifted from a tier: the bug lives in the
layouts the repo does not ship, which is the half no amount of running the real thing can
reach.
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


_LIB = Path(__file__).resolve().parents[2] / "bin" / "lib"


def _load() -> ModuleType:
    """Load ``bin/lib/pip_requirements.py`` by path (``bin/lib/`` is not a package).

    Returns
    -------
    ModuleType
        The imported module.
    """
    cls_spec = importlib.util.spec_from_file_location(
        "pip_requirements", _LIB / "pip_requirements.py"
    )
    cls_module = importlib.util.module_from_spec(cls_spec)
    sys.modules["pip_requirements"] = cls_module
    cls_spec.loader.exec_module(cls_module)
    return cls_module


MODULE = _load()


DICT_PEP621_OPTIONAL_ONLY = {
    "project": {
        "name": "optional-only",
        "optional-dependencies": {
            "dev": ["pytest>=8.0", "ruff>=0.6"],
            "docs": ["mkdocs>=1.6"],
        },
    }
}

DICT_PEP621_WITH_MAIN = {
    "project": {
        "name": "both",
        "dependencies": ["httpx>=0.27"],
        "optional-dependencies": {"dev": ["pytest>=8.0"]},
    }
}

DICT_POETRY_WITH_EMPTY_PROJECT_TABLE = {
    "project": {"name": "poetry-project"},
    "tool": {
        "poetry": {
            "dependencies": {"python": "^3.11", "pandas": "^2.2"},
            "group": {"dev": {"dependencies": {"pytest": "^8.0"}}},
        }
    },
}


def test_optional_only_pep621_resolves_its_group() -> None:
    """An optional-only PEP 621 project must resolve through the PEP 621 path."""
    assert MODULE.select_requirements(DICT_PEP621_OPTIONAL_ONLY, list_groups=["dev"]) == [
        "pytest>=8.0",
        "ruff>=0.6",
    ]


def test_optional_only_pep621_with_main_requested_still_resolves_the_group() -> None:
    """Requesting ``main`` on a project without main deps yields the optional group alone."""
    assert MODULE.select_requirements(DICT_PEP621_OPTIONAL_ONLY, list_groups=["main", "dev"]) == [
        "pytest>=8.0",
        "ruff>=0.6",
    ]


def test_main_dependencies_are_omitted_when_main_is_not_requested() -> None:
    """``[project.dependencies]`` belongs to the ``main`` group, not to every request."""
    assert MODULE.select_requirements(DICT_PEP621_WITH_MAIN, list_groups=["dev"]) == [
        "pytest>=8.0"
    ]


def test_main_dependencies_are_included_when_main_is_requested() -> None:
    """The same table IS emitted once ``main`` is among the requested groups."""
    assert MODULE.select_requirements(DICT_PEP621_WITH_MAIN, list_groups=["main", "dev"]) == [
        "httpx>=0.27",
        "pytest>=8.0",
    ]


def test_empty_project_table_falls_through_to_poetry() -> None:
    """A bare ``[project]`` name beside a populated ``[tool.poetry]`` must resolve via Poetry."""
    assert MODULE.select_requirements(
        DICT_POETRY_WITH_EMPTY_PROJECT_TABLE, list_groups=["main"]
    ) == ["pandas>=2.2,<3.0.0"]


def test_poetry_group_still_resolves() -> None:
    """The Poetry group path is unchanged by the selector fix."""
    assert MODULE.select_requirements(
        DICT_POETRY_WITH_EMPTY_PROJECT_TABLE, list_groups=["dev"]
    ) == ["pytest>=8.0,<9.0.0"]


def test_empty_result_for_a_requested_group_fails_loudly(
    tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zero requirements for a non-empty request must raise, never print nothing and exit 0.

    The negative control for the whole file: an empty ``requirements-lock.txt`` is
    indistinguishable from a dependency-free project, on precisely the constrained hosts
    where the pip fallback runs and nobody is reading the output.
    """
    tmp_path.joinpath("pyproject.toml").write_text('[project]\nname = "empty"\n', encoding="utf-8")
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("BX_GROUPS", "main,dev")

    with pytest.raises(SystemExit, match="No requirements resolved"):
        MODULE.main()


LIST_SPEC = [
    {"version": "^1.26", "python": ">=3.11"},
    {"version": "^1.24", "python": "<3.11"},
]


def test_multiple_constraints_list_expands_to_one_line_per_entry() -> None:
    """A Poetry multiple-constraints list yields one requirement per entry."""
    assert MODULE.build_requirements("numpy", union_spec=LIST_SPEC) == [
        "numpy>=1.26,<2.0.0 ; python_version >= '3.11'",
        "numpy>=1.24,<2.0.0 ; python_version < '3.11'",
    ]


def test_list_entry_with_unsupported_key_still_fails_loudly() -> None:
    """One path/git/url entry inside a list aborts instead of being dropped."""
    with pytest.raises(SystemExit, match="Unsupported dependency type"):
        MODULE.build_requirements("pkg", union_spec=[{"version": "1"}, {"git": "https://x"}])


def test_python_key_becomes_python_version_marker() -> None:
    """A table's ``python`` constraint is no longer dropped."""
    assert (
        MODULE.build_requirement("pkg", union_spec={"version": "^1.0", "python": ">=3.11"})
        == "pkg>=1.0,<2.0.0 ; python_version >= '3.11'"
    )


def test_python_key_merges_with_existing_markers() -> None:
    """``python`` and ``markers`` are joined with ``and``."""
    dict_spec = {"version": "1.0", "python": "<3.12", "markers": "sys_platform == 'win32'"}
    assert (
        MODULE.build_requirement("pkg", union_spec=dict_spec)
        == "pkg==1.0 ; (python_version < '3.12') and (sys_platform == 'win32')"
    )


def test_patch_level_python_constraint_uses_python_full_version() -> None:
    """``python_version`` is major.minor only, so a patch bound needs the full version."""
    assert (
        MODULE.build_requirement("pkg", union_spec={"version": "1.0", "python": ">=3.10.2"})
        == "pkg==1.0 ; python_full_version >= '3.10.2'"
    )


@pytest.mark.parametrize(
    ("str_python", "str_marker"),
    [
        (">3.11", "python_full_version > '3.11.0'"),
        ("<=3.11", "python_full_version <= '3.11.0'"),
        (">=3.11", "python_version >= '3.11'"),
        ("<3.11", "python_version < '3.11'"),
        (">3", "python_full_version > '3.0.0'"),
        ("3.11.*", "python_full_version == '3.11.*'"),
        (">=3.10 <3.12", "python_version >= '3.10' and python_version < '3.12'"),
    ],
)
def test_python_bound_without_patch_picks_the_variable_poetry_picks(
    *, str_python: str, str_marker: str
) -> None:
    """``>`` and ``<=`` on major.minor must not exclude or include a whole 3.11.x line."""
    assert MODULE.python_marker(str_python) == str_marker


def test_or_python_constraint_fails_loudly() -> None:
    """A ``||`` python constraint aborts instead of emitting a wrong marker."""
    with pytest.raises(SystemExit, match=r"Unsupported python constraint .*: pkg -> "):
        MODULE.build_requirement("pkg", union_spec={"version": "1.0", "python": "^2.7 || ^3.6"})


def test_wildcard_python_constraint_adds_no_marker() -> None:
    """``python = "*"`` means any interpreter and leaves the line unmarked."""
    assert (
        MODULE.build_requirement("pkg", union_spec={"version": "1.0", "python": "*"}) == "pkg==1.0"
    )


def test_poetry_dependency_given_as_list_resolves_every_entry() -> None:
    """The list form flows through the Poetry selector, not just the builder."""
    dict_pyproject = {"tool": {"poetry": {"dependencies": {"numpy": LIST_SPEC}}}}
    assert len(MODULE.select_requirements(dict_pyproject, list_groups=["main"])) == 2
