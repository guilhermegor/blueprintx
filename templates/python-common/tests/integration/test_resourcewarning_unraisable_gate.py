"""Should-fail witness for the ResourceWarning/unraisable pytest.ini gate (blueprintx#294).

A ``ResourceWarning`` raised while an object is finalised (``__del__``) is *unraisable* —
Python cannot propagate it out of a finalizer, so pytest catches it and re-emits it as
``pytest.PytestUnraisableExceptionWarning`` instead. ``error::ResourceWarning`` alone never
sees a warning of that re-emitted class, so a file handle leaked by a garbage-collected
object (the #223 shape) would pass silently. These tests prove, against the shipped
``pytest.ini`` itself rather than a copy, that the second filter line closes that gap and
that it does not turn an ordinary clean run red — by spawning a real ``pytest`` subprocess,
the same technique ``test_bin_scripts.py`` uses for a `bin/` script, which is why this test
lives here rather than in ``tests/unit/``.

⚠️ **Known gap, disclosed rather than hidden**: unlike ``test_bin_scripts.py``, this file is
not yet copied into a generated project by any ``bin/scaffold/python_*.sh`` — the only two
places that could wire it in (``bin/lib/scaffold_python_templates.sh`` and every
``bin/scaffold/python_*.sh``) were each already claimed by other open pull requests
(blueprintx#296, #316, #319) at the time this test was added. It runs, and is verified,
against the template source in this repo; wiring the copy line is a tracked follow-up once
one of those PRs lands.
"""

import subprocess
import sys
from pathlib import Path


_PATH_PYTEST_INI = Path(__file__).resolve().parents[2] / "pytest.ini"

_STR_LEAKY_MODULE = """
import gc


class LeakyHandle:
	def __init__(self, path):
		self._fh = open(path, "w")

	def __del__(self):
		pass


def test_leaks_file_handle(tmp_path):
	obj = LeakyHandle(tmp_path / "leak.txt")
	del obj
	gc.collect()
"""

_STR_CLEAN_MODULE = """
def test_stays_clean():
	assert True
"""


def _run_probe(path_tmp: Path, str_module_source: str) -> subprocess.CompletedProcess[str]:
	"""Run one throwaway test module under the shipped ``pytest.ini`` filters.

	Parameters
	----------
	path_tmp : pathlib.Path
		Scratch directory the throwaway module is written into.
	str_module_source : str
		Source of the single test module to execute.

	Returns
	-------
	subprocess.CompletedProcess[str]
		The completed ``pytest`` invocation, captured as text.
	"""
	path_module = path_tmp / "test_probe.py"
	path_module.write_text(str_module_source)
	# Constant, trusted argv: sys.executable plus repo-internal paths, no shell, no
	# untrusted input reaches it — the bandit subprocess warning is a false positive here.
	return subprocess.run(  # noqa: S603
		[sys.executable, "-m", "pytest", "-c", str(_PATH_PYTEST_INI), str(path_module), "-q"],
		capture_output=True,
		text=True,
		check=False,
	)


def test_resourcewarning_gate_fails_on_del_leak(tmp_path: Path) -> None:
	"""A file handle leaked via ``__del__`` must fail the suite.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest's per-test scratch directory (isolates the throwaway module).
	"""
	cls_result = _run_probe(tmp_path, _STR_LEAKY_MODULE)
	assert cls_result.returncode != 0
	assert "PytestUnraisableExceptionWarning" in cls_result.stdout


def test_resourcewarning_gate_leaves_clean_run_green(tmp_path: Path) -> None:
	"""An ordinary test with no leak must still pass under the same filters.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest's per-test scratch directory (isolates the throwaway module).
	"""
	cls_result = _run_probe(tmp_path, _STR_CLEAN_MODULE)
	assert cls_result.returncode == 0
