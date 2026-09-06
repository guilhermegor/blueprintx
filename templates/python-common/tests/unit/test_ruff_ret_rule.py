"""Witness for the `RET` (flake8-return) rule family adopted in ``ruff.toml`` (blueprintx#426).

**Why this exists.** `RET505` (unnecessary `else` after `return`) was measured at 0 findings
across `src/ bin/ tests/ optional/` at adoption time — the codebase already writes early
returns everywhere. A gate that has never fired is indistinguishable from a gate that never
ran, so a should-fail witness is the only thing that tells the two apart. This test invokes
``ruff`` directly (not the shipped config, which also enables `ANN`/`D`/… and would drown the
signal in unrelated findings on a two-line fixture) with `--isolated --select RET505` against
two synthetic fixtures: one that MUST fail, one that MUST pass.
"""

from pathlib import Path
import shutil
import subprocess

import pytest


_BAD_SOURCE = "def choose(flag: bool) -> int:\n\tif flag:\n\t\treturn 1\n\telse:\n\t\treturn 2\n"
_GOOD_SOURCE = "def choose(flag: bool) -> int:\n\tif flag:\n\t\treturn 1\n\treturn 2\n"

# Resolved once at collection time; branch lives in the `skipif` marker below, never in the
# helper, to keep `_run_ruff_ret505` at the `tests/` complexity ceiling of 1.
_STR_RUFF = shutil.which("ruff")


def _run_ruff_ret505(path_file: Path) -> subprocess.CompletedProcess[str]:
	"""Run ``ruff check --isolated --select RET505`` against a single file.

	Parameters
	----------
	path_file : pathlib.Path
		The Python source file to check.

	Returns
	-------
	subprocess.CompletedProcess[str]
		The completed ruff invocation (exit code + captured output).
	"""
	list_argv = [
		str(_STR_RUFF),
		"check",
		"--isolated",
		"--select",
		"RET505",
		"--output-format",
		"concise",
		str(path_file),
	]
	return subprocess.run(list_argv, capture_output=True, text=True, check=False)  # noqa: S603


# --------------------------
# 🔴 The negative control — the gate must be able to FAIL
# --------------------------


@pytest.mark.skipif(_STR_RUFF is None, reason="ruff is not on PATH")
def test_ret505_flags_else_after_return(tmp_path: Path) -> None:
	"""An `if: return … else: return …` shape must be rejected by RET505."""
	path_file = tmp_path / "bad.py"
	path_file.write_text(_BAD_SOURCE, encoding="utf-8")
	cls_result = _run_ruff_ret505(path_file)
	assert cls_result.returncode == 1
	assert "RET505" in cls_result.stdout


# --------------------------
# Tests
# --------------------------


@pytest.mark.skipif(_STR_RUFF is None, reason="ruff is not on PATH")
def test_ret505_allows_early_return(tmp_path: Path) -> None:
	"""An early-return shape (no `else` after `return`) must pass RET505 clean."""
	path_file = tmp_path / "good.py"
	path_file.write_text(_GOOD_SOURCE, encoding="utf-8")
	cls_result = _run_ruff_ret505(path_file)
	assert cls_result.returncode == 0
	assert "RET505" not in cls_result.stdout
