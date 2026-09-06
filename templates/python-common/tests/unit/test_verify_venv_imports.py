"""Unit tests for the post-install import verifier (blueprintx#127).

`bin/lib/pip_fallback.sh` used to treat "`pip install` returned 0" as the last word on
whether a pip-fallback bootstrap succeeded. That is exactly the probe blueprintx#127 calls
out as a lie: a blocked corporate index can report a requirement "already satisfied"
without ever contacting it, or a batch install can fail in a way the caller never checked,
leaving an empty `.venv` behind a green exit. These tests pin the SHOULD-FAIL behaviour —
a requirement that is not actually importable must be reported and must fail the run — so
a regression back to "did pip exit 0" is caught here rather than the first time someone
hits a real blocked proxy.
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


_LIB = Path(__file__).resolve().parents[2] / "bin" / "lib"


def _load() -> ModuleType:
    """Load ``bin/lib/verify_venv_imports.py`` by path (``bin/lib/`` is not a package).

    Returns
    -------
    ModuleType
            The imported module.
    """
    cls_spec = importlib.util.spec_from_file_location(
        "verify_venv_imports", _LIB / "verify_venv_imports.py"
    )
    cls_module = importlib.util.module_from_spec(cls_spec)
    sys.modules["verify_venv_imports"] = cls_module
    cls_spec.loader.exec_module(cls_module)
    return cls_module


MODULE = _load()


# --------------------------
# Tests — requirement_name
# --------------------------


def test_requirement_name_strips_extras_markers_and_comments() -> None:
    """A real requirement line reduces to its bare distribution name."""
    assert MODULE.requirement_name("httpx[http2]>=0.27 ; python_version >= '3.10'") == "httpx"
    assert MODULE.requirement_name("pytest  # dev group") == "pytest"


def test_requirement_name_blank_and_comment_lines_are_none() -> None:
    """Blank lines and full-line comments carry no distribution to check."""
    assert MODULE.requirement_name("") is None
    assert MODULE.requirement_name("   ") is None
    assert MODULE.requirement_name("# a comment") is None


# --------------------------
# Tests — check_requirement (the should-fail witness)
# --------------------------


def test_check_requirement_real_installed_package_passes() -> None:
    """A distribution that is genuinely installed and importable reports no problem.

    ``pytest`` is a dev-dependency of this very project, so it is always present in the
    interpreter running this test — the positive control for the probe.
    """
    assert MODULE.check_requirement("pytest>=8.0") is None


def test_check_requirement_missing_package_is_reported() -> None:
    """SHOULD-FAIL WITNESS: a declared-but-absent package must be named, not waved through.

    This is the exact shape of the defect blueprintx#127 reports: a package pip claims (or
    pyproject declares) as installed that is not actually there. A silent ``None`` here
    would reintroduce the "empty .venv reported as success" failure this file exists to
    catch.
    """
    str_problem = MODULE.check_requirement("definitely-not-a-real-package-xyz-127")
    assert str_problem is not None
    assert "definitely-not-a-real-package-xyz-127" in str_problem
    assert "not installed" in str_problem


# --------------------------
# Tests — main (the file-driven entrypoint pip_fallback.sh actually invokes)
# --------------------------


def test_main_empty_requirements_file_passes(tmp_path: Path) -> None:
    """A group with genuinely zero requirements is not a failure — nothing to verify."""
    path_req = tmp_path / "requirements.txt"
    path_req.write_text("", encoding="utf-8")

    int_exit = _run_main(path_req)
    assert int_exit == 0


def test_main_unimportable_requirement_fails_loud(tmp_path: Path) -> None:
    """SHOULD-FAIL WITNESS: the CLI entrypoint refuses when a requirement cannot import.

    This is what ``pip_fallback.sh`` actually shells out to. A regression that makes this
    return 0 on a broken venv is the regression that reopens blueprintx#127.
    """
    path_req = tmp_path / "requirements.txt"
    path_req.write_text("definitely-not-a-real-package-xyz-127>=1.0\n", encoding="utf-8")

    int_exit = _run_main(path_req)
    assert int_exit == 1


def _run_main(path_req: Path) -> int:
    """Invoke ``MODULE.main()`` with argv patched to point at ``path_req``.

    Parameters
    ----------
    path_req : pathlib.Path
            The requirements file to verify.

    Returns
    -------
    int
            ``main()``'s own return code.
    """
    list_argv_saved = sys.argv[:]
    sys.argv = ["verify_venv_imports.py", str(path_req)]
    try:
        return MODULE.main()
    finally:
        sys.argv = list_argv_saved


if __name__ == "__main__":
    pytest.main([__file__])
