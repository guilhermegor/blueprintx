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
        (STR_MKDOCS_EN, STR_EN + "\n````\n```\nque não para com isso, para que não\n```\n````\n"),
        (STR_MKDOCS_EN, STR_EN + "\n```\n~~~\nque não para com isso, para que não\n~~~\n```\n"),
        ("site_name: x\ntheme:\n# note\n  language: pt-BR\n", STR_PT),
        ("site_name: x\ntheme:\n  language: pt-BR  # site language\n", STR_PT),
        ("site_name: x\ntheme: {name: material, language: pt-BR}\n", STR_PT),
        (STR_MKDOCS_EN, STR_EN + "\n```\n```bash\nque não para com isso, para que não\n```\n"),
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


def test_main_custom_docs_dir_is_read(tmp_path: Path) -> None:
    """Pages under a custom ``docs_dir`` are part of the page set."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN + "docs_dir: manual\n")
    _write(tmp_path / "README.md", STR_EN)
    _write(tmp_path / "manual" / "guide.md", STR_PT)
    assert _run(tmp_path) == 1


@pytest.mark.parametrize(
    "str_mkdocs",
    [
        "site_name: x\ntheme:\n  language: !ENV [LANG, en]\n",
        "site_name: x\ntheme:\n  language: es  # note\n",
        "site_name: x\ntheme: {name: material, language: es}\n",
        "site_name: x: [\n",
    ],
)
def test_main_unreadable_declaration_exits_one(tmp_path: Path, str_mkdocs: str) -> None:
    """A declaration the gate cannot resolve to a known locale fails closed."""
    _write(tmp_path / "mkdocs.yml", str_mkdocs)
    _write(tmp_path / "docs" / "index.md", STR_EN)
    assert _run(tmp_path) == 1


@pytest.mark.parametrize(
    "str_mkdocs",
    [STR_MKDOCS_EN + "docs_dir: missing\n", STR_MKDOCS_EN + "docs_dir: manual  # c\n"],
)
def test_main_missing_docs_dir_exits_one_even_with_readme(tmp_path: Path, str_mkdocs: str) -> None:
    """A README alone must not make a misconfigured ``docs_dir`` pass."""
    _write(tmp_path / "mkdocs.yml", str_mkdocs)
    _write(tmp_path / "README.md", STR_EN)
    _write(tmp_path / "docs" / "index.md", STR_EN)
    assert _run(tmp_path) == 1


@pytest.mark.parametrize(
    ("str_exclude", "str_page"),
    [
        ("exclude_docs: |\n  /internal.md\n", "sub/internal.md"),
        ("exclude_docs: |\n  *.md\n  !keep.md\n", "keep.md"),
        ("exclude_docs: |\n  internal/specs/\n", "internal/specs-notes.md"),
    ],
)
def test_main_exclude_docs_follows_gitignore_semantics(
    tmp_path: Path, str_exclude: str, str_page: str
) -> None:
    """Anchoring and negation keep a page in the set that a looser match would drop."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN + str_exclude)
    _write(tmp_path / "README.md", STR_EN)
    _write(tmp_path / "docs" / str_page, STR_PT)
    assert _run(tmp_path) == 1


@pytest.mark.parametrize(
    ("str_exclude", "str_page"),
    [
        ("exclude_docs: drafts.md\n", "drafts.md"),
        ("exclude_docs: |\n  backlog\n", "backlog/plan.md"),
        ("", ".hidden/plan.md"),
    ],
)
def test_main_exclude_docs_drops_what_mkdocs_drops(
    tmp_path: Path, str_exclude: str, str_page: str
) -> None:
    """A page MkDocs does not publish is not read, whichever way the pattern is written."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN + str_exclude)
    _write(tmp_path / "README.md", STR_EN)
    _write(tmp_path / "docs" / str_page, STR_PT)
    assert _run(tmp_path) == 0


def test_main_inline_triple_backticks_do_not_open_a_fence(tmp_path: Path) -> None:
    """A line that starts with inline triple backticks leaves the prose after it readable."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN)
    _write(tmp_path / "docs" / "index.md", STR_EN + "\n```foo``` bar\n\n" + STR_PT)
    assert _run(tmp_path) == 1


@pytest.mark.parametrize(
    "str_text",
    [
        "# Using a database as a cache\n",
        "## Support for the API\n\nUse a cache as a store.\n",
        "## Dos and don'ts\n\n- Set the mode\n- Use a cache\n- Do not ask for more\n",
        "- Install the package\n- Run the tests\n- Read the docs\n",
    ],
)
def test_main_short_english_headings_and_bullets_pass(tmp_path: Path, str_text: str) -> None:
    """Short English headings and list items are not read as Portuguese."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN)
    _write(tmp_path / "docs" / "index.md", str_text)
    assert _run(tmp_path) == 0


def test_main_untranslated_page_is_skipped_and_counted(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A page carrying the untranslated marker passes, and the summary says so."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_PT)
    _write(tmp_path / "docs" / "index.md", STR_PT)
    _write(tmp_path / "docs" / "usage.md", STR_EN + "\n<!-- docs-lang:untranslated -->\n")
    assert _run(tmp_path) == 0
    assert "1 skipped as docs-lang:untranslated" in capsys.readouterr().out


def test_main_untranslated_marker_does_not_excuse_other_pages(tmp_path: Path) -> None:
    """The marker is page-scoped: an unmarked wrong-language page still fails."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_PT)
    _write(tmp_path / "docs" / "index.md", STR_EN)
    _write(tmp_path / "docs" / "usage.md", STR_EN + "\n<!-- docs-lang:untranslated -->\n")
    assert _run(tmp_path) == 1


def test_main_docs_dir_outside_root_reports_instead_of_raising(tmp_path: Path) -> None:
    """A ``docs_dir`` above the project root yields a finding, not a traceback."""
    path_root = tmp_path / "proj"
    _write(path_root / "mkdocs.yml", STR_MKDOCS_EN + "docs_dir: ../site-docs\n")
    _write(tmp_path / "site-docs" / "index.md", STR_PT)
    assert _run(path_root) == 1
