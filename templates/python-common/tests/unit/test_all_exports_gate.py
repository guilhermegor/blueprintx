"""Unit tests for the ``__all__`` completeness gate (``bin/check_all_exports.py``).

The should-PASS cases carry as much weight as the should-fail ones. A gate exercised only on
what it rejects has been shown to reject, not to discriminate — and this one rests on two
distinctions a blunter rule would flatten: a package **without** ``__all__`` is out of scope,
and a name a submodule merely **imported** is not a name it defines.
"""

import importlib.util
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
	assert cls_spec is not None and cls_spec.loader is not None
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
	list_problems = _load_gate().check_package(path_init)
	assert len(list_problems) == 1
	assert "OTHER" in list_problems[0]


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
	# A gate that scanned nothing also found nothing wrong, and would report OK forever the day
	# a path is renamed. This is the control that keeps the gate from becoming decorative.
	cls_gate = _load_gate()
	monkeypatch.setattr(cls_gate, "_SRC", tmp_path / "empty")
	(tmp_path / "empty").mkdir()
	assert cls_gate.main() == 1


_PATH_CONTRACTS_INIT = (
	Path(__file__).resolve().parents[2] / "src" / "config" / "contracts" / "__init__.py"
)


# The condition is fixed at import time (does this tier ship the package?), so it is not a path
# THROUGH the test — but an `if` in the body makes it one, to a reader and to mccabe alike.
@pytest.mark.skipif(
	not _PATH_CONTRACTS_INIT.is_file(), reason="contracts package ships to service tiers only"
)
def test_the_shipped_contracts_package_passes_the_gate() -> None:
	"""The template's own export list is complete.

	The gate enters green rather than with a debt to pay — a gate that ships already failing
	teaches its first reader to skip it.
	"""
	assert _load_gate().check_package(_PATH_CONTRACTS_INIT) == []
