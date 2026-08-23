"""Unit tests for the per-layer import gate (``bin/check_layer_imports.py``).

Every case is built from a shape **measured in a real project**, not invented: a vendor at the
top of ``model/``, the same vendor deferred into a function under an ``ImportError`` guard, and
pandas called as an API rather than named as a type.

The should-PASS cases matter as much as the should-fail ones. A gate exercised only on what it
rejects has been shown to reject, not to discriminate — and this gate's whole design rests on a
distinction (annotation vs API) that a blunter rule would flatten.
"""

import importlib.util
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest


# --------------------------
# Module Utilities
# --------------------------


def _load_gate() -> ModuleType:
	"""Import ``bin/check_layer_imports.py`` as a module.

	Returns
	-------
	ModuleType
		The loaded gate module.
	"""
	path_gate = Path(__file__).resolve().parents[2] / "bin" / "check_layer_imports.py"
	cls_spec = importlib.util.spec_from_file_location("_check_layer_imports", path_gate)
	assert cls_spec is not None and cls_spec.loader is not None
	cls_module = importlib.util.module_from_spec(cls_spec)
	cls_spec.loader.exec_module(cls_module)
	return cls_module


_POLICY = {
	"first_party_extra": ["chassis"],
	"annotation_only": {"pandas": "Build a frame with utils.frames.from_cursor."},
	"layers": {
		"model": {"allow": {}},
		"utils": {"allow": {"pandas": "the seam layer owns the pandas surface"}},
	},
}
_FIRST_PARTY = {"src", "model", "utils", "config", "view", "controller", "chassis"}


def _problems(tmp_path: Path, str_source: str, str_layer: str = "model") -> list[str]:
	"""Run the gate over one synthetic module and return its problems.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway directory.
	str_source : str
		The module source to check.
	str_layer : str, optional
		The layer the file is treated as belonging to, by default ``"model"``.

	Returns
	-------
	list of str
		The problems the gate reported.
	"""
	cls_gate = _load_gate()
	path_file = tmp_path / "probe.py"
	path_file.write_text(str_source, encoding="utf-8")
	return cls_gate.find_file_problems(path_file, str_layer, _POLICY, _FIRST_PARTY)


# --------------------------
# should-FAIL
# --------------------------


def test_vendor_at_the_top_of_a_layer_is_rejected(tmp_path: Path) -> None:
	"""The plain case: a domain vendor imported straight into ``model/``.

	Measured in two independent projects (blueprintx#171).
	"""
	list_problems = _problems(tmp_path, "from filings_cvm.submission import Submission\n")
	assert len(list_problems) == 1
	assert "filings_cvm" in list_problems[0]


def test_vendor_deferred_into_a_function_is_still_rejected(tmp_path: Path) -> None:
	"""Deferring the import buys no exemption, even under an ``ImportError`` guard.

	This is the shape the gate exists for. The guard answers *how to degrade when the vendor
	is missing*; it says nothing about *why the layer knows the vendor at all*, and the
	coupling is identical to a top-level import. The optional-dependency pattern is fine — in
	the ``utils/`` seam that owns the dependency, which then returns the degraded result.
	"""
	str_source = (
		"def read_portal() -> None:\n"
		'\t"""Read."""\n'
		"\ttry:\n"
		"\t\tfrom filings_cvm.ingestion import fi\n"
		"\texcept ImportError:\n"
		"\t\treturn None\n"
		"\treturn fi\n"
	)
	list_problems = _problems(tmp_path, str_source)
	assert len(list_problems) == 1
	assert "filings_cvm" in list_problems[0]
	# The message must name the evasion, since this is the form that passed unnoticed.
	assert "inside a function" in list_problems[0]


def test_annotation_only_vendor_called_as_an_api_is_rejected(tmp_path: Path) -> None:
	"""``pandas`` is the layers' vocabulary, not an API they may call."""
	str_source = (
		"import pandas as pd\n"
		"def load() -> pd.DataFrame:\n"
		'\t"""Load."""\n'
		'\treturn pd.read_sql("SELECT 1", None)\n'
	)
	list_problems = _problems(tmp_path, str_source)
	assert len(list_problems) == 1
	assert "TYPE only" in list_problems[0]
	# The remedy travels with the finding.
	assert "utils.frames.from_cursor" in list_problems[0]


# --------------------------
# should-PASS
# --------------------------


def test_annotation_only_vendor_used_as_a_type_passes(tmp_path: Path) -> None:
	"""The shape the reference model now ships: pandas named, never called."""
	str_source = (
		"from __future__ import annotations\n"
		"from typing import TYPE_CHECKING\n"
		"from utils.frames import from_cursor\n"
		"if TYPE_CHECKING:\n"
		"\timport pandas as pd\n"
		"def load(cls_cursor: object) -> pd.DataFrame:\n"
		'\t"""Load."""\n'
		'\treturn from_cursor(cls_cursor, {"id": "int64"})\n'
	)
	assert _problems(tmp_path, str_source) == []


def test_the_seam_layer_may_use_the_vendor_freely(tmp_path: Path) -> None:
	"""``utils/`` is where vendors are SUPPOSED to live — the gate must not fight its own fix."""
	str_source = 'import pandas as pd\ndef f() -> object:\n\t"""F."""\n\treturn pd.DataFrame()\n'
	assert _problems(tmp_path, str_source, str_layer="utils") == []


def test_the_layout_shim_is_first_party_not_a_vendor(tmp_path: Path) -> None:
	"""``chassis`` is our own code under the DDD layout, reached through the typing shim.

	Without ``first_party_extra`` this reported all 23 shipped helpers as vendor violations —
	a gate whose first run is 23 false positives is a gate nobody enables.
	"""
	str_source = (
		"try:\n"
		"\tfrom utils.typing import type_checker\n"
		"except ModuleNotFoundError:\n"
		"\tfrom chassis.typing import type_checker\n"
	)
	assert _problems(tmp_path, str_source, str_layer="utils") == []


def test_stdlib_is_unrestricted_in_every_layer(tmp_path: Path) -> None:
	"""The standard library carries no coupling risk and is never gated."""
	assert _problems(tmp_path, "import json\nfrom pathlib import Path\n") == []


@pytest.mark.parametrize("str_layer", ["model", "view", "controller"])
def test_one_statement_binding_many_names_is_one_violation(tmp_path: Path, str_layer: str) -> None:
	"""A single import binding several names must not report once per name.

	A gate that multiplies its own findings trains people to skim the output.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway directory.
	str_layer : str
		The layer the synthetic module is treated as belonging to.
	"""
	list_problems = _problems(tmp_path, "from filings_cvm import a, b, c\n", str_layer)
	assert len(list_problems) == 1


def test_a_module_directly_under_src_is_not_skipped(tmp_path: Path) -> None:
	"""An entrypoint at ``src/main.py`` is checked like any other file.

	It has no directory to name its layer, and an earlier revision skipped exactly those
	files — so ``src/main.py`` could import any vendor and bypass the policy entirely. The
	place a bypass is easiest is not the place to stop looking.
	"""
	cls_gate = _load_gate()
	path_src = tmp_path / "src"
	path_src.mkdir()
	(path_src / "main.py").write_text("from filings_cvm import fi\n", encoding="utf-8")
	(tmp_path / ".layer-policy.yaml").write_text(
		"layers:\n  __root__:\n    allow: {}\n", encoding="utf-8"
	)

	dict_policy = cls_gate.load_policy(tmp_path)
	list_problems = cls_gate.find_file_problems(
		path_src / "main.py", cls_gate._ROOT_LAYER, dict_policy, {"src"}
	)
	assert len(list_problems) == 1
	assert "filings_cvm" in list_problems[0]


# --------------------------
# main() — the gate must never pass by not looking (blueprintx#139)
# --------------------------


def _run_main(path_root: Path) -> tuple[int, str]:
	"""Run the gate's ``main()`` with ``path_root`` as the working directory.

	Parameters
	----------
	path_root : pathlib.Path
		Directory to treat as the project root.

	Returns
	-------
	tuple of (int, str)
		The exit code and everything printed.
	"""
	# Constant, trusted argv. Invoked as a subprocess so the working directory and the
	# printed output are the real ones main sees.
	cls_run = subprocess.run(  # noqa: S603
		[
			sys.executable,
			str(Path(__file__).resolve().parents[2] / "bin" / "check_layer_imports.py"),
		],
		cwd=path_root,
		capture_output=True,
		text=True,
		check=False,
	)
	return cls_run.returncode, cls_run.stdout + cls_run.stderr


def _seed_project(path_root: Path, str_module: str = "import os\n") -> None:
	"""Build a minimal project tree holding one module under ``src/model/``.

	Writing the policy is left to the caller: whether one exists is the very thing several of
	these tests vary, so making it a parameter would hide the difference inside a helper.

	Parameters
	----------
	path_root : pathlib.Path
		Directory to build in.
	str_module : str, optional
		Source of the single module placed under ``src/model/``.

	Returns
	-------
	None
	"""
	(path_root / "src" / "model").mkdir(parents=True, exist_ok=True)
	(path_root / "src" / "model" / "probe.py").write_text(str_module, encoding="utf-8")


_MINIMAL_POLICY = "layers:\n  model:\n    allow: {}\n"


def test_modules_with_no_policy_file_FAIL_rather_than_pass_silently(tmp_path: Path) -> None:
	"""⚠️ The negative control for the defect this fixed.

	The gate used to ``return 0`` in silence when no policy was present, so three of the five
	Python tiers shipped with NO import boundary at all while their CI stayed green. A gate
	reporting its own blindness as OK is the failure mode this repo writes gates to prevent.
	"""
	_seed_project(tmp_path)

	int_code, str_out = _run_main(tmp_path)

	assert int_code == 1
	assert ".layer-policy.yaml" in str_out
	assert "no import boundary" in str_out


def test_a_tree_with_no_modules_and_no_policy_is_not_a_failure(tmp_path: Path) -> None:
	"""The positive control: nothing to check is not the same as failing to check."""
	(tmp_path / "src").mkdir()

	int_code, str_out = _run_main(tmp_path)

	assert int_code == 0
	assert "nothing to do" in str_out


def test_a_clean_tree_prints_what_it_checked(tmp_path: Path) -> None:
	"""A silent gate cannot be told from an absent one, so success names the count."""
	_seed_project(tmp_path)
	(tmp_path / ".layer-policy.yaml").write_text(_MINIMAL_POLICY, encoding="utf-8")

	int_code, str_out = _run_main(tmp_path)

	assert int_code == 0
	assert "module(s) checked" in str_out


def test_layers_nested_inside_a_package_resolve_via_src_prefix_depth(tmp_path: Path) -> None:
	"""lib-minimal nests its layers as ``src/<pkg>/_internal/<layer>/``.

	Without the prefix the layer resolves to the PACKAGE NAME, matches no policy entry, and
	deny-by-default rejects the whole tree for the wrong reason — which is how one engine
	serving five layouts quietly stops serving one of them.
	"""
	path_deep = tmp_path / "src" / "mypkg" / "_internal" / "model"
	path_deep.mkdir(parents=True)
	(path_deep / "probe.py").write_text("import os\n", encoding="utf-8")
	(tmp_path / ".layer-policy.yaml").write_text(
		"src_prefix_depth: 2\n" + _MINIMAL_POLICY, encoding="utf-8"
	)

	int_code, str_out = _run_main(tmp_path)

	assert int_code == 0, str_out
	assert "module(s) checked" in str_out


def test_the_same_nested_tree_without_the_prefix_is_rejected(tmp_path: Path) -> None:
	"""The paired control: drop the prefix and the layer no longer resolves.

	Without this, the test above would pass against an engine that ignores the setting.
	"""
	path_deep = tmp_path / "src" / "mypkg" / "_internal" / "model"
	path_deep.mkdir(parents=True)
	(path_deep / "probe.py").write_text("import pandas\n", encoding="utf-8")
	(tmp_path / ".layer-policy.yaml").write_text(_MINIMAL_POLICY, encoding="utf-8")

	int_code, _ = _run_main(tmp_path)

	assert int_code == 1
