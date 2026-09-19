"""Unit tests for the template-drift gate (blueprintx#109; offline, no scaffold run).

The gate derives what a project MUST contain by parsing the shared scaffold lib's ``cp``
commands, so its should-fail witnesses are about that parse being complete and honest:
a wrapped ``cp`` must not be skipped, and a conditional ``cp`` must not be demanded from a
project that legitimately opted out.
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType


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

_LIB = '''scaffold_copy_common_templates() {
	cp "$COMMON_TEMPLATE_ROOT/plain.txt" "$str_project_path/plain.txt"
	cp "$COMMON_TEMPLATE_ROOT/tests/unit/test_wrapped.py" \\
		"$str_project_path/tests/unit/test_wrapped.py"
	if [[ "${INCLUDE_REVIEW_BOT_ROSTER:-true}" == "true" ]]; then
		cp "$COMMON_TEMPLATE_ROOT/.review-bots.yaml" "$str_project_path/.review-bots.yaml"
	fi
	cp "$COMMON_TEMPLATE_ROOT/after.txt" "$str_project_path/after.txt"
}
'''


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


# ------------------------------------------------
# A wrapped `cp` is still a `cp` (blueprintx#109)
# ------------------------------------------------


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


# --------------------------------------------------------
# A conditional `cp` is not an unconditional requirement
# --------------------------------------------------------


def test_a_conditional_cp_is_not_required_by_default(tmp_path: Path) -> None:
	"""`.review-bots.yaml` is copied only when the scaffold answered yes (blueprintx#374)."""
	set_required = gate.required_relpaths(_blueprintx_root(tmp_path))

	assert ".review-bots.yaml" not in set_required


def test_the_conditional_destination_is_reported_as_conditional(tmp_path: Path) -> None:
	"""It is excluded because it is conditional, not because it was never parsed."""
	str_lib = (tmp_path / gate._SCAFFOLD_LIB_RELPATH).parent
	_blueprintx_root(tmp_path)
	str_spliced = gate._RE_LINE_CONTINUATION.sub(
		" ", (tmp_path / gate._SCAFFOLD_LIB_RELPATH).read_text(encoding="utf-8")
	)
	assert str_lib.exists()
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
