"""Unit tests for the ``__all__`` completeness gate (``bin/check_all_exports.py``).

The should-PASS cases carry as much weight as the should-fail ones. A gate exercised only on
what it rejects has been shown to reject, not to discriminate — and this one rests on two
distinctions a blunter rule would flatten: a package **without** ``__all__`` is out of scope,
and a name a submodule merely **imported** is not a name it defines.
"""

from functools import partial
import importlib.util
from itertools import starmap
from pathlib import Path
from types import ModuleType

import pytest


def _load_gate() -> ModuleType:
    """Import ``bin/check_all_exports.py`` as a module.

    Returns
    -------
    ModuleType
        The loaded gate module.
    """
    path_gate = Path(__file__).resolve().parents[2] / "bin" / "check_all_exports.py"
    cls_spec = importlib.util.spec_from_file_location("_check_all_exports", path_gate)
    assert cls_spec is not None
    assert cls_spec.loader is not None
    cls_module = importlib.util.module_from_spec(cls_spec)
    cls_spec.loader.exec_module(cls_module)
    return cls_module


def _package(tmp_path: Path, str_init: str, str_member: str) -> Path:
    """Write a two-file package and return its ``__init__.py``.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Directory to build in.
    str_init : str
        Source of ``__init__.py``.
    str_member : str
        Source of the sibling submodule ``member.py``.

    Returns
    -------
    pathlib.Path
        Path to the written ``__init__.py``.
    """
    path_pkg = tmp_path / "pkg"
    path_pkg.mkdir(exist_ok=True)
    path_init = path_pkg / "__init__.py"
    path_init.write_text(str_init, encoding="utf-8")
    (path_pkg / "member.py").write_text(str_member, encoding="utf-8")
    return path_init


def _sole(list_problems: list[str]) -> str:
    """Return the one problem reported, asserting there is exactly one.

    The count is a precondition of the content claim (blueprintx#544), not a second
    behaviour: indexing ``[0]`` of an empty list raises an ``IndexError`` naming neither
    the gate nor the package.

    Parameters
    ----------
    list_problems : list of str
        Whatever the gate reported.

    Returns
    -------
    str
        The single problem.
    """
    assert len(list_problems) == 1, list_problems
    return list_problems[0]


def test_complete_export_list_passes(tmp_path: Path) -> None:
    """Every public member named in ``__all__`` → no problems."""
    path_init = _package(
        tmp_path, '__all__ = ["THING", "helper"]\n', "THING = 1\ndef helper():\n    pass\n"
    )
    assert _load_gate().check_package(path_init) == []


def test_member_missing_from_all_is_flagged(tmp_path: Path) -> None:
    """A defined-but-unexported member is named in the failure.

    This is the exact hole an introspective test cannot see: discovering the family through the
    export list just yields one fewer item, so the suite passes by not looking.
    """
    path_init = _package(tmp_path, '__all__ = ["THING"]\n', "THING = 1\nOTHER = 2\n")

    assert "OTHER" in _sole(_load_gate().check_package(path_init))


def test_a_tuple_all_is_read_like_a_list(tmp_path: Path) -> None:
    """``__all__`` may be a tuple; reading only the list form reports everything as missing."""
    path_init = _package(
        tmp_path, '__all__ = ("THING", "helper")\n', "THING = 1\ndef helper():\n    pass\n"
    )
    assert _load_gate().check_package(path_init) == []


def test_package_without_all_is_out_of_scope(tmp_path: Path) -> None:
    """No ``__all__`` means no promise, so nothing to enforce."""
    path_init = _package(tmp_path, "# no exports declared\n", "THING = 1\n")
    assert _load_gate().check_package(path_init) == []


def test_an_imported_name_is_not_required_to_be_exported(tmp_path: Path) -> None:
    """A name the submodule imported belongs to whoever defined it.

    Requiring re-export of everything a module pulls in would force the package to publish its
    own dependencies as public API.
    """
    path_init = _package(
        tmp_path, '__all__ = ["THING"]\n', "from pathlib import Path\n\nTHING = 1\n"
    )
    assert _load_gate().check_package(path_init) == []


def test_private_members_are_not_required_to_be_exported(tmp_path: Path) -> None:
    """An underscore-prefixed name is deliberately not public."""
    path_init = _package(tmp_path, '__all__ = ["THING"]\n', "THING = 1\n_INTERNAL = 2\n")
    assert _load_gate().check_package(path_init) == []


def test_annotated_assignment_counts_as_a_definition(tmp_path: Path) -> None:
    """``NAME: int = 1`` defines a public name just as ``NAME = 1`` does."""
    path_init = _package(tmp_path, '__all__ = ["THING"]\n', "THING = 1\nOTHER: int = 2\n")
    assert "OTHER" in _load_gate().check_package(path_init)[0]


def test_zero_discovery_fails_instead_of_reporting_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scanning nothing must exit non-zero, never green."""
    cls_gate = _load_gate()
    monkeypatch.setattr(cls_gate, "_SRC", tmp_path / "empty")
    (tmp_path / "empty").mkdir()
    assert cls_gate.main() == 1


_PATH_CONTRACTS_INIT = (
    Path(__file__).resolve().parents[2] / "src" / "config" / "contracts" / "__init__.py"
)


@pytest.mark.skipif(
    not _PATH_CONTRACTS_INIT.is_file(), reason="contracts package ships to service tiers only"
)
def test_the_shipped_contracts_package_passes_the_gate() -> None:
    """The template's own export list is complete.

    The gate enters green rather than with a debt to pay — a gate that ships already failing
    teaches its first reader to skip it.
    """
    assert _load_gate().check_package(_PATH_CONTRACTS_INIT) == []


def test_all_name_defined_under_internal_is_flagged(tmp_path: Path) -> None:
    """Re-exporting an ``_internal`` name through ``__all__`` breaks the underscore's promise."""
    path_init = _package(
        tmp_path,
        'from pkg._internal.config.schemas import Doc\n\n__all__ = ["Doc"]\n',
        "",
    )
    assert "is defined under _internal" in _sole(_load_gate().check_package(path_init))


def test_all_module_alias_of_internal_import_is_flagged(tmp_path: Path) -> None:
    """``import pkg._internal.x as schemas`` bound into ``__all__`` exposes an internal module."""
    path_init = _package(
        tmp_path,
        'import pkg._internal.config.schemas as schemas\n\n__all__ = ["schemas"]\n',
        "",
    )
    assert "is defined under _internal" in _sole(_load_gate().check_package(path_init))


def test_all_name_reexported_through_public_sibling_is_flagged(tmp_path: Path) -> None:
    """A name a public sibling took from ``_internal`` is still defined there."""
    path_init = _package(
        tmp_path,
        'from .member import Doc\n\n__all__ = ["Doc"]\n',
        "from pkg._internal.config.schemas import Doc\n",
    )
    assert "is defined under _internal" in _sole(_load_gate().check_package(path_init))


def test_function_local_internal_import_does_not_flag_public_name(tmp_path: Path) -> None:
    """An ``_internal`` import inside a function cannot shadow a public module-level name."""
    path_init = _package(
        tmp_path,
        'from pkg.member import run\n\n__all__ = ["run"]\n\n\n'
        "def helper() -> None:\n    from pkg._internal.x import run\n",
        "def run() -> None:\n    return None\n",
    )
    assert _load_gate().check_package(path_init) == []


def test_all_name_from_public_module_is_not_flagged(tmp_path: Path) -> None:
    """A name imported from a public sibling is untouched by the ``_internal`` guard."""
    path_init = _package(
        tmp_path, 'from pkg.member import THING\n\n__all__ = ["THING"]\n', "THING = 1\n"
    )
    assert _load_gate().check_package(path_init) == []


def test_checkout_path_named_internal_does_not_disable_guard(tmp_path: Path) -> None:
    """A project checked out under a directory called ``_internal`` is still guarded."""
    (tmp_path / "_internal" / "proj").mkdir(parents=True)
    path_init = _package(
        tmp_path / "_internal" / "proj",
        'from pkg._internal.config.schemas import Doc\n\n__all__ = ["Doc"]\n',
        "",
    )
    assert "is defined under _internal" in _sole(_load_gate().check_package(path_init))


def test_internal_package_itself_is_out_of_scope(tmp_path: Path) -> None:
    """The ``_internal`` package's own ``__init__`` may export its own names."""
    path_dir = tmp_path / "pkg" / "_internal"
    path_dir.mkdir(parents=True)
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    path_init = path_dir / "__init__.py"
    path_init.write_text(
        'from pkg._internal.config.schemas import Doc\n\n__all__ = ["Doc"]\n', encoding="utf-8"
    )
    assert _load_gate().check_package(path_init) == []


def _tree(tmp_path: Path, str_init: str, dict_files: dict[str, str]) -> Path:
    """Write ``pkg/__init__.py`` plus arbitrary files below ``pkg`` and return the init.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Directory to build in.
    str_init : str
        Source of ``pkg/__init__.py``.
    dict_files : dict[str, str]
        Path below ``pkg`` mapped to its source.

    Returns
    -------
    pathlib.Path
        Path to the written ``__init__.py``.
    """
    path_pkg = tmp_path / "pkg"
    path_pkg.mkdir(exist_ok=True)
    path_init = path_pkg / "__init__.py"
    path_init.write_text(str_init, encoding="utf-8")
    tuple(starmap(partial(_write, path_pkg), dict_files.items()))
    return path_init


def _write(path_base: Path, str_rel: str, str_source: str) -> None:
    """Write one file below a base directory, creating its parents.

    Parameters
    ----------
    path_base : pathlib.Path
        Directory the relative path is resolved against.
    str_rel : str
        Path of the file below the base.
    str_source : str
        File content.
    """
    path_file = path_base / str_rel
    path_file.parent.mkdir(parents=True, exist_ok=True)
    path_file.write_text(str_source, encoding="utf-8")


_STR_LEAK = "from pkg._internal.config.schemas import Doc\n"
_STR_EXPORT_DOC = '__all__ = ["Doc"]\n'
_STR_FROM_MEMBER = "from .member import Doc\n" + _STR_EXPORT_DOC


@pytest.mark.parametrize(
    ("str_init", "dict_files"),
    [
        pytest.param(
            "from pkg.member import Doc\n" + _STR_EXPORT_DOC,
            {"member.py": _STR_LEAK},
            id="absolute-sibling",
        ),
        pytest.param(
            "from .a.b import Doc\n" + _STR_EXPORT_DOC,
            {"a/__init__.py": "", "a/b.py": _STR_LEAK},
            id="dotted-relative",
        ),
        pytest.param(
            "from pkg.a.b import Doc\n" + _STR_EXPORT_DOC,
            {"a/__init__.py": "", "a/b.py": _STR_LEAK},
            id="dotted-absolute",
        ),
        pytest.param(
            _STR_FROM_MEMBER,
            {"member/__init__.py": _STR_LEAK},
            id="sibling-package",
        ),
        pytest.param(
            _STR_FROM_MEMBER,
            {"member.py": "try:\n    " + _STR_LEAK + "except ImportError:\n    Doc = None\n"},
            id="followed-file-try",
        ),
        pytest.param(
            _STR_FROM_MEMBER,
            {
                "member.py": "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    "
                + _STR_LEAK
            },
            id="followed-file-type-checking",
        ),
        pytest.param(
            _STR_FROM_MEMBER,
            {"member.py": "import sys\n\nif sys.version_info >= (3, 11):\n    " + _STR_LEAK},
            id="followed-file-version-check",
        ),
        pytest.param(
            "try:\n    " + _STR_LEAK + "except ImportError:\n    Doc = None\n" + _STR_EXPORT_DOC,
            {},
            id="init-level-try",
        ),
        pytest.param(
            "import contextlib\n\nwith contextlib.suppress(ImportError):\n    "
            + _STR_LEAK
            + _STR_EXPORT_DOC,
            {},
            id="init-level-with",
        ),
        pytest.param(
            "from . import _internal as Doc\n" + _STR_EXPORT_DOC,
            {"_internal/__init__.py": ""},
            id="bare-relative-internal-package",
        ),
        pytest.param(
            "from .member import Doc\n" + _STR_EXPORT_DOC,
            {"member.py": "from . import _internal as Doc\n", "_internal/__init__.py": ""},
            id="bare-relative-internal-package-via-sibling",
        ),
        pytest.param(
            "from pkg._internal.config.schemas import *\n" + _STR_EXPORT_DOC,
            {},
            id="star-import-from-internal",
        ),
        pytest.param(
            "from .member import *\n" + _STR_EXPORT_DOC,
            {"member.py": _STR_LEAK},
            id="star-import-through-sibling",
        ),
        pytest.param(
            "from pkg import _internal as Doc\n" + _STR_EXPORT_DOC,
            {"_internal/__init__.py": ""},
            id="absolute-internal-package",
        ),
        pytest.param(
            "from .member import Doc\n" + _STR_EXPORT_DOC,
            {"member.py": "from pkg import _internal as Doc\n", "_internal/__init__.py": ""},
            id="absolute-internal-package-via-sibling",
        ),
    ],
)
def test_internal_leak_is_traced_through_every_import_shape(
    tmp_path: Path, str_init: str, dict_files: dict[str, str]
) -> None:
    """Every spelling of an ``_internal`` import that reaches ``__all__`` is a finding."""
    path_init = _tree(tmp_path, str_init, dict_files)
    assert "is defined under _internal" in _sole(_load_gate().check_package(path_init))


def test_star_import_of_a_public_module_is_not_flagged(tmp_path: Path) -> None:
    """``from .member import *`` is clean when ``member`` defines the name itself."""
    path_init = _tree(
        tmp_path, "from .member import *\n" + _STR_EXPORT_DOC, {"member.py": "Doc = 1\n"}
    )
    assert _load_gate().check_package(path_init) == []


@pytest.mark.parametrize(
    "str_import",
    [
        pytest.param("from .member import Doc\n", id="relative"),
        pytest.param("from vendor import Doc\n", id="third-party"),
        pytest.param("import vendor.Doc as Doc\n", id="aliased-module"),
    ],
)
def test_star_import_is_not_a_fallback_for_an_explicitly_imported_name(
    tmp_path: Path, str_import: str
) -> None:
    """A name some statement binds explicitly is never attributed to a later ``_internal`` star."""
    path_init = _tree(
        tmp_path,
        str_import + "from pkg._internal.config.schemas import *\n" + _STR_EXPORT_DOC,
        {"member.py": "Doc = 1\n"},
    )
    assert _load_gate().check_package(path_init) == []


def test_star_import_shadowed_by_a_local_definition_is_not_flagged(tmp_path: Path) -> None:
    """A name the module defines itself is not the star import's name."""
    path_init = _tree(
        tmp_path,
        "from .member import *\n" + _STR_EXPORT_DOC,
        {"member.py": "from pkg._internal.config.schemas import *\n\n\nclass Doc:\n    pass\n"},
    )
    assert _load_gate().check_package(path_init) == []


def test_absolute_import_cycle_terminates_without_a_finding(tmp_path: Path) -> None:
    """Two siblings importing each other through absolute paths do not loop."""
    path_init = _tree(
        tmp_path,
        "from pkg.a import Doc\n" + _STR_EXPORT_DOC,
        {"a.py": "from pkg.b import Doc\n", "b.py": "from pkg.a import Doc\n"},
    )
    assert _load_gate().check_package(path_init) == []


def test_absolute_import_of_another_top_package_is_not_followed(tmp_path: Path) -> None:
    """``from other.member import Doc`` never resolves into this package's tree."""
    path_init = _tree(
        tmp_path,
        "from other.member import Doc\n" + _STR_EXPORT_DOC,
        {"member.py": _STR_LEAK},
    )
    assert _load_gate().check_package(path_init) == []


def test_followed_file_with_a_syntax_error_is_reported_not_raised(tmp_path: Path) -> None:
    """A broken sibling is a finding naming that file, not a traceback."""
    path_init = _tree(tmp_path, _STR_FROM_MEMBER, {"member.py": "def (:\n"})
    assert "member.py: could not parse" in _sole(_load_gate().check_package(path_init))


def test_public_and_internal_star_imports_do_not_flag_the_public_names(tmp_path: Path) -> None:
    """A public star import beside an ``_internal`` one keeps its names."""
    path_init = _tree(
        tmp_path,
        "from .public import *\nfrom ._internal.config import *\n" + '__all__ = ["Pub", "Priv"]\n',
        {
            "public.py": "class Pub:\n    pass\n",
            "_internal/__init__.py": "",
            "_internal/config.py": "class Priv:\n    pass\n",
        },
    )
    assert "'Priv'" in _sole(_load_gate().check_package(path_init))


_STR_STAR_INTERNAL = "from .public import *\nfrom ._internal.config import *\n"


def test_nested_star_import_inside_internal_is_still_charged(tmp_path: Path) -> None:
    """A name an ``_internal`` module re-exports through its own star import still leaks."""
    path_init = _tree(
        tmp_path,
        _STR_STAR_INTERNAL + '__all__ = ["Pub", "Priv"]\n',
        {
            "public.py": "class Pub:\n    pass\n",
            "_internal/__init__.py": "",
            "_internal/config.py": "from .deeper import *\n",
            "_internal/deeper.py": "class Priv:\n    pass\n",
        },
    )
    assert "'Priv'" in _sole(_load_gate().check_package(path_init))


def test_internal_all_limits_what_its_star_import_is_charged(tmp_path: Path) -> None:
    """A name outside the ``_internal`` module's own ``__all__`` is not its star import's."""
    path_init = _tree(
        tmp_path,
        _STR_STAR_INTERNAL + '__all__ = ["Pub"]\n',
        {
            "public.py": "class Pub:\n    pass\n",
            "_internal/__init__.py": "",
            "_internal/config.py": '__all__ = ["Other"]\n\n\nclass Other:\n    pass\n',
        },
    )
    assert _load_gate().check_package(path_init) == []


def test_broken_internal_star_target_is_a_finding_not_a_traceback(tmp_path: Path) -> None:
    """A syntax error in the ``_internal`` star target is reported by file name."""
    path_init = _tree(
        tmp_path,
        _STR_STAR_INTERNAL + _STR_EXPORT_DOC,
        {
            "public.py": "Doc = 1\n",
            "_internal/__init__.py": "",
            "_internal/config.py": "def (:\n",
        },
    )
    assert "config.py: could not parse" in _sole(_load_gate().check_package(path_init))


def test_third_party_internal_package_is_not_charged(tmp_path: Path) -> None:
    """``from otherlib import _internal`` is not this package's ``_internal``."""
    path_init = _tree(tmp_path, "from otherlib import _internal as Doc\n" + _STR_EXPORT_DOC, {})
    assert _load_gate().check_package(path_init) == []


def test_relative_internal_package_keeps_its_leading_dot(tmp_path: Path) -> None:
    """The finding names ``.sub._internal``, the path as written."""
    path_init = _tree(
        tmp_path,
        "from .sub import _internal as Doc\n" + _STR_EXPORT_DOC,
        {"sub/__init__.py": "", "sub/_internal/__init__.py": ""},
    )
    assert "(.sub._internal)" in _sole(_load_gate().check_package(path_init))
