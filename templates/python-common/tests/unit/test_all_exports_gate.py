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


_STR_STAR_INTERNAL = "from .public import *\nfrom ._internal.config import *\n"


def test_public_and_internal_star_imports_do_not_flag_the_public_names(tmp_path: Path) -> None:
    """A public star import beside an ``_internal`` one keeps its names."""
    path_init = _tree(
        tmp_path,
        _STR_STAR_INTERNAL + '__all__ = ["Pub", "Priv"]\n',
        {
            "public.py": "class Pub:\n    pass\n",
            "_internal/__init__.py": "",
            "_internal/config.py": "class Priv:\n    pass\n",
        },
    )
    assert "'Priv'" in _sole(_load_gate().check_package(path_init))


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


def test_unresolvable_nested_star_inside_internal_fails_closed(tmp_path: Path) -> None:
    """A nested star import nobody can read is assumed to provide the name."""
    path_init = _tree(
        tmp_path,
        'from ._internal.config import *\n__all__ = ["Priv"]\n',
        {
            "_internal/__init__.py": "",
            "_internal/config.py": "from otherlib import *\n",
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
            "_internal/config.py": (
                '__all__ = ["Other"]\n\n\nclass Other:\n    pass\n\n\nclass Pub:\n    pass\n'
            ),
        },
    )
    assert _load_gate().check_package(path_init) == []


def test_name_listed_in_internal_all_is_charged_even_when_unbound_visibly(
    tmp_path: Path,
) -> None:
    """A name in the ``_internal`` module's ``__all__`` is its star import's, bound or not."""
    path_init = _tree(
        tmp_path,
        'from ._internal.config import *\n__all__ = ["Priv"]\n',
        {
            "_internal/__init__.py": "",
            "_internal/config.py": '__all__ = ["Priv"]\n',
        },
    )
    assert "'Priv'" in _sole(_load_gate().check_package(path_init))


def test_internal_all_extended_after_assignment_is_not_trusted(tmp_path: Path) -> None:
    """A ``+=`` on ``__all__`` means the first assignment cannot exclude a name."""
    path_init = _tree(
        tmp_path,
        'from ._internal.config import *\n__all__ = ["Priv"]\n',
        {
            "_internal/__init__.py": "",
            "_internal/config.py": (
                '__all__ = ["Other"]\n__all__ += ["Priv"]\n\n\nclass Other:\n    pass\n\n\n'
                "class Priv:\n    pass\n"
            ),
        },
    )
    assert "'Priv'" in _sole(_load_gate().check_package(path_init))


@pytest.mark.parametrize(
    "str_config",
    [
        "for Priv in range(1):\n    pass\n",
        "with open('x') as Priv:\n    pass\n",
        "Other, Priv = 1, 2\n",
        "(Priv := 1)\n",
        "try:\n    pass\nexcept ValueError as Priv:\n    pass\n",
        "globals()['Priv'] = 1\n",
        "locals()['Priv'] = 1\n",
        "exec('Priv = 1')\n",
        "import builtins\nsetattr(builtins, 'Priv', 1)\n",
        "match 1:\n    case Priv:\n        pass\n",
        "def f():\n    global Priv\n    Priv = 1\n",
    ],
    ids=[
        "for",
        "with",
        "unpack",
        "walrus",
        "except",
        "globals",
        "locals",
        "exec",
        "setattr",
        "match",
        "global",
    ],
)
def test_binding_form_without_all_is_still_charged(tmp_path: Path, str_config: str) -> None:
    """With no ``__all__``, any form that binds the name in an ``_internal`` target leaks it."""
    path_init = _tree(
        tmp_path,
        'from ._internal.config import *\n__all__ = ["Priv"]\n',
        {"_internal/__init__.py": "", "_internal/config.py": str_config},
    )
    assert "'Priv'" in _sole(_load_gate().check_package(path_init))


@pytest.mark.parametrize(
    "str_tail",
    [
        '__all__ = __all__ + ["Priv"]\n',
        '__all__ = ["Other"]\n',
        '__all__.append("Priv")\n',
        '__all__.extend(["Priv"])\n',
        '__all__[:] = ["Priv"]\n',
    ],
    ids=["concat", "reassign", "append", "extend", "subscript"],
)
def test_internal_all_changed_after_assignment_is_not_trusted(
    tmp_path: Path, str_tail: str
) -> None:
    """Any later write to ``__all__`` means its first assignment cannot exclude a name."""
    path_init = _tree(
        tmp_path,
        'from ._internal.config import *\n__all__ = ["Priv"]\n',
        {
            "_internal/__init__.py": "",
            "_internal/config.py": '__all__ = ["Other"]\n' + str_tail + "Priv = Other = 1\n",
        },
    )
    assert "'Priv'" in _sole(_load_gate().check_package(path_init))


@pytest.mark.parametrize(
    ("str_config", "bool_charged"),
    [
        ('globals()["Priv"] = 1\n', True),
        ('def _i():\n    globals()["Priv"] = 1\n\n\n_i()\n', True),
        ('class A:\n    globals()["Priv"] = 1\n', True),
        ("(lambda: globals().update(Priv=1))()\n", True),
        ("def f(x=globals().update(Priv=1)):\n    pass\n", True),
        (
            "def d(f):\n    return f\n\n\n@d(globals().update(Priv=1))\ndef g():\n    pass\n",
            True,
        ),
        ('def _i():\n    exec("Priv = 1", globals())\n\n\n_i()\n', True),
        ('__all__ = ["Other"]\ndef _i():\n    globals()["__all__"].append("Priv")\n', True),
        ("import sys\nsetattr(sys.modules[__name__], 'Priv', 1)\n", True),
        ("def f():\n    setattr(sys.modules[__name__], 'Priv', 1)\n", True),
        ("(lambda self: setattr(self, 'Priv', 1))(sys.modules[__name__])\n", True),
        ("def f(cls=sys.modules[__name__]):\n    setattr(cls, 'Priv', 1)\nf()\n", True),
        ("eval('globals().update(Priv=1)')\n", True),
        ("import builtins\nbuiltins.exec('Priv = 1')\n", True),
        ("import sys\nsys.modules[__name__].Priv = 1\n", True),
        ("import os\nif os.environ.get('X'):\n    globals()['Priv'] = 1\n", True),
        ('class A:\n    def __init__(self):\n        setattr(self, "Priv", 1)\n', False),
        ("class A:\n    def d(self):\n        return vars(self)\n", False),
        ("class A:\n    async def d(self):\n        setattr(self, 'Priv', 1)\n", False),
        ("def f():\n    (Priv := 1)\n    return lambda: (Priv := 2)\n", False),
    ],
    ids=[
        "module",
        "def-called",
        "class-body",
        "lambda",
        "default-arg",
        "decorator",
        "exec-in-def",
        "all-append-in-def",
        "setattr-sys-modules",
        "setattr-sys-modules-in-def",
        "lambda-self",
        "def-cls-default",
        "eval",
        "builtins-attr",
        "sys-modules-store",
        "dynamic-in-if",
        "setattr-self",
        "vars-self",
        "async-setattr-self",
        "walrus-in-body",
    ],
)
def test_dynamic_write_anywhere_is_charged_except_on_self(
    tmp_path: Path, str_config: str, bool_charged: bool
) -> None:
    """Any dynamic write is assumed to provide the name; ``self``/``cls`` writes are exempt."""
    path_init = _tree(
        tmp_path,
        'from ._internal.config import *\n__all__ = ["Priv"]\n',
        {"_internal/__init__.py": "", "_internal/config.py": str_config},
    )
    assert bool(_load_gate().check_package(path_init)) is bool_charged


def test_opaque_all_provides_a_name_that_is_not_visibly_bound(tmp_path: Path) -> None:
    """An ``__all__`` the gate cannot read provides every name, bound or not."""
    path_init = _tree(
        tmp_path,
        'from ._internal.config import *\n__all__ = ["Priv"]\n',
        {"_internal/__init__.py": "", "_internal/config.py": '__all__ = ["Priv"] + []\n'},
    )
    assert "'Priv'" in _sole(_load_gate().check_package(path_init))


def test_internal_all_built_from_a_non_literal_is_not_trusted(tmp_path: Path) -> None:
    """``__all__ = [*other]`` hides names from the literal reader, so it excludes nothing."""
    path_init = _tree(
        tmp_path,
        'from ._internal.config import *\n__all__ = ["Priv"]\n',
        {
            "_internal/__init__.py": "",
            "_internal/config.py": '__all__ = [*["Priv"]]\nPriv = 1\n',
        },
    )
    assert "'Priv'" in _sole(_load_gate().check_package(path_init))


def test_missing_internal_star_target_is_still_charged(tmp_path: Path) -> None:
    """A star import from an ``_internal`` file that does not exist is attributed to it."""
    path_init = _tree(
        tmp_path,
        'from ._internal.missing import *\n__all__ = ["Priv"]\n',
        {"_internal/__init__.py": ""},
    )
    assert "'Priv'" in _sole(_load_gate().check_package(path_init))


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


def test_relative_internal_package_in_a_namespace_directory_is_charged(tmp_path: Path) -> None:
    """A relative import is first-party even when its directory has no ``__init__.py``."""
    path_init = _tree(
        tmp_path,
        "from .sub import _internal as Doc\n" + _STR_EXPORT_DOC,
        {"sub/_internal/__init__.py": ""},
    )
    assert "'Doc'" in _sole(_load_gate().check_package(path_init))


def test_relative_internal_package_keeps_its_leading_dot(tmp_path: Path) -> None:
    """The finding names ``.sub._internal``, the path as written."""
    path_init = _tree(
        tmp_path,
        "from .sub import _internal as Doc\n" + _STR_EXPORT_DOC,
        {"sub/__init__.py": "", "sub/_internal/__init__.py": ""},
    )
    assert "(.sub._internal)" in _sole(_load_gate().check_package(path_init))


_STR_SELF_MODULE = "import pkg._internal.config as me\n"


@pytest.mark.parametrize(
    "str_config",
    [
        "from builtins import exec as run\nrun('Priv = 1')\n",
        "from builtins import globals as gl\ngl()['Priv'] = 1\n",
        "from sys import modules as m\nm[__name__].Priv = 1\n",
        _STR_SELF_MODULE
        + "class A:\n    def f(self):\n        self = me\n        setattr(self, 'Priv', 1)\n"
        + "A().f()\n",
        _STR_SELF_MODULE
        + "class A:\n    def f(self):\n        def inner(self):\n"
        + "            setattr(self, 'Priv', 1)\n        inner(me)\nA().f()\n",
        _STR_SELF_MODULE
        + "class A:\n    @staticmethod\n    def f(cls):\n        setattr(cls, 'Priv', 1)\n"
        + "A.f(me)\n",
        _STR_SELF_MODULE
        + "class A:\n    def f(self):\n        import pkg._internal.config as self\n"
        + "        setattr(self, 'Priv', 1)\nA().f()\n",
        _STR_SELF_MODULE
        + "class A:\n    def f(self):\n        match me:\n            case self:\n"
        + "                setattr(self, 'Priv', 1)\nA().f()\n",
        _STR_SELF_MODULE
        + "class A:\n    def f(self):\n        try:\n            pass\n"
        + "        except Exception as self:\n            pass\n        setattr(self, 'Priv', 1)\n"
        + "A().f()\n",
        "def f(x=(Priv := 1)):\n    pass\n",
        "def f(*, x=(Priv := 1)):\n    pass\n",
        "g = lambda x=(Priv := 1): x\n",
        "class B(metaclass=(Priv := type)):\n    pass\n",
        "async def f(x=(Priv := 1)):\n    pass\n",
        _STR_SELF_MODULE
        + "class A:\n    def f(self):\n        type self = int\n        setattr(self, 'Priv', 1)\n"
        + "A().f()\n",
        _STR_SELF_MODULE
        + "class A:\n    @builtins.staticmethod\n    def f(cls):\n"
        + "        setattr(cls, 'Priv', 1)\nA.f(me)\n",
        "def d(v):\n    return lambda f: f\n\n\n@d(Priv := 1)\ndef g():\n    pass\n",
        "class B((Priv := 1).__class__):\n    pass\n",
        "__all__ = ['Other']\ndel __all__\nPriv = 1\n",
    ],
    ids=[
        "alias-exec",
        "alias-globals",
        "alias-sys-modules",
        "self-reassigned",
        "nested-def-self",
        "staticmethod-cls",
        "import-as-self",
        "match-capture-self",
        "except-as-self",
        "walrus-default",
        "walrus-kwonly-default",
        "walrus-lambda-default",
        "walrus-class-keyword",
        "walrus-async-default",
        "type-alias-self",
        "staticmethod-attribute",
        "walrus-decorator",
        "walrus-class-base",
        "del-all",
    ],
)
def test_dynamic_binding_shape_beyond_the_plain_forms_is_charged(
    tmp_path: Path, str_config: str
) -> None:
    """An aliased writer, a rebound ``self``, a walrus outside a body or ``del __all__`` leaks."""
    path_init = _tree(
        tmp_path,
        'from ._internal.config import *\n__all__ = ["Priv"]\n',
        {"_internal/__init__.py": "", "_internal/config.py": str_config},
    )
    assert "'Priv'" in _sole(_load_gate().check_package(path_init))


@pytest.mark.parametrize(
    "str_config",
    [
        "class A:\n    def f(self):\n        self.x = 1\n        setattr(self, 'Priv', 1)\n",
        "class A:\n    @classmethod\n    def f(cls):\n        setattr(cls, 'Priv', 1)\n",
        "from builtins import print as p\np('Priv')\n",
        "class A:\n    def f(self):\n        def g(x=setattr(self, 'Priv', 1)):\n"
        + "            pass\n",
        "class A:\n    def f(self):\n        @setattr(self, 'Priv', 1)\n        def g():\n"
        + "            pass\n",
    ],
    ids=[
        "attribute-store-on-self",
        "classmethod-cls",
        "unrelated-builtins-alias",
        "own-self-in-nested-default",
        "own-self-in-nested-decorator",
    ],
)
def test_dynamic_binding_exemption_still_holds_for_the_plain_forms(
    tmp_path: Path, str_config: str
) -> None:
    """A method writing its own ``self``/``cls``, or a harmless builtin alias, stays clean."""
    path_init = _tree(
        tmp_path,
        'from ._internal.config import *\n__all__ = ["Priv"]\n',
        {"_internal/__init__.py": "", "_internal/config.py": str_config},
    )
    assert _load_gate().check_package(path_init) == []
