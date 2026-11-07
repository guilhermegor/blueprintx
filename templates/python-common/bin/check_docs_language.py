r"""Fail when README.md or a docs page is written in a language other than the declared locale.

``bin/check_comment_language.py`` polices the code half of the documentation boundary and never
reads ``docs/``. This gate is the other half: the locale a project declares in ``mkdocs.yml``
(``theme.language``, the only declaration -- there is no second one to drift) must be the
language its pages are written in. Measured on five real projects, the conforming ones had zero
minority paragraphs, which is the margin a function-word classifier needs.

How it decides:

1. **Page set.** ``README.md`` plus every ``*.md`` under ``docs_dir`` (default ``docs``) that
   ``exclude_docs`` does not match, so an internal tree is excluded by the config that already
   excludes it. A project with no ``mkdocs.yml``, or whose page set is empty, fails: a gate that
   checked nothing must not print success.
2. **Prose only.** Fenced code, inline code, links, bare URLs, HTML tags and table rows are
   blanked before counting, so quoting a command or naming a Portuguese product proves nothing.
3. **One verdict per paragraph.** Each paragraph is scored against every locale's function-word
   set; the paragraph reads as the locale with the most hits, and only when that count reaches
   ``INT_MIN_HITS`` and beats the declared locale's own. The Portuguese set is imported from
   ``check_comment_language`` rather than copied, so the two gates cannot disagree about it.
4. **Escape.** ``docs-lang:ok`` anywhere in a paragraph skips it.

A locale outside ``DICT_LOCALE_WORDS`` fails closed: the gate cannot say what it would be
checking against.
"""

import fnmatch
import pathlib
import re
import sys

from check_comment_language import RE_WORD, SET_PT_WORDS, split_root_option


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

STR_ESCAPE = "docs-lang:ok"

STR_DEFAULT_LOCALE = "en"

STR_DEFAULT_DOCS_DIR = "docs"

TUPLE_BLANKINGS = (
    re.compile(r"`[^`\n]*`"),
    re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)"),
    re.compile(r"https?://\S+"),
    re.compile(r"<[^>\n]+>"),
)

RE_FENCE = re.compile(r"^\s*(```|~~~)")

RE_TOP_KEY = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*?)\s*$")

RE_THEME_LANGUAGE = re.compile(r"^\s+language:\s*(\S+)\s*$")


def _unquote(str_value: str) -> str:
    """Return a YAML scalar without its surrounding quotes.

    Parameters
    ----------
    str_value : str
        The raw scalar.

    Returns
    -------
    str
        The scalar, trimmed of whitespace and one pair of matching quotes.
    """
    return str_value.strip().strip("\"'")


def _block_lines(list_lines: list, str_key: str) -> list:
    """Return the indented lines that follow a top-level ``key:`` line.

    Parameters
    ----------
    list_lines : list of str
        The file's lines.
    str_key : str
        The top-level key whose block is wanted.

    Returns
    -------
    list of str
        The block's lines up to the next column-0 line; empty when the key is absent.
    """
    list_out: list = []
    bool_in = False
    for str_line in list_lines:
        re_key = RE_TOP_KEY.match(str_line)
        if bool_in and str_line.strip() and not str_line[0].isspace():
            break
        if re_key and re_key.group(1) == str_key:
            bool_in = True
        elif bool_in:
            list_out.append(str_line)
    return list_out


def declared_locale(str_mkdocs: str) -> str:
    """Return the locale ``mkdocs.yml`` declares in ``theme.language``.

    Parameters
    ----------
    str_mkdocs : str
        The file's text.

    Returns
    -------
    str
        The declared locale, or ``STR_DEFAULT_LOCALE`` when the key is absent (MkDocs' own
        default).
    """
    for str_line in _block_lines(str_mkdocs.splitlines(), "theme"):
        re_lang = RE_THEME_LANGUAGE.match(str_line)
        if re_lang:
            return _unquote(re_lang.group(1))
    return STR_DEFAULT_LOCALE


def docs_dir_name(str_mkdocs: str) -> str:
    """Return the ``docs_dir`` setting of ``mkdocs.yml``.

    Parameters
    ----------
    str_mkdocs : str
        The file's text.

    Returns
    -------
    str
        The configured directory, or ``STR_DEFAULT_DOCS_DIR``.
    """
    for str_line in str_mkdocs.splitlines():
        re_key = RE_TOP_KEY.match(str_line)
        if re_key and re_key.group(1) == "docs_dir" and re_key.group(2):
            return _unquote(re_key.group(2))
    return STR_DEFAULT_DOCS_DIR


def excluded_patterns(str_mkdocs: str) -> list:
    """Return the ``exclude_docs`` patterns of ``mkdocs.yml``.

    Parameters
    ----------
    str_mkdocs : str
        The file's text.

    Returns
    -------
    list of str
        One pattern per non-blank, non-comment line of the block.
    """
    list_lines = _block_lines(str_mkdocs.splitlines(), "exclude_docs")
    return [
        str_line.strip()
        for str_line in list_lines
        if str_line.strip() and not str_line.strip().startswith("#")
    ]


def is_excluded(path_rel: pathlib.PurePosixPath, list_patterns: list) -> bool:
    """Say whether a page under ``docs_dir`` is excluded by ``exclude_docs``.

    Parameters
    ----------
    path_rel : pathlib.PurePosixPath
        The page's path relative to ``docs_dir``.
    list_patterns : list of str
        Patterns from ``excluded_patterns``. A trailing ``/`` names a directory at any depth;
        anything else is matched against the whole path and the file name.

    Returns
    -------
    bool
        True when any pattern matches.
    """
    for str_pattern in list_patterns:
        str_bare = str_pattern.lstrip("/")
        if str_pattern.endswith("/") and str_bare.rstrip("/") in path_rel.parts[:-1]:
            return True
        if fnmatch.fnmatch(str(path_rel), str_bare) or fnmatch.fnmatch(path_rel.name, str_bare):
            return True
    return False


def page_set(path_root: pathlib.Path, str_mkdocs: str) -> list:
    """Return the pages the gate reads.

    Parameters
    ----------
    path_root : pathlib.Path
        The project root.
    str_mkdocs : str
        Text of the project's ``mkdocs.yml``.

    Returns
    -------
    list of pathlib.Path
        ``README.md`` (when present) and every non-excluded ``*.md`` under ``docs_dir``, sorted.
    """
    path_docs = path_root / docs_dir_name(str_mkdocs)
    list_patterns = excluded_patterns(str_mkdocs)
    list_pages = [
        path_page
        for path_page in path_docs.rglob("*.md")
        if not is_excluded(
            pathlib.PurePosixPath(path_page.relative_to(path_docs).as_posix()), list_patterns
        )
    ]
    path_readme = path_root / "README.md"
    return sorted({*list_pages, *([path_readme] if path_readme.is_file() else [])})


def _mask_lines(str_text: str) -> list:
    """Blank every line that is fenced code or a table row, keeping line numbers.

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
    bool_fence = False
    for str_line in [*str_text.splitlines(), ""]:
        bool_marker = bool(RE_FENCE.match(str_line))
        bool_fence = bool_fence != bool_marker
        bool_blank = bool_marker or bool_fence or str_line.lstrip().startswith("|")
        list_out.append("" if bool_blank else str_line)
    return list_out


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
    for int_line, str_line in enumerate(_mask_lines(str_text), 1):
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


def page_problems(path_page: pathlib.Path, path_root: pathlib.Path, str_declared: str) -> list:
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
    list of str
        ``path:line`` messages naming the locale the paragraph reads as and an excerpt.
    """
    list_out = []
    str_text = path_page.read_text(encoding="utf-8")
    for int_line, str_para in prose_paragraphs(str_text):
        str_read = paragraph_locale(str_para, str_declared)
        if str_read != str_declared:
            str_excerpt = " ".join(str_para.split())[:80]
            list_out.append(
                f"❌ {path_page.relative_to(path_root)}:{int_line}: paragraph reads as "
                f"{str_read} but theme.language is {str_declared} -- {str_excerpt}…"
            )
    return list_out


def main(list_argv: list) -> int:
    """Check every page against the locale ``mkdocs.yml`` declares.

    Parameters
    ----------
    list_argv : list of str
        Optional leading ``--root <dir>``; defaults to the project the script ships in.

    Returns
    -------
    int
        0 when every paragraph reads as the declared locale, 1 on a violation, an unsupported
        locale, a missing ``mkdocs.yml`` or an empty page set.
    """
    try:
        path_arg, list_rest = split_root_option(list_argv)
    except ValueError as cls_err:
        print(f"❌ {cls_err}")
        return 1
    path_root = path_arg or pathlib.Path(__file__).resolve().parent.parent
    path_mkdocs = path_root / "mkdocs.yml"
    if list_rest or not path_mkdocs.is_file():
        print(f"❌ usage: check_docs_language.py [--root <dir>]; {path_mkdocs} must exist")
        return 1
    str_mkdocs = path_mkdocs.read_text(encoding="utf-8")
    str_declared = declared_locale(str_mkdocs)
    if str_declared not in DICT_LOCALE_WORDS:
        print(f"❌ theme.language '{str_declared}' has no function-word set; add one to this gate")
        return 1
    list_pages = page_set(path_root, str_mkdocs)
    if not list_pages:
        print(f"❌ no page found under {path_root}; this gate would pass vacuously")
        return 1
    list_problems = [
        str_problem
        for path_page in list_pages
        for str_problem in page_problems(path_page, path_root, str_declared)
    ]
    for str_problem in list_problems:
        print(str_problem)
    if list_problems:
        print(
            f"\n{len(list_problems)} paragraph(s) are not in {str_declared}. Translate them, "
            f"change theme.language, or add {STR_ESCAPE} to the paragraph."
        )
        return 1
    print(f"✅ docs language is {str_declared} ({len(list_pages)} page(s) checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
