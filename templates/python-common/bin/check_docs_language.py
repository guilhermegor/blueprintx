r"""Fail when README.md or a docs page is written in a language other than the declared locale.

``bin/check_comment_language.py`` polices the code half of the documentation boundary and never
reads ``docs/``. This gate is the other half: the locale a project declares in ``mkdocs.yml``
(``theme.language``, the only declaration -- there is no second one to drift) must be the
language its pages are written in. Measured on five real projects, the conforming ones had zero
minority paragraphs, which is the margin a function-word classifier needs.

How it decides:

1. **Page set.** ``README.md`` plus every page MkDocs publishes under ``docs_dir`` (default
   ``docs``), found by ``check_docs_gap.published_pages`` so ``exclude_docs`` and the implicit
   dot-path and ``templates/`` drops follow MkDocs' own gitignore engine. A ``docs_dir`` that is
   not a directory fails rather than leaving the README alone to pass. A project with no
   ``mkdocs.yml``, or whose page set is empty, fails: a gate that checked nothing must not
   print success.
2. **Prose only.** Fenced code (fences at any indent, since MkDocs admonitions and tabs nest
   them), YAML front matter, multi-line HTML comments, inline code, links, bare URLs, HTML
   tags (also across lines), link definitions and table rows are blanked before counting, so
   quoting a command or naming a Portuguese product proves nothing.
3. **One verdict per paragraph.** Each paragraph is scored against every locale's function-word
   set; the paragraph reads as the locale with the most hits, and only when that count reaches
   ``INT_MIN_HITS`` and beats the declared locale's own. The Portuguese set is imported from
   ``check_comment_language`` rather than copied, so the two gates cannot disagree about it.
4. **Escape.** ``docs-lang:ok`` in a paragraph, outside inline code, skips it.
   ``docs-lang:untranslated`` as its own HTML comment line outside fenced code skips the whole page
   and is counted in the final line, failing runs included, so skipped pages are never silent.
   A scaffold whose locale is not ``en`` appends it to every shipped page, which the English
   templates would otherwise fail on the first lint; deleting it is the act of declaring the
   page translated.
5. **Never vacuous.** A run whose unskipped pages hold no scoreable paragraph fails; a run where
   every page is marked untranslated only warns, since that is a fresh non-English scaffold.
   ``--list-pages`` prints the page set so a caller never has to redefine it.

A locale outside ``DICT_LOCALE_WORDS`` fails closed: the gate cannot say what it would be
checking against.
"""

import os
import pathlib
import re
import sys

from check_comment_language import RE_WORD, SET_PT_WORDS, split_root_option
from check_docs_gap import load_mkdocs, published_pages, unpublished_specs
import yaml


SET_EN_WORDS = frozenset(
    {
        "and",
        "are",
        "be",
        "been",
        "but",
        "can",
        "for",
        "from",
        "has",
        "have",
        "if",
        "is",
        "it",
        "its",
        "not",
        "of",
        "or",
        "that",
        "the",
        "their",
        "then",
        "there",
        "these",
        "this",
        "to",
        "was",
        "when",
        "which",
        "will",
        "with",
        "you",
        "your",
    }
)

DICT_LOCALE_WORDS = {"en": SET_EN_WORDS, "pt-BR": SET_PT_WORDS}

INT_MIN_HITS = 2

INT_EXCERPT = 80

STR_ESCAPE = "docs-lang:ok"

STR_UNTRANSLATED = "docs-lang:untranslated"

STR_DEFAULT_LOCALE = "en"

STR_DEFAULT_DOCS_DIR = "docs"

RE_CODE_SPAN = re.compile(r"(`+).+?\1")

RE_MULTILINE_BLANK = re.compile(
    r"\A---\n.*?\n(?:---|\.\.\.)[ \t]*$|<!--.*?-->", re.DOTALL | re.MULTILINE
)

TUPLE_BLANKINGS = (
    re.compile(r"<!--.*?-->", re.DOTALL),
    re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)"),
    re.compile(r"https?://\S+"),
    re.compile(
        r"""</?[A-Za-z][\w:-]*(?:\s+[A-Za-z_:][\w:.-]*(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'<>=]+))?)*\s*/?>"""
    ),
)

RE_TABLE_ROW = re.compile(r"^[ \t]*\|")

RE_LINK_DEFINITION = re.compile(
    r"""^[ \t]*\[(?!\^)[^\]\n]+\]:[ \t]*\S+(?:[ \t]+(?:"[^"]*"|'[^']*'|\([^)]*\)))?[ \t]*$"""
)

RE_DEFINITION_TITLE = re.compile(r"""^[ \t]*(?:"[^"]*"|'[^']*'|\([^)]*\))[ \t]*$""")

RE_UNTRANSLATED = re.compile(rf"^<!--\s*{re.escape(STR_UNTRANSLATED)}\s*-->\s*$", re.MULTILINE)

RE_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")


def declared_locale(dict_mkdocs: dict) -> str:
    """Return the locale ``mkdocs.yml`` declares in ``theme.language``.

    Parameters
    ----------
    dict_mkdocs : dict
        The parsed ``mkdocs.yml``.

    Returns
    -------
    str
        The declared locale, ``STR_DEFAULT_LOCALE`` when the key is absent (MkDocs' own
        default), or ``""`` when it is not a plain string (``!ENV``, a list), which no word set
        matches and so fails closed.
    """
    dict_theme = dict_mkdocs.get("theme")
    if not isinstance(dict_theme, dict) or "language" not in dict_theme:
        return STR_DEFAULT_LOCALE
    str_language = dict_theme["language"]
    return str_language if isinstance(str_language, str) else ""


def page_set(path_root: pathlib.Path, dict_mkdocs: dict) -> list:
    """Return the pages the gate reads.

    Parameters
    ----------
    path_root : pathlib.Path
        The project root.
    dict_mkdocs : dict
        The parsed ``mkdocs.yml``.

    Returns
    -------
    list of pathlib.Path
        ``README.md`` (when present) and every page MkDocs publishes under ``docs_dir``, sorted.
    """
    path_docs = path_root / str(dict_mkdocs.get("docs_dir") or STR_DEFAULT_DOCS_DIR)
    list_pages = [
        path_docs / str_rel
        for str_rel in published_pages(path_docs, unpublished_specs(dict_mkdocs))
    ]
    path_readme = path_root / "README.md"
    return sorted({*list_pages, *([path_readme] if path_readme.is_file() else [])})


def _fence_toggles(str_open: str, str_marker: str, str_info: str) -> bool:
    """Say whether a fence line opens a block or closes the open one, as CommonMark does.

    Parameters
    ----------
    str_open : str
        The marker that opened the current block, or empty outside a block.
    str_marker : str
        The run of backticks or tildes on this line, or empty when the line is not a fence.
    str_info : str
        What follows the marker on the line.

    Returns
    -------
    bool
        True for an opener (a backtick info string may not hold a backtick, so inline
        ``code`` at a line start is not one), or for a closer: same character, at least as
        long, and nothing after it.
    """
    if not str_marker:
        return False
    if not str_open:
        return "`" not in str_info or str_marker[0] != "`"
    return (
        str_marker[0] == str_open[0] and len(str_marker) >= len(str_open) and not str_info.strip()
    )


def _mask_lines(str_text: str) -> list:
    """Blank fenced code, table rows and link definitions, keeping line numbers.

    Parameters
    ----------
    str_text : str
        The page's text.

    Returns
    -------
    list of str
        One entry per source line, plus a trailing empty line that closes the last paragraph.
    """
    list_out: list = []
    str_open = ""
    bool_after_definition = False
    for str_line in [*str_text.splitlines(), ""]:
        re_marker = RE_FENCE.match(str_line)
        str_marker, str_info = re_marker.groups() if re_marker else ("", "")
        bool_toggle = _fence_toggles(str_open, str_marker, str_info)
        if bool_toggle:
            str_open = "" if str_open else str_marker
        bool_definition = not str_open and bool(RE_LINK_DEFINITION.match(str_line))
        bool_title = bool_after_definition and bool(RE_DEFINITION_TITLE.match(str_line))
        bool_after_definition = bool_definition
        bool_blank = (
            bool_toggle
            or bool(str_open)
            or bool_definition
            or bool_title
            or bool(RE_TABLE_ROW.match(str_line))
        )
        list_out.append("" if bool_blank else str_line)
    return list_out


def _blank_multiline(list_lines: list) -> list:
    """Blank YAML front matter and HTML comments that span lines, keeping line numbers.

    Inline code spans are blanked first, so a quoted ``<!--`` cannot open a comment.

    Parameters
    ----------
    list_lines : list of str
        The lines ``_mask_lines`` returned, with fenced code already blanked.

    Returns
    -------
    list of str
        The same number of lines, with each blanked span reduced to empty lines.
    """
    str_blanked = RE_MULTILINE_BLANK.sub(
        lambda re_hit: re.sub(r"[^\n]", "", re_hit.group())
        if "\n" in re_hit.group()
        else re_hit.group(),
        RE_CODE_SPAN.sub(" ", "\n".join(list_lines)),
    )
    return str_blanked.split("\n")


def prose_paragraphs(str_text: str) -> list:
    """Split a page into its prose paragraphs, keyed by start line.

    Parameters
    ----------
    str_text : str
        The page's text.

    Returns
    -------
    list of tuple
        ``(int_line, str_paragraph)`` pairs with fences, inline code, links, URLs, HTML tags
        and table rows already blanked. A paragraph carrying ``STR_ESCAPE`` is dropped.
    """
    list_out: list = []
    list_block: list = []
    int_start = 0
    for int_line, str_line in enumerate(_blank_multiline(_mask_lines(str_text)), 1):
        if str_line.strip():
            int_start = int_start or int_line
            list_block.append(str_line)
            continue
        str_para = "\n".join(list_block)
        if list_block and STR_ESCAPE not in str_para:
            for re_span in TUPLE_BLANKINGS:
                str_para = re_span.sub(" ", str_para)
            list_out.append((int_start, str_para))
        list_block, int_start = [], 0
    return list_out


def locale_hits(str_paragraph: str) -> dict:
    """Count each locale's function words in a paragraph.

    Parameters
    ----------
    str_paragraph : str
        One prose paragraph, already blanked.

    Returns
    -------
    dict
        Locale -> number of word occurrences from that locale's set.
    """
    list_words = RE_WORD.findall(str_paragraph.lower())
    return {
        str_locale: sum(str_word in set_words for str_word in list_words)
        for str_locale, set_words in DICT_LOCALE_WORDS.items()
    }


def paragraph_locale(str_paragraph: str, str_declared: str) -> str:
    """Return the locale a paragraph reads as, or the declared one when it is not decisive.

    Parameters
    ----------
    str_paragraph : str
        One prose paragraph, already blanked.
    str_declared : str
        The project's declared locale.

    Returns
    -------
    str
        The locale with the most function-word hits when it reaches ``INT_MIN_HITS`` and beats
        the declared locale's count; otherwise ``str_declared``.
    """
    dict_hits = locale_hits(str_paragraph)
    str_top = max(dict_hits, key=lambda str_locale: dict_hits[str_locale])
    if dict_hits[str_top] >= INT_MIN_HITS and dict_hits[str_top] > dict_hits[str_declared]:
        return str_top
    return str_declared


def is_untranslated(str_text: str) -> bool:
    """Tell whether a page carries the untranslated marker as its own comment line.

    Parameters
    ----------
    str_text : str
        The page's text.

    Returns
    -------
    bool
        True only for the exact HTML-comment line outside fenced code, not for prose or code
        that mentions it.
    """
    return bool(RE_UNTRANSLATED.search("\n".join(_blank_multiline(_mask_lines(str_text)))))


def page_problems(path_page: pathlib.Path, path_root: pathlib.Path, str_declared: str) -> tuple:
    """Return one message per paragraph of a page written in the wrong locale.

    Parameters
    ----------
    path_page : pathlib.Path
        The page to read.
    path_root : pathlib.Path
        The project root, used to print a relative path.
    str_declared : str
        The project's declared locale.

    Returns
    -------
    tuple of (list of str, bool, int)
        ``path:line`` messages naming the locale the paragraph reads as and an excerpt, whether
        the page was skipped as untranslated, then how many paragraphs were scored.
    """
    list_out: list = []
    str_text = path_page.read_text(encoding="utf-8")
    if is_untranslated(str_text):
        return list_out, True, 0
    list_paras = prose_paragraphs(str_text)
    for int_line, str_para in list_paras:
        str_read = paragraph_locale(str_para, str_declared)
        if str_read != str_declared:
            str_flat = " ".join(str_para.split())
            str_tail = "…" if len(str_flat) > INT_EXCERPT else ""
            str_excerpt = f"{str_flat[:INT_EXCERPT]}{str_tail}"
            str_rel = pathlib.Path(os.path.relpath(path_page, path_root)).as_posix()
            list_out.append(
                f"❌ {str_rel}:{int_line}: paragraph reads as "
                f"{str_read} but theme.language is {str_declared} -- {str_excerpt}"
            )
    return list_out, False, len(list_paras)


def _load_config(path_root: pathlib.Path) -> tuple:
    """Parse ``mkdocs.yml`` and check that its ``docs_dir`` exists.

    Parameters
    ----------
    path_root : pathlib.Path
        The project root.

    Returns
    -------
    tuple of (dict, str)
        The parsed config, then an error message that is empty when the config is usable.
    """
    path_mkdocs = path_root / "mkdocs.yml"
    if not path_mkdocs.is_file():
        return {}, f"{path_mkdocs} must exist"
    try:
        dict_mkdocs = load_mkdocs(path_mkdocs)
    except yaml.YAMLError as cls_err:
        return {}, f"{path_mkdocs} is not valid YAML: {cls_err}"
    if not isinstance(dict_mkdocs, dict):
        return {}, f"{path_mkdocs} must be a YAML mapping"
    path_docs = path_root / str(dict_mkdocs.get("docs_dir") or STR_DEFAULT_DOCS_DIR)
    if not path_docs.is_dir():
        return dict_mkdocs, f"docs_dir {path_docs} is not a directory; README alone would pass"
    return dict_mkdocs, ""


def _resolve(path_root: pathlib.Path, bool_check_locale: bool = True) -> tuple:
    """Load the config and the page set, or say why the gate cannot run.

    Parameters
    ----------
    path_root : pathlib.Path
        The project root.
    bool_check_locale : bool
        False for ``--list-pages``, which names pages and needs no word set for the locale.

    Returns
    -------
    tuple of (str, list, str)
        The declared locale, the pages to read, and an error message that is empty when the
        gate can run.
    """
    dict_mkdocs, str_error = _load_config(path_root)
    str_declared = declared_locale(dict_mkdocs)
    if bool_check_locale and not str_error and str_declared not in DICT_LOCALE_WORDS:
        str_error = (
            f"theme.language '{str_declared}' has no function-word set; add one to this gate"
        )
    list_pages = [] if str_error else page_set(path_root, dict_mkdocs)
    if not str_error and not list_pages:
        str_error = f"no page found under {path_root}; this gate would pass vacuously"
    return str_declared, list_pages, str_error


def main(list_argv: list) -> int:
    """Check every page against the locale ``mkdocs.yml`` declares.

    Parameters
    ----------
    list_argv : list of str
        Optional leading ``--root <dir>``; defaults to the project the script ships in.
        ``--list-pages`` prints the page set, one path per line, instead of checking it.

    Returns
    -------
    int
        0 when every paragraph reads as the declared locale, 1 on a violation, an unsupported
        locale, a missing ``mkdocs.yml``, an empty page set or a run that scored no paragraph.
    """
    try:
        path_arg, list_rest = split_root_option(list_argv)
    except ValueError as cls_err:
        print(f"❌ {cls_err}")
        return 1
    path_root = path_arg or pathlib.Path(__file__).resolve().parent.parent
    bool_list = list_rest == ["--list-pages"]
    if list_rest and not bool_list:
        print("❌ usage: check_docs_language.py [--root <dir>] [--list-pages]")
        return 1
    str_declared, list_pages, str_error = _resolve(path_root, not bool_list)
    if str_error:
        print(f"❌ {str_error}")
        return 1
    if bool_list:
        print("\n".join(str(path_page) for path_page in list_pages))
        return 0
    return _report(
        [page_problems(path_page, path_root, str_declared) for path_page in list_pages],
        str_declared,
    )


def _report(list_results: list, str_declared: str) -> int:
    """Print the findings and the summary, and return the exit code.

    Parameters
    ----------
    list_results : list of tuple
        One ``(problems, skipped, scored)`` triple per page, from ``page_problems``.
    str_declared : str
        The locale the pages were checked against.

    Returns
    -------
    int
        1 on a violation or when no paragraph was scored in a page that was not skipped, else 0.
    """
    list_problems = [str_found for list_found, _, _ in list_results for str_found in list_found]
    int_skipped = sum(bool_skipped for _, bool_skipped, _ in list_results)
    int_checked = len(list_results) - int_skipped
    str_note = f"{int_skipped} skipped as {STR_UNTRANSLATED}"
    for str_problem in list_problems:
        print(str_problem)
    if list_problems:
        print(
            f"\n{len(list_problems)} paragraph(s) are not in {str_declared}. Translate them, "
            f"change theme.language, or add {STR_ESCAPE} to the paragraph."
            + (f" ({str_note})" if int_skipped else "")
        )
        return 1
    if int_checked == 0:
        print(f"⚠️ docs language: 0 page(s) checked, all {int_skipped} marked {STR_UNTRANSLATED}")
        return 0
    if not sum(int_scored for _, _, int_scored in list_results):
        print(f"❌ {int_checked} page(s) checked but no prose paragraph scored; vacuous pass")
        return 1
    str_tail = f", {str_note}" if int_skipped else ""
    print(f"✅ docs language is {str_declared} ({int_checked} page(s) checked{str_tail})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
