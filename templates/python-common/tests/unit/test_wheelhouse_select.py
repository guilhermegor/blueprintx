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

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import ModuleType
import zipfile

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


def _manifest(list_parts: list[dict], **kwargs: object) -> dict:
    """Build a manifest with sane defaults, overridable per test.

    Parameters
    ----------
    list_parts : list of dict
        The ``parts`` entries.
    **kwargs : object
        Fields overriding the defaults.

    Returns
    -------
    dict
        A manifest shaped like the one ``pack_wheelhouse`` writes.
    """
    dict_manifest = {
        "parts": list_parts,
        "part_count": len(list_parts),
        "zip_name": "wheelhouse.zip",
    }
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
    dict_env = gate.target_environment(
        "3.12.1",
        str_sys_platform="linux",
        str_platform_machine="x86_64",
        str_implementation="cpython",
    )

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
        gate.verify_parts(tmp_path, dict_manifest=dict_manifest)


def test_a_manifest_whose_declared_count_agrees_still_passes(tmp_path: Path) -> None:
    """The negative control — the new check must not reject an honest manifest."""
    (tmp_path / "a.part").write_bytes(b"x")
    dict_manifest = _manifest([{"name": "a.part", "sha256": gate.sha256_of(tmp_path / "a.part")}])

    assert gate.verify_parts(tmp_path, dict_manifest=dict_manifest) == [
        (tmp_path / "a.part").resolve()
    ]


def test_a_non_positive_part_size_is_refused_instead_of_packing_nothing(tmp_path: Path) -> None:
    """A zero part size used to produce no parts and a successful, unassemblable manifest."""
    path_zip = tmp_path / "w.zip"
    path_zip.write_bytes(b"x")

    with pytest.raises(SystemExit, match="positive"):
        gate.split_into_parts(path_zip, int_part_mb=0)


def test_an_absolute_part_name_cannot_escape_the_transfer_directory(tmp_path: Path) -> None:
    """``Path("/srv/parts") / "/etc/passwd"`` is ``/etc/passwd`` — the base is discarded.

    The sha256 fields authenticate CONTENT, never the path, so they cannot catch this.
    """
    dict_manifest = _manifest([{"name": "/etc/passwd", "sha256": "0" * 64}])

    with pytest.raises(SystemExit, match="escapes"):
        gate.verify_parts(tmp_path, dict_manifest=dict_manifest)


def test_a_parent_relative_part_name_cannot_escape_either(tmp_path: Path) -> None:
    """``../../etc/shadow`` resolves outside the base without ever looking absolute."""
    dict_manifest = _manifest([{"name": "../../etc/shadow", "sha256": "0" * 64}])

    with pytest.raises(SystemExit, match="escapes"):
        gate.verify_parts(tmp_path, dict_manifest=dict_manifest)


def test_an_ordinary_part_name_is_still_accepted(tmp_path: Path) -> None:
    """The negative control for containment: a plain basename must keep working."""
    (tmp_path / "wheelhouse.zip.001").write_bytes(b"x")

    assert gate._contained_path(tmp_path, str_name="wheelhouse.zip.001").is_file()


def test_a_nested_part_name_inside_the_directory_is_accepted(tmp_path: Path) -> None:
    """Containment is the rule, not basename-only — a subdirectory is still inside."""
    (tmp_path / "sub").mkdir()

    assert gate._contained_path(tmp_path, str_name="sub/a.part").parent.name == "sub"


def _wheel_dir(tmp_path: Path, *list_names: str) -> Path:
    """Create a directory holding one tiny file per name.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory to create the folder in.
    *list_names : str
        File names to create.

    Returns
    -------
    pathlib.Path
        The directory.
    """
    dir_wheels = tmp_path / "dl"
    dir_wheels.mkdir()
    tuple(map(lambda str_name: (dir_wheels / str_name).write_bytes(b"x" * 10), list_names))
    return dir_wheels


def _pack_args(tmp_path: Path, *, dir_wheels: Path) -> argparse.Namespace:
    """Build the ``pack`` arguments for a payload written next to ``tmp_path``.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory the payload is written into.
    dir_wheels : pathlib.Path
        The wheels directory to pack.

    Returns
    -------
    argparse.Namespace
        Arguments as the CLI would parse them.
    """
    return argparse.Namespace(
        wheels_dir=str(dir_wheels),
        zip_path=str(tmp_path / "out" / "wheelhouse.zip"),
        manifest=str(tmp_path / "out" / "manifest.json"),
        part_size_mb=1,
    )


def test_a_non_wheel_download_is_refused_instead_of_silently_dropped(tmp_path: Path) -> None:
    """An sdist has no wheel to zip; packing only the wheels would hide it from the target."""
    dir_wheels = _wheel_dir(tmp_path, "a-1.0-py3-none-any.whl", "b-2.0.tar.gz")

    with pytest.raises(SystemExit, match=r"b-2\.0\.tar\.gz"):
        gate.build_zip(dir_wheels, path_zip=tmp_path / "w.zip")


def test_pack_then_assemble_round_trips_the_wheels(tmp_path: Path) -> None:
    """The shipped payload shape must reassemble to the wheels that were packed."""
    dir_wheels = _wheel_dir(tmp_path, "a-1.0-py3-none-any.whl", "b-2.0-py3-none-any.whl")
    gate.pack_wheelhouse(_pack_args(tmp_path, dir_wheels=dir_wheels))
    dir_out = tmp_path / "wheels"

    gate.assemble_wheelhouse(
        argparse.Namespace(
            source=str(tmp_path / "out"),
            wheels_out=str(dir_out),
            manifest=str(tmp_path / "out" / "manifest.json"),
        )
    )

    assert sorted(p.name for p in dir_out.glob("*.whl")) == [
        "a-1.0-py3-none-any.whl",
        "b-2.0-py3-none-any.whl",
    ]


def test_a_hand_made_zip_with_a_nested_folder_extracts_flat(tmp_path: Path) -> None:
    """Pip's --find-links does not recurse, so ``wheels/x.whl`` must land as ``x.whl``."""
    path_zip = tmp_path / "wheelhouse.zip"
    with zipfile.ZipFile(path_zip, "w") as zip_out:
        zip_out.writestr("wheels/a-1.0-py3-none-any.whl", b"x")

    gate.unzip_wheels(path_zip, dir_out=tmp_path / "out")

    assert (tmp_path / "out" / "a-1.0-py3-none-any.whl").is_file()


def test_loose_wheels_that_disagree_with_the_manifest_do_not_shadow_it(tmp_path: Path) -> None:
    """A leftover or half-extracted ``wheels/`` must not win over the verified payload."""
    path_manifest = tmp_path / "manifest.json"
    path_manifest.write_text('{"wheel_count": 2}', encoding="utf-8")

    assert gate._loose_wheels_match_manifest(path_manifest, list_loose=["a.whl"]) is False


def test_loose_wheels_matching_the_manifest_count_are_accepted(tmp_path: Path) -> None:
    """The negative control: a complete earlier assemble is still a no-op."""
    path_manifest = tmp_path / "manifest.json"
    path_manifest.write_text('{"wheel_count": 2}', encoding="utf-8")

    assert gate._loose_wheels_match_manifest(path_manifest, list_loose=["a.whl", "b.whl"]) is True


def test_a_zip_name_that_collides_with_a_part_is_refused(tmp_path: Path) -> None:
    """``zip_name`` pointing at an input would truncate it before it is read."""
    dir_wheels = _wheel_dir(tmp_path, "a-1.0-py3-none-any.whl")
    gate.pack_wheelhouse(_pack_args(tmp_path, dir_wheels=dir_wheels))
    path_manifest = tmp_path / "out" / "manifest.json"
    dict_manifest = json.loads(path_manifest.read_text(encoding="utf-8"))
    dict_manifest["zip_name"] = dict_manifest["parts"][0]["name"]
    path_manifest.write_text(json.dumps(dict_manifest), encoding="utf-8")

    with pytest.raises(SystemExit, match="collides"):
        gate.assemble_wheelhouse(
            argparse.Namespace(
                source=str(tmp_path / "out"),
                wheels_out=str(tmp_path / "wheels"),
                manifest=str(path_manifest),
            )
        )


def test_a_rebuild_with_fewer_parts_removes_the_stale_ones(tmp_path: Path) -> None:
    """Old ``wheelhouse.zip.NNN`` files would otherwise be copied to the target for nothing."""
    dir_wheels = _wheel_dir(tmp_path, "a-1.0-py3-none-any.whl")
    path_stale = tmp_path / "out" / "wheelhouse.zip.007"
    path_stale.parent.mkdir()
    path_stale.write_bytes(b"old")

    gate.pack_wheelhouse(_pack_args(tmp_path, dir_wheels=dir_wheels))

    assert not path_stale.exists()


def _assemble_args(tmp_path: Path) -> argparse.Namespace:
    """Build the ``assemble`` arguments for the payload ``_pack_args`` writes.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory holding ``out/`` (the payload) and receiving ``wheels/``.

    Returns
    -------
    argparse.Namespace
        Arguments as the CLI would parse them.
    """
    return argparse.Namespace(
        source=str(tmp_path / "out"),
        wheels_out=str(tmp_path / "wheels"),
        manifest=str(tmp_path / "out" / "manifest.json"),
    )


def test_pack_records_the_sorted_wheel_names_in_the_manifest(tmp_path: Path) -> None:
    """Names, not just a count, are what tell a stale ``wheels/`` from the payload."""
    dir_wheels = _wheel_dir(tmp_path, "b-2.0-py3-none-any.whl", "a-1.0-py3-none-any.whl")

    gate.pack_wheelhouse(_pack_args(tmp_path, dir_wheels=dir_wheels))

    dict_manifest = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert dict_manifest["wheel_names"] == ["a-1.0-py3-none-any.whl", "b-2.0-py3-none-any.whl"]


def test_loose_wheels_with_the_manifest_names_are_accepted(tmp_path: Path) -> None:
    """The negative control for the name comparison: the same set is still a no-op."""
    path_manifest = tmp_path / "manifest.json"
    path_manifest.write_text('{"wheel_count": 2, "wheel_names": ["a.whl", "b.whl"]}')

    assert gate._loose_wheels_match_manifest(path_manifest, list_loose=["b.whl", "a.whl"]) is True


def test_loose_wheels_with_other_names_but_the_same_count_are_rejected(tmp_path: Path) -> None:
    """Two wheels from a different lock must not pass for the two the manifest names."""
    path_manifest = tmp_path / "manifest.json"
    path_manifest.write_text('{"wheel_count": 2, "wheel_names": ["a.whl", "b.whl"]}')

    assert (
        gate._loose_wheels_match_manifest(path_manifest, list_loose=["a.whl", "stale.whl"])
        is False
    )


def test_stale_wheels_of_the_same_count_do_not_short_circuit_assemble(tmp_path: Path) -> None:
    """End to end: N stale wheels from another lock must not skip extracting the payload."""
    dir_wheels = _wheel_dir(tmp_path, "a-1.0-py3-none-any.whl", "b-2.0-py3-none-any.whl")
    gate.pack_wheelhouse(_pack_args(tmp_path, dir_wheels=dir_wheels))
    dir_out = tmp_path / "wheels"
    dir_out.mkdir()
    (dir_out / "x-9.0-py3-none-any.whl").write_bytes(b"stale")
    (dir_out / "y-9.0-py3-none-any.whl").write_bytes(b"stale")

    gate.assemble_wheelhouse(_assemble_args(tmp_path))

    assert (dir_out / "a-1.0-py3-none-any.whl").is_file()


def test_stale_wheels_are_removed_once_the_payload_is_verified(tmp_path: Path) -> None:
    """A wheel the manifest does not name must not survive next to the extracted payload."""
    dir_wheels = _wheel_dir(tmp_path, "a-1.0-py3-none-any.whl", "b-2.0-py3-none-any.whl")
    gate.pack_wheelhouse(_pack_args(tmp_path, dir_wheels=dir_wheels))
    dir_out = tmp_path / "wheels"
    dir_out.mkdir()
    (dir_out / "x-9.0-py3-none-any.whl").write_bytes(b"stale")

    gate.assemble_wheelhouse(_assemble_args(tmp_path))

    assert sorted(path_wheel.name for path_wheel in dir_out.glob("*.whl")) == [
        "a-1.0-py3-none-any.whl",
        "b-2.0-py3-none-any.whl",
    ]


def test_a_sha_mismatch_does_not_leave_the_reassembled_zip_behind(tmp_path: Path) -> None:
    """A failed archive left as ``wheelhouse.zip`` could later be extracted as unverified."""
    # one-assert-ok: the raises block IS the failure under test; the assert is its cleanup
    dir_wheels = _wheel_dir(tmp_path, "a-1.0-py3-none-any.whl")
    gate.pack_wheelhouse(_pack_args(tmp_path, dir_wheels=dir_wheels))
    path_manifest = tmp_path / "out" / "manifest.json"
    dict_manifest = json.loads(path_manifest.read_text(encoding="utf-8"))
    dict_manifest["zip_sha256"] = "0" * 64
    path_manifest.write_text(json.dumps(dict_manifest), encoding="utf-8")

    with pytest.raises(SystemExit, match="sha256 mismatch"):
        gate.assemble_wheelhouse(_assemble_args(tmp_path))

    assert not (tmp_path / "out" / "wheelhouse.zip").exists()


def test_a_failed_extraction_does_not_leave_the_reassembled_zip_behind(tmp_path: Path) -> None:
    """The sha matches but the bytes are no zip, so extraction fails after reassembly."""
    # one-assert-ok: the raises block IS the failure under test; the assert is its cleanup
    path_part = tmp_path / "out" / "wheelhouse.zip.000"
    path_part.parent.mkdir()
    path_part.write_bytes(b"not a zip")
    dict_manifest = _manifest(
        [{"name": path_part.name, "sha256": gate.sha256_of(path_part)}],
        zip_sha256=gate.sha256_of(path_part),
    )
    (tmp_path / "out" / "manifest.json").write_text(json.dumps(dict_manifest), encoding="utf-8")

    with pytest.raises(zipfile.BadZipFile):
        gate.assemble_wheelhouse(_assemble_args(tmp_path))

    assert not (tmp_path / "out" / "wheelhouse.zip").exists()


_PIP_SHIM = """#!/usr/bin/env bash
if [[ "$1 $2 $3" == "-m pip download" ]]; then
	shift 3
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--dest) dir_dest="$2"; shift 2 ;;
		-r) path_req="$2"; shift 2 ;;
		*) shift ;;
		esac
	done
	while read -r str_line; do
		str_name="${str_line%%[<>=!~; ]*}"
		[[ -n "$str_name" ]] || continue
		str_stem="${str_name//-/_}"
		cp "${STUB_INDEX:-/nonexistent}"/"$str_stem"-*.whl "$dir_dest"/ 2>/dev/null && continue
		"@PY@" -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1], "w").writestr(sys.argv[2], "Name: x\\n")' \\
			"$dir_dest/$str_stem-1.0-py3-none-any.whl" "$str_stem-1.0.dist-info/METADATA"
	done <"$path_req"
	exit 0
fi
exec "@PY@" "$@"
"""

_POETRY_REQUIRES = (
    'Requires-Dist: pywin32-ctypes>=0.2 ; sys_platform == "win32"',
    'Requires-Dist: secretstorage>=3 ; sys_platform == "linux"',
)


def _stub_wheel(path_index: Path, *, str_stem: str, list_requires: tuple[str, ...]) -> None:
    """Write a minimal wheel whose METADATA carries the given ``Requires-Dist`` lines.

    Parameters
    ----------
    path_index : Path
        Directory acting as the stubbed package index.
    str_stem : str
        Wheel file stem, e.g. ``poetry-2.4.0-py3-none-any``.
    list_requires : tuple of str
        ``Requires-Dist`` header lines.
    """
    str_dist = str_stem.rsplit("-", 3)[0]
    str_metadata = "\n".join(["Name: x", *list_requires, ""])
    with zipfile.ZipFile(path_index / f"{str_stem}.whl", "w") as zip_out:
        zip_out.writestr(f"{str_dist}.dist-info/METADATA", str_metadata)


def _build_for(tmp_path: Path, *, dict_target: dict[str, str]) -> str:
    """Run ``build_wheelhouse.sh build`` against a stubbed pip/index and return the manifest.

    Parameters
    ----------
    tmp_path : Path
        Scratch directory.
    dict_target : dict of str to str
        ``WHEELHOUSE_*`` variables selecting the target environment.

    Returns
    -------
    str
        The text of the packed ``manifest.json``.
    """
    path_project = tmp_path / "proj"
    shutil.copytree(_LIB.parent, path_project / "bin")
    shutil.copy(_LIB.parents[1] / "requirements.txt", path_project / "requirements.txt")
    (path_project / "bin" / "export_deps.sh").write_text(
        '#!/usr/bin/env bash\necho "requests==2.32.0" >"$OUTPUT_FILE"\n'
    )
    path_index = tmp_path / "index"
    path_index.mkdir()
    _stub_wheel(path_index, str_stem="poetry-2.4.0-py3-none-any", list_requires=_POETRY_REQUIRES)
    _stub_wheel(path_index, str_stem="pywin32_ctypes-0.2.3-py3-none-any", list_requires=())
    _stub_wheel(path_index, str_stem="secretstorage-3.3.3-py3-none-any", list_requires=())
    path_shims = tmp_path / "shims"
    path_shims.mkdir()
    path_shim = path_shims / "python3"
    path_shim.write_text(_PIP_SHIM.replace("@PY@", sys.executable))
    path_shim.chmod(0o755)
    (path_shims / "python").symlink_to(path_shim)
    (path_shims / "py").symlink_to(path_shim)
    path_out = tmp_path / "out"

    subprocess.run(  # noqa: S603
        [
            shutil.which("bash") or "bash",
            str(path_project / "bin" / "build_wheelhouse.sh"),
            "build",
        ],
        check=True,
        capture_output=True,
        env={
            "PATH": f"{path_shims}:/usr/bin:/bin",
            "WHEELHOUSE_DIR": str(path_out),
            "STUB_INDEX": str(path_index),
            "WHEELHOUSE_TARGET_PYTHON_VERSION": "3.12.2",
            **dict_target,
        },
    )
    return (path_out / "manifest.json").read_text()


_LINUX_TARGET = {
    "WHEELHOUSE_PIP_PLATFORM": "manylinux2014_x86_64",
    "WHEELHOUSE_TARGET_SYS_PLATFORM": "linux",
    "WHEELHOUSE_TARGET_PLATFORM_MACHINE": "x86_64",
}
_WINDOWS_TARGET = {
    "WHEELHOUSE_PIP_PLATFORM": "win_amd64",
    "WHEELHOUSE_TARGET_SYS_PLATFORM": "win32",
    "WHEELHOUSE_TARGET_PLATFORM_MACHINE": "AMD64",
}
_SKIP_NO_SCRIPT = pytest.mark.skipif(
    not (_LIB.parent / "build_wheelhouse.sh").exists(),
    reason="this tier does not ship bin/build_wheelhouse.sh",
)


@_SKIP_NO_SCRIPT
def test_wheelhouse_includes_poetry_wheel(tmp_path: Path) -> None:
    """A lock with no Poetry still yields a Poetry wheel in the packed manifest."""
    str_manifest = _build_for(tmp_path, dict_target=_LINUX_TARGET)

    assert "poetry-2.4.0-py3-none-any.whl" in str_manifest


@_SKIP_NO_SCRIPT
def test_wheelhouse_includes_a_transitive_dependency_marked_for_the_target(
    tmp_path: Path,
) -> None:
    """A win32-only dependency of Poetry is packed for a Windows target built on Linux.

    pip evaluates the markers of transitive dependencies against the builder, so the
    ``sys_platform == "win32"`` requirement was dropped (blueprintx#1302).
    """
    str_manifest = _build_for(tmp_path, dict_target=_WINDOWS_TARGET)

    assert "pywin32_ctypes-0.2.3-py3-none-any.whl" in str_manifest


@_SKIP_NO_SCRIPT
def test_wheelhouse_omits_a_transitive_dependency_marked_for_another_platform(
    tmp_path: Path,
) -> None:
    """A linux-only dependency of Poetry is not packed for a Windows target."""
    str_manifest = _build_for(tmp_path, dict_target=_WINDOWS_TARGET)

    assert "secretstorage" not in str_manifest


def test_close_keeps_only_the_dependencies_whose_marker_holds_for_the_target(
    tmp_path: Path,
) -> None:
    """``close`` reads a wheel's ``Requires-Dist`` and evaluates it for the TARGET."""
    _stub_wheel(tmp_path, str_stem="poetry-2.4.0-py3-none-any", list_requires=_POETRY_REQUIRES)
    (tmp_path / "seed.txt").write_text("poetry>=2.4\n", encoding="utf-8")
    args = argparse.Namespace(
        seed=str(tmp_path / "seed.txt"),
        wheels_dir=str(tmp_path),
        out=str(tmp_path / "out.txt"),
        target_python_version="3.12.2",
        target_sys_platform="win32",
        target_platform_machine="AMD64",
        target_implementation="cpython",
    )

    gate.close_requirements(args)

    assert (tmp_path / "out.txt").read_text(encoding="utf-8").splitlines() == [
        "poetry>=2.4",
        "pywin32-ctypes>=0.2",
    ]
