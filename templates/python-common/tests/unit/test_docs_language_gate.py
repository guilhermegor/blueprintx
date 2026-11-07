"""Unit tests for the docs-locale gate: each case runs ``main`` over a throwaway project."""

import importlib.util
from pathlib import Path
import sys

import pytest


_BIN = Path(__file__).resolve().parents[2] / "bin"
sys.path.insert(0, str(_BIN))

_SPEC = importlib.util.spec_from_file_location(
    "check_docs_language", _BIN / "check_docs_language.py"
)
gate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gate)

STR_EN = "This is the page that you can read, and it is written in English for the reader.\n"
STR_PT = "Esta é a página que você pode ler, e ela está escrita para o leitor que não sabe.\n"

STR_MKDOCS_EN = "site_name: x\ntheme:\n  language: en\n"
STR_MKDOCS_UNSET = "site_name: x\n"
STR_MKDOCS_PT = "site_name: x\ntheme:\n  name: material\n  language: pt-BR\n"
STR_MKDOCS_ES = "site_name: x\ntheme:\n  language: es\n"
STR_EXCLUDE_TREE = "exclude_docs: |\n  backlog/\n  internal.md\n"
STR_EXCLUDE_ALL = "exclude_docs: |\n  *.md\n"


def _write(path_file: Path, str_text: str) -> Path:
    """Write a file, creating its parents.

    Parameters
    ----------
    path_file : pathlib.Path
        Destination.
    str_text : str
        Content.

    Returns
    -------
    pathlib.Path
        The file written.
    """
    path_file.parent.mkdir(parents=True, exist_ok=True)
    path_file.write_text(str_text, encoding="utf-8")
    return path_file


def _run(path_root: Path) -> int:
    """Run the gate over ``path_root``.

    Parameters
    ----------
    path_root : pathlib.Path
        Project root.

    Returns
    -------
    int
        The gate's exit code.
    """
    return gate.main(["--root", str(path_root)])


@pytest.mark.parametrize(
    ("str_mkdocs", "str_text"),
    [
        (STR_MKDOCS_EN, STR_EN),
        (STR_MKDOCS_UNSET, STR_EN),
        (STR_MKDOCS_PT, STR_PT),
        (STR_MKDOCS_EN, STR_EN + "\n```\nque não para com isso, para que não\n```\n"),
        (
            STR_MKDOCS_EN,
            STR_EN + "\nUse `que não para com isso` e [que não para](https://a.b/c).\n",
        ),
        (STR_MKDOCS_EN, STR_EN + "\ndocs-lang:ok Esta é a página que você pode ler, que não.\n"),
    ],
)
def test_main_conforming_pages_exit_zero(tmp_path: Path, str_mkdocs: str, str_text: str) -> None:
    """A page in the declared locale, or foreign text only inside ignored spans, passes."""
    _write(tmp_path / "mkdocs.yml", str_mkdocs)
    _write(tmp_path / "docs" / "index.md", str_text)
    _write(tmp_path / "README.md", str_text)
    assert _run(tmp_path) == 0


@pytest.mark.parametrize(
    ("str_mkdocs", "str_text"),
    [(STR_MKDOCS_EN, STR_PT), (STR_MKDOCS_UNSET, STR_PT), (STR_MKDOCS_PT, STR_EN)],
)
def test_main_wrong_language_page_exits_one(
    tmp_path: Path, str_mkdocs: str, str_text: str
) -> None:
    """A page whose prose is in the other locale fails."""
    _write(tmp_path / "mkdocs.yml", str_mkdocs)
    _write(tmp_path / "docs" / "index.md", str_text)
    assert _run(tmp_path) == 1


def test_main_wrong_language_readme_exits_one(tmp_path: Path) -> None:
    """The root README is part of the page set."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN)
    _write(tmp_path / "docs" / "index.md", STR_EN)
    _write(tmp_path / "README.md", STR_PT)
    assert _run(tmp_path) == 1


def test_main_wrong_language_names_file_and_line(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The finding names the file and the paragraph's own start line."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN)
    _write(tmp_path / "docs" / "guide.md", "# T\n\n" + STR_PT)
    _run(tmp_path)
    str_want = "docs/guide.md:3: paragraph reads as pt-BR but theme.language is en"
    assert str_want in capsys.readouterr().out


@pytest.mark.parametrize("str_exclude", [STR_EXCLUDE_TREE, STR_EXCLUDE_ALL])
def test_main_excluded_page_is_not_read(tmp_path: Path, str_exclude: str) -> None:
    """A page matched by ``exclude_docs`` is skipped even when it is in the wrong language."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN + str_exclude)
    _write(tmp_path / "README.md", STR_EN)
    _write(tmp_path / "docs" / "backlog" / "plan.md", STR_PT)
    _write(tmp_path / "docs" / "internal.md", STR_PT)
    assert _run(tmp_path) == 0


def test_main_unexcluded_sibling_of_excluded_tree_is_read(tmp_path: Path) -> None:
    """Excluding one tree does not excuse the pages beside it."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN + STR_EXCLUDE_TREE)
    _write(tmp_path / "docs" / "backlog" / "plan.md", STR_PT)
    _write(tmp_path / "docs" / "usage.md", STR_PT)
    assert _run(tmp_path) == 1


def test_main_unsupported_locale_exits_one(tmp_path: Path) -> None:
    """A locale with no function-word set fails closed."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_ES)
    _write(tmp_path / "docs" / "index.md", STR_EN)
    assert _run(tmp_path) == 1


def test_main_no_mkdocs_exits_one(tmp_path: Path) -> None:
    """A project with no ``mkdocs.yml`` has no declaration to check against."""
    _write(tmp_path / "README.md", STR_EN)
    assert _run(tmp_path) == 1


def test_main_empty_page_set_exits_one(tmp_path: Path) -> None:
    """Zero pages is a vacuous pass, which the gate refuses."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN)
    assert _run(tmp_path) == 1
