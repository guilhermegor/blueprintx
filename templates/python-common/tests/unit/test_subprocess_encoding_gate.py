"""Unit tests for the subprocess-encoding gate (offline; no git, no network).

Every case either proves the gate FIRES on a text-mode call that drops ``encoding=``
(the should-fail witnesses) or pins a shape it must leave alone.
"""

import importlib.util
from pathlib import Path
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


gate = _load("check_subprocess_encoding")


def _problems(path_dir: Path, *, str_source: str) -> list[str]:
    """Write a source file and return the gate's findings for it.

    Parameters
    ----------
    path_dir : pathlib.Path
        Directory to write into.
    str_source : str
        File contents.

    Returns
    -------
    list[str]
        The gate's findings.
    """
    path_file = path_dir / "sample.py"
    path_file.write_text(str_source, encoding="utf-8")
    return gate.file_problems(path_file, path_root=path_dir)


@pytest.mark.parametrize(
    "str_source",
    [
        "import subprocess\nsubprocess.run(['x'], text=True)\n",
        "import subprocess\nsubprocess.run(['x'], capture_output=True, text=True, check=False)\n",
        "import subprocess\nsubprocess.check_output(['x'], universal_newlines=True)\n",
        "import subprocess\nsubprocess.Popen(['x'], text=True)\n",
        "import subprocess\nsubprocess.check_call(['x'], text=True)\n",
        "from subprocess import run\nrun(['x'], text=True)\n",
        "from subprocess import run as go\ngo(['x'], text=True)\n",
        "import subprocess\nsubprocess.run(['x'], text=True, encoding=None)\n",
    ],
)
def test_gate_text_mode_without_encoding_is_a_finding(*, tmp_path: Path, str_source: str) -> None:
    """A text-mode subprocess call with no ``encoding=`` is reported once, with its line.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    str_source : str
        A source file the gate must reject.
    """
    assert len(_problems(tmp_path, str_source=str_source)) == 1


@pytest.mark.parametrize(
    "str_source",
    [
        "import subprocess\nsubprocess.run(['x'], text=True, encoding='utf-8')\n",
        "import subprocess\nsubprocess.run(['x'], capture_output=True)\n",
        "import subprocess\nsubprocess.run(['x'], text=False)\n",
        "import subprocess\nsubprocess.run(['x'], text=None)\n",
        "import subprocess\nsubprocess.run(['x'], universal_newlines=None)\n",
        "import subprocess\nsubprocess.run(['x'], **dict_kwargs)\n",
        "import runner\nrunner.run(['x'], text=True)\n",
        "from runner import run\nrun(['x'], text=True)\n",
    ],
)
def test_gate_encoded_or_non_text_call_is_clean(*, tmp_path: Path, str_source: str) -> None:
    """A call naming its encoding, not in text mode, or not from subprocess passes.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    str_source : str
        A source file the gate must accept.
    """
    assert _problems(tmp_path, str_source=str_source) == []


def test_gate_unparsable_file_is_a_finding(tmp_path: Path) -> None:
    """A file that cannot be parsed is reported, never silently treated as clean.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    assert "could not parse" in _problems(tmp_path, str_source="def (:\n")[0]


def test_main_violating_tree_exits_one(tmp_path: Path) -> None:
    """The CLI exits 1 on a tree holding an offending call.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    (tmp_path / "bad.py").write_text(
        "import subprocess\nsubprocess.run(['x'], text=True)\n", encoding="utf-8"
    )
    assert gate.main(["--root", str(tmp_path)]) == 1


def test_main_violation_message_names_the_file(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The finding names the file and line, so it is fixable without a search.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    capsys : pytest.CaptureFixture[str]
        Captures the gate's output.
    """
    (tmp_path / "bad.py").write_text(
        "import subprocess\nsubprocess.run(['x'], text=True)\n", encoding="utf-8"
    )
    gate.main(["--root", str(tmp_path)])
    assert "bad.py:2:" in capsys.readouterr().out


def test_main_clean_tree_exits_zero(tmp_path: Path) -> None:
    """The CLI exits 0 on a tree whose calls all name their encoding.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    (tmp_path / "ok.py").write_text(
        "import subprocess\nsubprocess.run(['x'], text=True, encoding='utf-8')\n",
        encoding="utf-8",
    )
    assert gate.main(["--root", str(tmp_path)]) == 0


def test_main_empty_tree_fails_rather_than_passing_vacuously(tmp_path: Path) -> None:
    """A root with no Python file is an error: success for having checked nothing.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    assert gate.main(["--root", str(tmp_path)]) == 1


def test_main_skips_vendored_directories(tmp_path: Path) -> None:
    """A violation under ``.venv`` is not this project's code and is not reported.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.
    """
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    path_venv = tmp_path / ".venv"
    path_venv.mkdir()
    (path_venv / "dep.py").write_text(
        "import subprocess\nsubprocess.run(['x'], text=True)\n", encoding="utf-8"
    )
    assert gate.main(["--root", str(tmp_path)]) == 0


def test_main_shipped_tree_is_clean() -> None:
    """The project this gate ships into holds no offending call."""
    assert gate.main([]) == 0
