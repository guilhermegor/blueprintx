"""Unit tests for the docs-locale gate: each case runs ``main`` over a throwaway project."""

import importlib.util
from pathlib import Path
import sys

import pytest


PATH_BIN = Path(__file__).resolve().parents[2] / "bin"
sys.path.insert(0, str(PATH_BIN))

SPEC_GATE = importlib.util.spec_from_file_location(
    "check_docs_language", PATH_BIN / "check_docs_language.py"
)
cls_gate = importlib.util.module_from_spec(SPEC_GATE)
SPEC_GATE.loader.exec_module(cls_gate)

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
    return cls_gate.main(["--root", str(path_root)])


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


@pytest.fixture
def tuple_untranslated_run(tmp_path: Path, capsys: pytest.CaptureFixture) -> tuple:
    """Run the gate over a pt-BR project with one marked English page.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Throwaway project root.
    capsys : pytest.CaptureFixture
        Output capture.

    Returns
    -------
    tuple
        The exit code and the captured stdout.
    """
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_PT)
    _write(tmp_path / "docs" / "index.md", STR_PT)
    _write(tmp_path / "docs" / "usage.md", STR_EN + "\n<!-- docs-lang:untranslated -->\n")
    return _run(tmp_path), capsys.readouterr().out


def test_main_untranslated_page_passes(tuple_untranslated_run: tuple) -> None:
    """A page carrying the untranslated marker passes."""
    assert tuple_untranslated_run[0] == 0


def test_main_untranslated_page_is_counted(tuple_untranslated_run: tuple) -> None:
    """The summary line counts the skipped page."""
    assert "1 skipped as docs-lang:untranslated" in tuple_untranslated_run[1]


def test_main_skipped_page_is_not_counted_as_checked(tuple_untranslated_run: tuple) -> None:
    """Only the unmarked page counts as checked."""
    assert "(1 page(s) checked," in tuple_untranslated_run[1]


def test_main_all_pages_skipped_does_not_report_success(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A run that read no page must not print the success mark."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_PT)
    _write(tmp_path / "docs" / "index.md", STR_EN + "\n<!-- docs-lang:untranslated -->\n")
    _run(tmp_path)
    assert "✅" not in capsys.readouterr().out


def test_main_untranslated_marker_does_not_excuse_other_pages(tmp_path: Path) -> None:
    """The marker is page-scoped: an unmarked wrong-language page still fails."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_PT)
    _write(tmp_path / "docs" / "index.md", STR_EN)
    _write(tmp_path / "docs" / "usage.md", STR_EN + "\n<!-- docs-lang:untranslated -->\n")
    assert _run(tmp_path) == 1


def test_main_marker_mentioned_in_prose_does_not_skip_page(tmp_path: Path) -> None:
    """Prose that merely names the marker must not exempt a wrong-language page."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_PT)
    str_mention = "\nUse `<!-- docs-lang:untranslated -->` to skip.\n"
    _write(tmp_path / "docs" / "index.md", STR_EN + str_mention)
    assert _run(tmp_path) == 1


def test_main_docs_dir_outside_root_reports_instead_of_raising(tmp_path: Path) -> None:
    """A ``docs_dir`` above the project root yields a finding, not a traceback."""
    path_root = tmp_path / "proj"
    _write(path_root / "mkdocs.yml", STR_MKDOCS_EN + "docs_dir: ../site-docs\n")
    _write(tmp_path / "site-docs" / "index.md", STR_PT)
    assert _run(path_root) == 1


STR_FOREIGN_BLOCK = "que não para com isso, para que não\n"


@pytest.mark.parametrize(
    "str_text",
    [
        "---\ntitle: " + STR_FOREIGN_BLOCK + "---\n\n" + STR_EN,
        STR_EN + "\n<!--\n" + STR_FOREIGN_BLOCK + "-->\n",
        STR_EN + "\n   ```\n" + STR_FOREIGN_BLOCK + "   ```\n",
        STR_EN + "\n<!-- docs-lang:ok --> Esta é a página que você pode ler, que não.\n",
    ],
)
def test_main_front_matter_comments_and_shallow_fences_are_not_prose(
    tmp_path: Path, str_text: str
) -> None:
    """Front matter, multi-line comments and 0-3 space fences are blanked, not scored."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN)
    _write(tmp_path / "docs" / "index.md", str_text)
    assert _run(tmp_path) == 0


@pytest.mark.parametrize(
    "str_text",
    [
        STR_PT + "Mention `docs-lang:ok` here.\n",
        STR_EN + "\nUse `<!--` to open one.\n\n" + STR_PT + "\n<!-- end -->\n",
    ],
)
def test_main_quoted_escape_and_quoted_comment_opener_do_not_hide_prose(
    tmp_path: Path, str_text: str
) -> None:
    """A quoted ``docs-lang:ok`` or ``<!--`` neither escapes a paragraph nor opens a comment."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN)
    _write(tmp_path / "docs" / "index.md", str_text)
    assert _run(tmp_path) == 1


def test_main_marker_inside_fenced_code_does_not_skip_page(tmp_path: Path) -> None:
    """A page that shows the untranslated marker in a fence is still checked."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_PT)
    str_fence = "\n```\n<!-- docs-lang:untranslated -->\n```\n"
    _write(tmp_path / "docs" / "index.md", STR_EN + str_fence)
    assert _run(tmp_path) == 1


LIST_READS: list = []

FN_READ_TEXT = Path.read_text


def _counting_read_text(self: Path, *list_args: object, **dict_kwargs: object) -> str:
    """Record the name of each file read, then read it.

    Parameters
    ----------
    self : pathlib.Path
        The file being read.
    *list_args : object
        Positional arguments for ``Path.read_text``.
    **dict_kwargs : object
        Keyword arguments for ``Path.read_text``.

    Returns
    -------
    str
        The file's text.
    """
    LIST_READS.append(self.name)
    return FN_READ_TEXT(self, *list_args, **dict_kwargs)


def test_main_reads_each_page_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The skip count comes from the first read, not a second pass over every page."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN)
    _write(tmp_path / "docs" / "index.md", STR_EN)
    LIST_READS.clear()
    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    _run(tmp_path)
    assert LIST_READS.count("index.md") == 1


@pytest.mark.parametrize(
    "str_text",
    [
        STR_EN + "\n!!! example\n    ```python\n" + STR_FOREIGN_BLOCK + "    ```\n",
        STR_EN + "\n- item\n\n        ```\n" + STR_FOREIGN_BLOCK + "        ```\n",
        STR_EN + "\n<!-- a -> " + STR_FOREIGN_BLOCK.strip() + " -->\n",
        STR_EN + "\n`` " + STR_FOREIGN_BLOCK.strip() + " ` x `` \n",
    ],
)
def test_main_indented_fences_and_odd_spans_are_not_prose(tmp_path: Path, str_text: str) -> None:
    """Admonition fences, ``>`` in one-line comments and double-backtick spans are blanked."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN)
    _write(tmp_path / "docs" / "index.md", str_text)
    assert _run(tmp_path) == 0


@pytest.mark.parametrize("str_yaml", ["- a\n- b\n", "just text\n"])
def test_main_non_mapping_mkdocs_fails_with_a_message(
    tmp_path: Path, capsys: pytest.CaptureFixture, str_yaml: str
) -> None:
    """A list- or scalar-shaped ``mkdocs.yml`` fails closed with a message, not a traceback."""
    _write(tmp_path / "mkdocs.yml", str_yaml)
    _write(tmp_path / "docs" / "index.md", STR_EN)
    assert (_run(tmp_path), "YAML mapping" in capsys.readouterr().out) == (1, True)


@pytest.mark.parametrize(
    "str_text",
    [
        STR_EN + '\n<div\n  title="' + STR_FOREIGN_BLOCK.strip() + '">\n',
        STR_EN + "\n<img\n  alt='" + STR_FOREIGN_BLOCK.strip() + '\'\n  src="a.png" />\n',
        STR_EN + '\n[ref]: https://a.b "' + STR_FOREIGN_BLOCK.strip() + '"\n',
    ],
)
def test_main_multiline_html_tags_and_link_definitions_are_not_prose(
    tmp_path: Path, str_text: str
) -> None:
    """A tag split over lines and a reference-link definition are blanked, not scored."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN)
    _write(tmp_path / "docs" / "index.md", str_text)
    assert _run(tmp_path) == 0


def test_main_prose_with_a_lone_angle_bracket_is_still_scored(tmp_path: Path) -> None:
    """A stray ``<`` in a paragraph is not a tag, so it does not hide the text after it."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN)
    _write(tmp_path / "docs" / "index.md", STR_EN + "\nSe 1 < 2 então " + STR_PT + "e 3 > 2\n")
    assert _run(tmp_path) == 1


def test_main_failing_run_still_counts_skipped_pages(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A run that fails still says how many pages it skipped as untranslated."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_PT)
    _write(tmp_path / "docs" / "index.md", STR_EN)
    _write(tmp_path / "docs" / "usage.md", STR_EN + "\n<!-- docs-lang:untranslated -->\n")
    _run(tmp_path)
    assert "1 skipped as docs-lang:untranslated" in capsys.readouterr().out


@pytest.mark.parametrize(
    "str_text", ["```\n" + STR_FOREIGN_BLOCK + "```\n", "| a | b |\n|---|---|\n", "\n\n"]
)
def test_main_run_that_scored_no_paragraph_exits_one(tmp_path: Path, str_text: str) -> None:
    """Pages that exist but hold no scoreable prose must not read as a pass."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN)
    _write(tmp_path / "docs" / "index.md", str_text)
    assert _run(tmp_path) == 1


def test_list_pages_prints_the_gates_own_page_set(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """``--list-pages`` prints README plus the published pages, minus ``exclude_docs``."""
    _write(tmp_path / "mkdocs.yml", STR_MKDOCS_EN + STR_EXCLUDE_TREE)
    _write(tmp_path / "README.md", STR_EN)
    _write(tmp_path / "docs" / "index.md", STR_EN)
    _write(tmp_path / "docs" / "backlog" / "plan.md", STR_EN)
    int_rc = cls_gate.main(["--root", str(tmp_path), "--list-pages"])
    list_names = [Path(str_line).name for str_line in capsys.readouterr().out.splitlines()]
    assert (int_rc, sorted(list_names)) == (0, ["README.md", "index.md"])
