"""Docs-gap gate — flags published ``docs/`` pages that escaped navigation and the index.

blueprintx#340 measured the defect this closes: MkDocs **builds every ``.md`` under
``docs/`` into the site**, even a page absent from ``mkdocs.yml`` ``nav:`` — it is merely
unlisted, still reachable by URL (the same mechanism ``check_docs_sections.py`` documents
for its own fixed canonical-page set). That gate only watches a FIXED English-slug list
(``index``, ``usage``, ``examples``, ``api/index``, ``faq``, ``contributing``,
``changelog``); it never asks whether every OTHER page under ``docs/`` also reached
``nav:``. Measured against BlueprintX's own ``docs/`` on 2026-09-19: **2 of 26 published
pages** (``decision-records.md``, ``issue-scope.md``) were on disk, built by MkDocs, and
absent from BOTH ``mkdocs.yml`` ``nav:`` AND this repo's own ``docs/CLAUDE.md`` file
index — a real, reproducible gap, not a hypothetical one (see blueprintx#340 for the
full measurement and the PR that shipped this gate).

Two independent layers, both fail-closed:

- **Layer 1 — orphan pages (always runs).** Every ``.md`` under ``docs_dir`` (default
  ``docs/``) that MkDocs would build — not dot-pathed, under ``templates/``, nor matched by
  ``exclude_docs:`` / ``draft_docs:``, all via MkDocs' own gitignore engine — and is not
  ``docs/CLAUDE.md`` itself must be registered somewhere in ``nav:``. Runs identically here
  and in every generated project — no repo-specific assumption, no fixed slug list.
- **Layer 2 — CLAUDE.md file-index sync (optional, repo-owned).** When ``docs/CLAUDE.md``
  carries a ``## 1. File index`` table (this repo's own format — a generated project's
  ``docs/CLAUDE.md`` is prose-only and has none), every path in that table's first column
  must exist on disk, and every non-excluded page on disk must appear in the table.
  Skipped — never silently passed — when the table is absent, the same contract
  ``check_docs_sections.py``'s own Layer 2 uses for an absent ``docs/.docs-skeleton.yaml``.

Placement mirrors ``check_docs_code_refs.py`` / ``check_docs_sections.py``: one
implementation in ``templates/python-common/bin/``, run over BlueprintX's own root via
``--root .`` and copied into every generated project to run on itself — every Python
skeleton ships its own ``docs/`` + ``mkdocs.yml`` + ``docs/CLAUDE.md``, so this is not a
BlueprintX-only concern (``bin/ci/`` is reserved for checks with no template counterpart,
e.g. ``check_makefile_pairing.sh``, since generated projects carry no ``Makefile``).

Every finding is a hard error (exit 1), printed to stderr. Fails when ``docs/`` or
``mkdocs.yml`` is missing or empty — discovery collapsing to zero must never read as
"nothing to check".
"""

import os
import pathlib
import re
import sys

import pathspec
import yaml


PATH_ROOT = pathlib.Path(__file__).resolve().parent.parent
_INDEX_HEADING_RE = re.compile(r"^#+\s*\d*\.?\s*File index", re.IGNORECASE)
_INDEX_ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|")


class _MkDocsSafeLoader(yaml.SafeLoader):
    """SafeLoader that tolerates MkDocs' custom ``!!python/name:`` tags (returns ``None``).

    Identical contract to ``check_docs_sections.py``'s loader of the same name — both need
    only ``nav`` and ``exclude_docs``, so an unknown tag resolving to ``None`` is safe.
    """


def _ignore_unknown(loader: _MkDocsSafeLoader, tag_suffix: str, node: yaml.Node) -> None:  # noqa: ARG001
    """Resolve any unknown YAML tag to ``None`` — see :class:`_MkDocsSafeLoader`.

    Parameters
    ----------
    loader : _MkDocsSafeLoader
        The active loader.
    tag_suffix : str
        The unresolved tag suffix.
    node : yaml.Node
        The node carrying the unknown tag.

    Returns
    -------
    None
        Always ``None`` — the value is irrelevant to this gate.
    """


_MkDocsSafeLoader.add_multi_constructor("tag:yaml.org,2002:python/name:", _ignore_unknown)
_MkDocsSafeLoader.add_multi_constructor("!", _ignore_unknown)


def load_mkdocs(path_mkdocs: pathlib.Path) -> dict:
    """Parse ``mkdocs.yml`` tolerantly; return ``{}`` when the file is absent or empty.

    Parameters
    ----------
    path_mkdocs : pathlib.Path
        Path to the project's ``mkdocs.yml``.

    Returns
    -------
    dict
        The parsed document, or an empty dict when the file is missing or has no content.
    """
    if not path_mkdocs.is_file():
        return {}
    return (
        yaml.load(
            path_mkdocs.read_text(encoding="utf-8"),
            Loader=_MkDocsSafeLoader,  # noqa: S506 — SafeLoader-derived, unknown tags -> None
        )
        or {}
    )


def nav_files(nav: object) -> set[str]:
    """Collect every ``.md`` path registered anywhere in a (possibly nested) ``nav`` tree.

    Parameters
    ----------
    nav : object
        The parsed ``nav`` value (a list of str / dict, arbitrarily nested).

    Returns
    -------
    set of str
        Every doc path referenced in the nav.
    """
    set_files: set[str] = set()
    if isinstance(nav, str):
        set_files.add(nav)
    elif isinstance(nav, list):
        for item in nav:
            set_files |= nav_files(item)
    elif isinstance(nav, dict):
        for value in nav.values():
            set_files |= nav_files(value)
    return set_files


def unpublished_specs(dict_mkdocs: dict) -> tuple[pathspec.GitIgnoreSpec, ...]:
    """Build the specs MkDocs itself uses to decide a page is NOT in the built site.

    Parameters
    ----------
    dict_mkdocs : dict
        The parsed ``mkdocs.yml``.

    Returns
    -------
    tuple of pathspec.GitIgnoreSpec
        Two specs. The first combines the implicit rules (dot-paths, ``/templates/``) with
        ``exclude_docs:``, implicit rules first, as MkDocs does, so a ``!`` re-include in
        ``exclude_docs`` can cancel an implicit drop. The second is ``draft_docs:``, kept
        apart: MkDocs evaluates it on its own.
    """
    # ⚠️ Same engine MkDocs 1.6 builds these with (`mkdocs/structure/files.py`): a
    # hand-rolled matcher diverged on basename-at-any-depth, anchored `/x`, `**` and `!`.
    list_lines = [".*", "/templates/", *(dict_mkdocs.get("exclude_docs") or "").splitlines()]
    str_draft = dict_mkdocs.get("draft_docs") or ""
    return (
        pathspec.GitIgnoreSpec.from_lines(list_lines),
        pathspec.GitIgnoreSpec.from_lines(str_draft.splitlines()),
    )


def _walk_markdown(path_docs: pathlib.Path) -> list[pathlib.Path]:
    """Find every ``*.md`` under ``path_docs``, descending into directory symlinks.

    Parameters
    ----------
    path_docs : pathlib.Path
        The docs directory.

    Returns
    -------
    list of pathlib.Path
        Markdown files, unsorted. A directory whose real path is an ancestor on its own
        branch is pruned, so a link back cannot loop; sibling aliases are all kept.
    """
    list_found = []
    dict_ancestors: dict[str, frozenset[str]] = {str(path_docs): frozenset()}
    for str_dir, list_dirs, list_files in os.walk(path_docs, followlinks=True):
        str_real = os.path.realpath(str_dir)
        set_ancestors = dict_ancestors[str_dir]
        if str_real in set_ancestors:
            list_dirs.clear()
            continue
        for str_sub in list_dirs:
            dict_ancestors[os.path.join(str_dir, str_sub)] = set_ancestors | {str_real}
        list_found.extend(
            pathlib.Path(str_dir) / str_f for str_f in list_files if str_f.endswith(".md")
        )
    return list_found


def published_pages(
    path_docs: pathlib.Path, tuple_specs: tuple[pathspec.GitIgnoreSpec, ...]
) -> list[str]:
    """List every published (not excluded/drafted, non-``CLAUDE.md``) page under the docs dir.

    Parameters
    ----------
    path_docs : pathlib.Path
        The project's docs directory (``docs_dir``, default ``docs/``).
    tuple_specs : tuple of pathspec.GitIgnoreSpec
        From :func:`unpublished_specs`.

    Returns
    -------
    list of str
        Docs-relative paths (forward slashes), sorted.
    """
    list_pages = []
    for path_md in sorted(_walk_markdown(path_docs)):
        str_rel = path_md.relative_to(path_docs).as_posix()
        if str_rel == "CLAUDE.md" or any(spec.match_file(str_rel) for spec in tuple_specs):
            continue
        list_pages.append(str_rel)
    return list_pages


def check_orphan_pages(
    list_pages: list[str], set_nav_files: set[str], str_docs: str = "docs"
) -> list[str]:
    """Return errors for published pages absent from ``mkdocs.yml`` ``nav:``.

    Parameters
    ----------
    list_pages : list of str
        Every published page, docs-relative.
    set_nav_files : set of str
        Every path registered in ``nav:``.
    str_docs : str
        The docs directory as written in ``mkdocs.yml`` ``docs_dir`` — for the message only.

    Returns
    -------
    list of str
        One message per orphan page.
    """
    return [
        f"{str_docs}/{str_rel}: published page not registered in mkdocs.yml nav "
        f"(MkDocs builds it anyway, so it silently vanishes from navigation)"
        for str_rel in list_pages
        if str_rel not in set_nav_files
    ]


def claude_index_table(path_claude_index: pathlib.Path) -> set[str] | None:
    """Return the path column of ``docs/CLAUDE.md``'s ``## 1. File index`` table.

    Parameters
    ----------
    path_claude_index : pathlib.Path
        Path to the project's ``docs/CLAUDE.md``.

    Returns
    -------
    set of str or None
        The listed paths, or ``None`` when the file is absent or has no such heading
        followed by a table — Layer 2 is then skipped, never silently passed.
    """
    if not path_claude_index.is_file():
        return None
    bool_in_table = False
    bool_found_table = False
    set_paths: set[str] = set()
    for str_line in path_claude_index.read_text(encoding="utf-8").splitlines():
        str_stripped = str_line.strip()
        if _INDEX_HEADING_RE.match(str_stripped):
            bool_in_table = True
            continue
        if bool_in_table and str_stripped.startswith("#"):
            break
        if bool_in_table:
            # A heading followed only by prose is NOT a table: enabling Layer 2 on it would
            # report every published page as missing from an index that was never a table.
            bool_found_table = bool_found_table or str_stripped.startswith("|")
            cls_match = _INDEX_ROW_RE.match(str_stripped)
            if cls_match:
                set_paths.add(cls_match.group(1))
    return set_paths if bool_found_table else None


def check_claude_index(
    set_indexed: set[str],
    list_pages: list[str],
    path_docs: pathlib.Path,
    str_docs: str = "docs",
) -> list[str]:
    """Return errors where ``docs/CLAUDE.md``'s file index and disk reality disagree.

    Parameters
    ----------
    set_indexed : set of str
        Paths listed in the ``## 1. File index`` table.
    list_pages : list of str
        Every published page actually on disk.
    path_docs : pathlib.Path
        The project's docs directory.
    str_docs : str
        The docs directory as written in ``mkdocs.yml`` ``docs_dir`` — for messages only.

    Returns
    -------
    list of str
        One message per stale or missing row.
    """
    list_errors = [
        f"{str_docs}/CLAUDE.md file index lists `{str_path}`, which does not exist on disk"
        for str_path in sorted(set_indexed)
        if not (path_docs / str_path).is_file()
    ]
    list_errors += [
        f"{str_docs}/{str_rel}: published page missing from the {str_docs}/CLAUDE.md file index"
        for str_rel in list_pages
        if str_rel not in set_indexed
    ]
    return list_errors


# `--root <dir>` is a flag plus its value, so argv must hold at least two entries.
_INT_FLAG_WITH_VALUE = 2


def main(list_argv: list) -> int:
    """Run both layers over the project's docs directory; return 1 on any violation.

    Parameters
    ----------
    list_argv : list of str
        ``["--root", <dir>]`` to check a tree other than this file's own project, else
        empty.

    Returns
    -------
    int
        0 when no orphan page and (if applicable) no index drift was found, 1 otherwise.
    """
    global PATH_ROOT  # noqa: PLW0603 — same documented seam as check_docs_code_refs.py
    if list_argv[:1] == ["--root"]:
        if len(list_argv) < _INT_FLAG_WITH_VALUE:
            print("no directory given for --root", file=sys.stderr)
            return 1
        PATH_ROOT = pathlib.Path(list_argv[1]).resolve()

    dict_mkdocs = load_mkdocs(PATH_ROOT / "mkdocs.yml")
    # MkDocs resolves a relative `docs_dir` against mkdocs.yml's folder; `/` on an absolute
    # right-hand side keeps the absolute path, so both documented forms land correctly.
    str_docs = str(dict_mkdocs.get("docs_dir") or "docs")
    path_docs = PATH_ROOT / str_docs
    if not path_docs.is_dir():
        print(f"no {str_docs}/ directory found — discovery is broken, not clean", file=sys.stderr)
        return 1
    if not dict_mkdocs:
        print(
            "no mkdocs.yml found (or it is empty) — discovery is broken, not clean",
            file=sys.stderr,
        )
        return 1

    list_pages = published_pages(path_docs, unpublished_specs(dict_mkdocs))
    if not list_pages:
        # Same reason as the empty-mkdocs.yml branch above: a scan that found nothing to
        # check has not passed, it has failed to run. Reporting 0 errors over 0 pages is
        # a gate declaring its own blindness as OK.
        print(
            "no published documentation pages found — discovery is broken, not clean",
            file=sys.stderr,
        )
        return 1
    set_nav_files = nav_files(dict_mkdocs.get("nav"))
    list_errors = check_orphan_pages(list_pages, set_nav_files, str_docs)

    set_indexed = claude_index_table(path_docs / "CLAUDE.md")
    if set_indexed is not None:
        list_errors += check_claude_index(set_indexed, list_pages, path_docs, str_docs)

    for str_error in list_errors:
        print(f"docs-gap: {str_error}", file=sys.stderr)
    return 1 if list_errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
