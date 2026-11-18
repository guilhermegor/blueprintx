"""Should-fail tests for the pt-BR language check of ``bin/check_description_sync.sh``."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


PATH_BIN = Path(__file__).resolve().parents[2] / "bin"
STR_MKDOCS_PT = "site_name: x\ntheme:\n  name: material\n  language: pt-BR\n"
STR_MKDOCS_EN = "site_name: x\ntheme:\n  language: en\n"
STR_DESC_PT = "Biblioteca para validar e mascarar os documentos que você usa no Brasil."
STR_DESC_SHORT_PT = "Valida, aplica e remove a máscara de documentos brasileiros"
STR_DESC_EN = "A library that you can use to validate and mask the documents used in Brazil."


def _run(path_root: Path, *, str_mkdocs: str, str_desc: str) -> subprocess.CompletedProcess:
    """Run the gate over a throwaway project with a ``package.json`` manifest.

    Parameters
    ----------
    path_root : pathlib.Path
        Project root.
    str_mkdocs : str
        ``mkdocs.yml`` content.
    str_desc : str
        Manifest description.

    Returns
    -------
    subprocess.CompletedProcess
        The finished process.
    """
    (path_root / "mkdocs.yml").write_text(str_mkdocs, encoding="utf-8")
    (path_root / "package.json").write_text(
        json.dumps({"description": str_desc}), encoding="utf-8"
    )
    return subprocess.run(  # noqa: S603 - constant trusted argv, bash resolved via shutil
        [
            shutil.which("bash") or "bash",
            str(PATH_BIN / "check_description_sync.sh"),
            str(path_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("str_mkdocs", "str_desc", "int_code"),
    [
        (STR_MKDOCS_PT, STR_DESC_EN, 1),
        (STR_MKDOCS_PT, STR_DESC_PT, 0),
        (STR_MKDOCS_PT, STR_DESC_SHORT_PT, 0),
        (STR_MKDOCS_PT, "Reads de facto standards", 1),
        (STR_MKDOCS_EN, STR_DESC_EN, 0),
    ],
)
def test_description_language_exit_code(
    tmp_path: Path, *, str_mkdocs: str, str_desc: str, int_code: int
) -> None:
    """An English description under a pt-BR docs site fails; every other pairing passes."""
    assert _run(tmp_path, str_mkdocs=str_mkdocs, str_desc=str_desc).returncode == int_code


@pytest.mark.parametrize(
    "str_theme",
    [
        "theme:\n    # note\n  name: material\n  language: pt-BR\n",
        'theme:\n  "language": pt-BR\n',
        "theme:\n  'language': pt-BR\n",
        'theme: {"language": pt-BR}\n',
        'theme: {custom_dir: "language: en", language: pt-BR}\n',
        "theme: {name: material, 'language': pt-BR}\n",
    ],
)
def test_description_language_theme_spellings_reject_english(
    tmp_path: Path, *, str_theme: str
) -> None:
    """Every YAML spelling of ``theme.language: pt-BR`` still triggers the pt-BR check."""
    cls_run = _run(tmp_path, str_mkdocs=str_theme, str_desc=STR_DESC_EN)
    assert cls_run.returncode == 1


def test_description_language_failure_message(tmp_path: Path) -> None:
    """The failure message says the description does not read as pt-BR."""
    cls_run = _run(tmp_path, str_mkdocs=STR_MKDOCS_PT, str_desc=STR_DESC_EN)
    assert "does not read as pt-BR" in cls_run.stdout + cls_run.stderr
