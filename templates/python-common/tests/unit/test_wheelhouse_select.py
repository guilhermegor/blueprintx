"""Unit tests for the offline-wheelhouse selector and assembler (blueprintx#299).

Every case here is a **should-fail witness calibrated against the pre-fix code** —
each one was run against the buggy version first and watched to fail, because a
regression test written at the moment of the fix is the one most likely to be
asserting nothing.

The three defects these pin share one shape: the manifest and the target triple are
**untrusted input**, and each check trusted them in a different way. A marker
environment built with the wrong spelling silently drops requirements; a manifest that
disagrees with itself was accepted; and a manifest naming ``../../etc/shadow`` was
resolved and operated on. None of the three produced an error — all three produced a
confident wrong answer, which is why they need tests rather than review.
"""

import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest


_LIB = Path(__file__).resolve().parents[2] / "bin" / "lib"


def _load(str_name: str) -> ModuleType:
	"""Load a ``bin/lib/`` script by path (``bin/lib/`` is not a package).

	Parameters
	----------
	str_name : str
		Module stem under ``bin/lib/``.

	Returns
	-------
	ModuleType
		The imported module.
	"""
	cls_spec = importlib.util.spec_from_file_location(str_name, _LIB / f"{str_name}.py")
	cls_module = importlib.util.module_from_spec(cls_spec)
	sys.modules[str_name] = cls_module
	cls_spec.loader.exec_module(cls_module)
	return cls_module


gate = _load("wheelhouse_select")


def _manifest(list_parts: list[dict], **kwargs) -> dict:
	"""Build a manifest with sane defaults, overridable per test.

	Parameters
	----------
	list_parts : list of dict
		The ``parts`` entries.
	**kwargs
		Fields overriding the defaults.

	Returns
	-------
	dict
		A manifest shaped like the one ``pack_wheelhouse`` writes.
	"""
	dict_manifest = {"parts": list_parts, "part_count": len(list_parts),
		"zip_name": "wheelhouse.zip"}
	dict_manifest.update(kwargs)
	return dict_manifest


def test_cpython_maps_to_the_spelling_pep_508_compares_against() -> None:
	"""``"cpython".capitalize()`` is ``Cpython``, and the marker then evaluates False.

	Measured: ``Marker('platform_python_implementation == "CPython"')`` evaluates False
	against ``Cpython`` and True against ``CPython``, so every CPython-only requirement
	left the default wheelhouse — the wheelhouse was short, not broken, which is why
	nothing failed.
	"""
	assert gate._canonical_implementation("cpython") == "CPython"


def test_pypy_maps_to_its_canonical_spelling_too() -> None:
	"""``"pypy".capitalize()`` is ``Pypy``; the same silent drop applies."""
	assert gate._canonical_implementation("pypy") == "PyPy"


def test_an_unknown_implementation_is_returned_unchanged_not_guessed() -> None:
	"""Guessing a canonical spelling reintroduces the same silent-drop failure."""
	assert gate._canonical_implementation("graalpy") == "graalpy"


def test_the_marker_environment_carries_the_canonical_implementation() -> None:
	"""The end-to-end assertion: the fix has to reach the dict the marker reads."""
	dict_env = gate.target_environment("3.12.1", "linux", "x86_64", "cpython")

	assert dict_env["platform_python_implementation"] == "CPython"


def test_a_manifest_whose_declared_count_disagrees_is_refused(tmp_path: Path) -> None:
	"""``verify_parts``' docstring promised this check; the code never made it.

	Worse than a missing check: the contract was *documented*, so a reader had no
	reason to look. A manifest declaring 3 parts while listing 2 assembled happily as
	long as the 2 listed hashes matched.
	"""
	(tmp_path / "a.part").write_bytes(b"x")
	dict_manifest = _manifest(
		[{"name": "a.part", "sha256": gate.sha256_of(tmp_path / "a.part")}], part_count=3
	)

	with pytest.raises(SystemExit, match="declares 3 part"):
		gate.verify_parts(tmp_path, dict_manifest)


def test_a_manifest_whose_declared_count_agrees_still_passes(tmp_path: Path) -> None:
	"""The negative control — the new check must not reject an honest manifest."""
	(tmp_path / "a.part").write_bytes(b"x")
	dict_manifest = _manifest([{"name": "a.part", "sha256": gate.sha256_of(tmp_path / "a.part")}])

	assert gate.verify_parts(tmp_path, dict_manifest) == [(tmp_path / "a.part").resolve()]


def test_an_absolute_part_name_cannot_escape_the_transfer_directory(tmp_path: Path) -> None:
	"""``Path("/srv/parts") / "/etc/passwd"`` is ``/etc/passwd`` — the base is discarded.

	The sha256 fields authenticate CONTENT, never the path, so they cannot catch this.
	"""
	dict_manifest = _manifest([{"name": "/etc/passwd", "sha256": "0" * 64}])

	with pytest.raises(SystemExit, match="escapes"):
		gate.verify_parts(tmp_path, dict_manifest)


def test_a_parent_relative_part_name_cannot_escape_either(tmp_path: Path) -> None:
	"""``../../etc/shadow`` resolves outside the base without ever looking absolute."""
	dict_manifest = _manifest([{"name": "../../etc/shadow", "sha256": "0" * 64}])

	with pytest.raises(SystemExit, match="escapes"):
		gate.verify_parts(tmp_path, dict_manifest)


def test_an_ordinary_part_name_is_still_accepted(tmp_path: Path) -> None:
	"""The negative control for containment: a plain basename must keep working."""
	(tmp_path / "wheelhouse.zip.001").write_bytes(b"x")

	assert gate._contained_path(tmp_path, "wheelhouse.zip.001").is_file()


def test_a_nested_part_name_inside_the_directory_is_accepted(tmp_path: Path) -> None:
	"""Containment is the rule, not basename-only — a subdirectory is still inside."""
	(tmp_path / "sub").mkdir()

	assert gate._contained_path(tmp_path, "sub/a.part").parent.name == "sub"
