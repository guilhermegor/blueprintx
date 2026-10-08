"""Unit tests for the template-drift gate (blueprintx#109; offline, no scaffold run).

The gate derives what a project MUST contain by parsing the shared scaffold lib's ``cp``
commands, so its should-fail witnesses are about that parse being complete and honest:
a wrapped ``cp`` must not be skipped, and a conditional ``cp`` must not be demanded from a
project that legitimately opted out.
"""

import importlib.util
from pathlib import Path
import subprocess
import sys
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


gate = _load("check_template_drift")

_LIB = """scaffold_copy_common_templates() {
	cp "$COMMON_TEMPLATE_ROOT/plain.txt" "$str_project_path/plain.txt"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_wrapped.py" \\
		"$str_project_path/tests/unit/test_wrapped.py"
	if [[ "${INCLUDE_REVIEW_BOT_ROSTER:-true}" == "true" ]]; then
		cp "$COMMON_TEMPLATE_ROOT/.review-bots.yaml" "$str_project_path/.review-bots.yaml"
	fi
	cp "$COMMON_TEMPLATE_ROOT/after.txt" "$str_project_path/after.txt"
}
"""


def _blueprintx_root(path_tmp: Path) -> Path:
    """Write a synthetic BlueprintX checkout holding just the shared scaffold lib.

    Parameters
    ----------
    path_tmp : pathlib.Path
            A temporary directory to build under.

    Returns
    -------
    pathlib.Path
            The synthetic root, suitable for ``required_relpaths``.
    """
    path_lib = path_tmp / gate._SCAFFOLD_LIB_RELPATH
    path_lib.parent.mkdir(parents=True, exist_ok=True)
    path_lib.write_text(_LIB, encoding="utf-8")
    return path_tmp


def test_a_cp_split_over_two_lines_is_still_required(tmp_path: Path) -> None:
    """The regex stopped at the backslash, so a wrapped destination was never required.

    Measured on the real lib when this was found: 23 destinations parsed against 52
    actually copied — the drift doctor was blind to 29 of the files it exists to police,
    and reported a clean comparison while doing it.
    """
    set_required = gate.required_relpaths(_blueprintx_root(tmp_path))

    assert "tests/unit/test_wrapped.py" in set_required


def test_a_plain_cp_after_a_wrapped_one_is_not_swallowed(tmp_path: Path) -> None:
    """The negative control for the splice: it must not consume the following command."""
    set_required = gate.required_relpaths(_blueprintx_root(tmp_path))

    assert {"plain.txt", "after.txt"} <= set_required


def test_a_conditional_cp_is_not_required_by_default(tmp_path: Path) -> None:
    """`.review-bots.yaml` is copied only when the scaffold answered yes (blueprintx#374)."""
    set_required = gate.required_relpaths(_blueprintx_root(tmp_path))

    assert ".review-bots.yaml" not in set_required


def test_the_conditional_destination_is_reported_as_conditional(tmp_path: Path) -> None:
    """It is excluded because it is conditional, not because it was never parsed."""
    _blueprintx_root(tmp_path)
    str_spliced = gate._RE_LINE_CONTINUATION.sub(
        " ", (tmp_path / gate._SCAFFOLD_LIB_RELPATH).read_text(encoding="utf-8")
    )

    assert gate.conditional_relpaths(str_spliced) == {".review-bots.yaml"}


def test_provenance_records_the_roster_choice(tmp_path: Path) -> None:
    """The stamp is what lets the checker recover an opt-out instead of guessing."""
    (tmp_path / gate._PROVENANCE_FILENAME).write_text(
        "tier: lib-minimal\nreview_bot_roster: false\n", encoding="utf-8"
    )

    assert gate.review_bot_roster_enabled(tmp_path) is False


def test_a_project_predating_the_stamp_reads_as_unknown(tmp_path: Path) -> None:
    """`None`, never `False` — the caller must not assume either answer for old projects."""
    (tmp_path / gate._PROVENANCE_FILENAME).write_text("tier: lib-minimal\n", encoding="utf-8")

    assert gate.review_bot_roster_enabled(tmp_path) is None


def test_a_one_line_if_does_not_make_later_copies_conditional() -> None:
    """`if ...; then cp ...; fi` closes on its own line; the depth counter must not leak."""
    str_lib = (
        'if [ "$x" ]; then cp "$COMMON_TEMPLATE_ROOT/a.txt" "$str_project_path/a.txt"; fi\n'
        'cp "$COMMON_TEMPLATE_ROOT/b.txt" "$str_project_path/b.txt"\n'
    )

    assert gate.conditional_relpaths(str_lib) == {"a.txt"}


def test_bytecode_under_a_copied_directory_is_not_required(tmp_path: Path) -> None:
    """A `__pycache__` in the checkout's bin/ is an untracked artifact, never a template file."""
    path_root = _blueprintx_root(tmp_path)
    path_cache = path_root / gate._COMMON_TEMPLATE_RELPATH / "bin" / "__pycache__"
    path_cache.mkdir(parents=True)
    (path_cache / "x.cpython-312.pyc").write_bytes(b"")

    set_required = gate.required_relpaths(path_root)

    assert not any("__pycache__" in str_rel for str_rel in set_required)


def test_roster_opt_in_against_a_checkout_without_the_lib_skips_instead_of_crashing(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The roster add-back re-read the lib unguarded and raised FileNotFoundError."""
    path_project = tmp_path / "project"
    path_project.mkdir()
    (path_project / gate._PROVENANCE_FILENAME).write_text(
        "tier: lib-minimal\nreview_bot_roster: true\n", encoding="utf-8"
    )
    path_empty_checkout = tmp_path / "checkout"
    path_empty_checkout.mkdir()

    int_code = gate.main(
        ["--root", str(path_project), "--blueprintx-root", str(path_empty_checkout)]
    )

    assert int_code == 0
    assert "SKIPPED" in capsys.readouterr().out


def test_the_equals_form_of_a_flag_is_honoured(tmp_path: Path) -> None:
    """`--root=x` used to be ignored silently, so the check ran against cwd without saying so."""
    path_root, _ = gate._parse_args([f"--root={tmp_path}"])

    assert path_root == tmp_path.resolve()


def test_a_copy_from_the_language_agnostic_root_is_required() -> None:
    """`$SHARED_TEMPLATE_ROOT` (templates/common/) copies are shipped to every project too."""
    str_line = 'cp "$SHARED_TEMPLATE_ROOT/bin/ship.sh" "$str_project_path/bin/ship.sh"'

    assert gate._cp_destinations(str_line) == {"bin/ship.sh"}


def test_a_one_line_and_chain_copy_is_conditional() -> None:
    """`[[ ... ]] && cp ...` is a guarded copy; demanding it unconditionally is a false report."""
    str_lib = '[[ "$x" == y ]] && cp "$COMMON_TEMPLATE_ROOT/a.txt" "$str_project_path/a.txt"\n'

    assert gate.conditional_relpaths(str_lib) == {"a.txt"}


def test_a_case_arm_copy_is_conditional_and_closes_at_esac() -> None:
    """A `case` arm is conditional; `esac` must close it so later copies stay required."""
    str_lib = (
        'case "$t" in\n'
        '  a) cp "$COMMON_TEMPLATE_ROOT/a.txt" "$str_project_path/a.txt" ;;\n'
        "esac\n"
        'cp "$COMMON_TEMPLATE_ROOT/b.txt" "$str_project_path/b.txt"\n'
    )

    assert gate.conditional_relpaths(str_lib) == {"a.txt"}


def test_braced_variable_names_are_parsed() -> None:
    """`${COMMON_TEMPLATE_ROOT}` is the same copy as `$COMMON_TEMPLATE_ROOT`."""
    str_line = 'cp "${COMMON_TEMPLATE_ROOT}/a.txt" "${str_project_path}/a.txt"'

    assert gate._cp_destinations(str_line) == {"a.txt"}


@pytest.mark.parametrize("str_flag", ["-a", "-R", "-p"])
def test_cp_flags_other_than_bare_are_parsed(str_flag: str) -> None:
    """`cp -a`/`-R`/`-p` of a single file is still a copy the scaffold performs."""
    str_line = f'cp {str_flag} "$COMMON_TEMPLATE_ROOT/a.txt" "$str_project_path/a.txt"'

    assert gate._cp_destinations(str_line) == {"a.txt"}


def test_a_recursive_directory_copy_without_trailing_dot_is_required(tmp_path: Path) -> None:
    """`cp -r "$SRC/dir" "$DST/dir"` (no `/.`) ships every file under dir."""
    path_root = _blueprintx_root(tmp_path)
    path_lib = path_root / gate._SCAFFOLD_LIB_RELPATH
    path_lib.write_text(
        'cp -r "$COMMON_TEMPLATE_ROOT/.specs" "$str_project_path/.specs"\n', encoding="utf-8"
    )
    path_dir = path_root / gate._COMMON_TEMPLATE_RELPATH / ".specs"
    path_dir.mkdir(parents=True)
    (path_dir / "a.md").write_text("x", encoding="utf-8")

    assert gate.required_relpaths(path_root) == {".specs/a.md"}


def test_roster_opt_in_adds_back_only_the_roster_guarded_copies() -> None:
    """A copy guarded by some OTHER condition must not become required by the roster choice."""
    str_lib = (
        'if [[ "${INCLUDE_REVIEW_BOT_ROSTER:-true}" == "true" ]]; then\n'
        '  cp "$COMMON_TEMPLATE_ROOT/r.yaml" "$str_project_path/r.yaml"\n'
        "fi\n"
        'if [[ "$tier" == "x" ]]; then\n'
        '  cp "$COMMON_TEMPLATE_ROOT/t.txt" "$str_project_path/t.txt"\n'
        "fi\n"
    )

    assert gate.conditional_relpaths(str_lib, "INCLUDE_REVIEW_BOT_ROSTER") == {"r.yaml"}


def test_untracked_files_in_a_git_checkout_are_not_required(tmp_path: Path) -> None:
    """Only tracked files are template files; a stray untracked one is never 'missing'."""
    path_root = _blueprintx_root(tmp_path)
    path_lib = path_root / gate._SCAFFOLD_LIB_RELPATH
    path_lib.write_text(
        'cp -r "$COMMON_TEMPLATE_ROOT/bin/." "$str_project_path/bin"\n', encoding="utf-8"
    )
    path_bin = path_root / gate._COMMON_TEMPLATE_RELPATH / "bin"
    path_bin.mkdir(parents=True)
    (path_bin / "tracked.sh").write_text("x", encoding="utf-8")
    (path_bin / "stray.log").write_text("x", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=path_root, check=True)  # noqa: S603, S607
    subprocess.run(  # noqa: S603, S607
        ["git", "add", "-f", str(path_bin / "tracked.sh")],  # noqa: S607
        cwd=path_root,
        check=True,
    )

    assert gate.required_relpaths(path_root) == {"bin/tracked.sh"}


def test_a_flag_without_a_value_fails_loudly() -> None:
    """A valueless `--root` must not silently fall back to cwd."""
    with pytest.raises(SystemExit):
        gate._parse_args(["--root"])
