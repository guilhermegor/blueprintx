"""Keep the shared registries merge-friendly: sorted ``__all__``, one name per line, no counts.

Rationale and the measurement behind it: ``docs/conflict-free-registries.md`` in BlueprintX.
"""

import ast
import pathlib
import re
import sys


_SRC = pathlib.Path("src")
_DOC_ROOTS = (pathlib.Path("README.md"), pathlib.Path("docs"))
_RE_FENCE = re.compile(r"^\s*(```|~~~)")
_RE_COUNT = re.compile(
    r"\b\d+\s+(?:public\s+)?(?:modules?|exports?|functions?|classes|layouts?|readers?|"
    r"writers?|endpoints?|commands?|models?|handlers?)\b",
    re.IGNORECASE,
)


def sort_key(str_name: str) -> tuple[bool, str]:
    """Return the canonical ordering key: dunders first, then case-insensitive name.

    Parameters
    ----------
    str_name : str
        An ``__all__`` entry.

    Returns
    -------
    tuple of (bool, str)
        The key shared by every registry list.
    """
    return (not str_name.startswith("__"), str_name.lower())


def binds_all(cls_node: ast.Assign | ast.AnnAssign | ast.AugAssign) -> bool:
    """Return whether an assignment statement targets ``__all__``.

    Parameters
    ----------
    cls_node : ast.Assign or ast.AnnAssign or ast.AugAssign
        The statement to inspect.

    Returns
    -------
    bool
        ``True`` when ``__all__`` is one of its targets, including inside tuple unpacking.
    """
    list_targets = cls_node.targets if isinstance(cls_node, ast.Assign) else [cls_node.target]
    return any(
        isinstance(cls_n, ast.Name) and cls_n.id == "__all__"
        for cls_t in list_targets
        for cls_n in ast.walk(cls_t)
    )


def all_value(path_init: pathlib.Path) -> ast.expr | None:
    """Return the expression bound to a module's ``__all__``, or ``None`` when it has none.

    Parameters
    ----------
    path_init : pathlib.Path
        The ``__init__.py`` to read.

    Returns
    -------
    ast.expr or None
        The bound value; a ``None`` constant for a ``+=`` or repeated binding, which
        ``order_problems`` rejects as unreadable.
    """
    cls_tree = ast.parse(path_init.read_text(encoding="utf-8"))
    list_nodes = [
        cls_node
        for cls_node in ast.walk(cls_tree)
        if isinstance(cls_node, ast.Assign | ast.AnnAssign | ast.AugAssign) and binds_all(cls_node)
    ]
    if not list_nodes:
        return None
    if len(list_nodes) > 1 or isinstance(list_nodes[0], ast.AugAssign):
        return ast.Constant(None)
    return list_nodes[0].value or ast.Constant(None)


def order_problems(path_init: pathlib.Path, cls_value: ast.expr) -> list[str]:
    """Return one message per ordering or layout defect in an ``__all__``.

    Parameters
    ----------
    path_init : pathlib.Path
        The ``__init__.py`` the list belongs to.
    cls_value : ast.expr
        The expression bound to ``__all__``.

    Returns
    -------
    list of str
        Human-readable problems; empty when sorted and one entry per line.
    """
    if not isinstance(cls_value, ast.List | ast.Tuple) or not all(
        isinstance(cls_e, ast.Constant) and isinstance(cls_e.value, str)
        for cls_e in cls_value.elts
    ):
        return [f"{path_init}: __all__ must be one literal list of strings"]
    list_problems: list[str] = []
    list_names = [cls_e.value for cls_e in cls_value.elts]
    if list_names != sorted(list_names, key=sort_key):
        list_problems.append(f"{path_init}: __all__ is not sorted (dunders first, then A-Z)")
    list_lines = [cls_e.lineno for cls_e in cls_value.elts]
    set_brackets = {cls_value.lineno, cls_value.end_lineno}
    if len(set(list_lines)) != len(list_lines) or set_brackets & set(list_lines):
        list_problems.append(f"{path_init}: __all__ must hold exactly one entry per line")
    return list_problems


def count_problems(path_doc: pathlib.Path) -> list[str]:
    """Return one message per stored count found outside fenced code in a Markdown file.

    Parameters
    ----------
    path_doc : pathlib.Path
        The Markdown file to read.

    Returns
    -------
    list of str
        Human-readable problems; empty when no count restates something countable.
    """
    list_problems: list[str] = []
    bool_fenced = False
    for int_no, str_line in enumerate(path_doc.read_text(encoding="utf-8").splitlines(), 1):
        if _RE_FENCE.match(str_line):
            bool_fenced = not bool_fenced
        elif not bool_fenced and (cls_m := _RE_COUNT.search(str_line)):
            list_problems.append(f"{path_doc}:{int_no}: stored count '{cls_m.group(0)}'")
    return list_problems


def doc_files() -> list[pathlib.Path]:
    """Return the README and every Markdown file under ``docs/``.

    Returns
    -------
    list of pathlib.Path
        Existing files only.
    """
    list_files: list[pathlib.Path] = []
    for path_root in _DOC_ROOTS:
        if path_root.is_dir():
            list_files.extend(sorted(path_root.rglob("*.md")))
        elif path_root.is_file():
            list_files.append(path_root)
    return list_files


def main() -> int:
    """Run the gate over every ``__all__`` under ``src/`` and every documentation file.

    Returns
    -------
    int
        ``0`` when every registry is canonical and no count is stored, ``1`` otherwise.
    """
    list_found = [
        (path_init, cls_value)
        for path_init in sorted(_SRC.rglob("__init__.py"))
        if (cls_value := all_value(path_init)) is not None
    ]
    if not list_found:
        print("check_registry_order: found ZERO __all__ lists under src/", file=sys.stderr)
        return 1
    list_problems: list[str] = []
    for path_init, cls_value in list_found:
        list_problems += order_problems(path_init, cls_value)
    for path_doc in doc_files():
        list_problems += count_problems(path_doc)
    for str_problem in list_problems:
        print(f"❌ {str_problem}", file=sys.stderr)
    if list_problems:
        return 1
    print(f"Registries canonical in {len(list_found)} package(s); no stored counts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
