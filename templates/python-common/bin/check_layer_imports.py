"""Enforce the per-layer import policy: a vendor lives behind a seam, not in a layer.

The prose rule ("every third-party dependency is reached through a seam in ``utils/``") is
only a suggestion until something reads it. This gate reads it.

Three classifications, in order:

1. **stdlib** — always allowed, in every layer. It carries no coupling risk.
2. **first-party** — always allowed here. Direction between layers is a separate concern.
3. **third-party** — allowed only if the file's layer names it in ``allow``, WITH a reason.

Two properties are deliberate, because both are how the rule gets evaded in practice:

- **Scope is irrelevant to the verdict.** An import inside a function is judged exactly like
  one at the top of the file. Deferring an import does not undo the layer's knowledge of the
  vendor, so scope only changes where this gate has to LOOK, never what it decides. It does
  change the message, because that is the form that used to pass unnoticed.
- **A vendor may be allowed as a TYPE and denied as an API.** ``pandas`` is the vocabulary the
  layers speak: ``-> pd.DataFrame`` in a signature couples nothing, while ``pd.read_sql(...)``
  couples everything. A module under ``annotation_only`` may appear in annotations and
  nowhere else; the construction and reading live behind the ``utils/`` seams.

The policy lives in ``.layer-policy.yaml`` at the project root. No file, no gate — the check
exits 0, so a tier that has not adopted it is not blocked.
"""

from __future__ import annotations

import ast
import pathlib
import sys


try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - the gate self-skips without its parser
    yaml = None  # type: ignore[assignment]


_POLICY_FILE = ".layer-policy.yaml"
_SRC_ROOT = "src"


def load_policy(path_root: pathlib.Path) -> dict | None:
    """Read the layer policy, or ``None`` when the project has not adopted one.

    Parameters
    ----------
    path_root : pathlib.Path
        The project root holding ``.layer-policy.yaml``.

    Returns
    -------
    dict or None
        The parsed policy, or ``None`` when the file is absent or empty.
    """
    path_policy = path_root / _POLICY_FILE
    if yaml is None or not path_policy.is_file():
        return None
    return yaml.safe_load(path_policy.read_text(encoding="utf-8")) or None


def first_party_roots(path_src: pathlib.Path, dict_policy: dict) -> set[str]:
    """Return the top-level package names that belong to this project.

    Includes ``first_party_extra`` from the policy, which exists for the **layout shim**: the
    shared helpers ship to both tiers and import their engine as

    ``try: from utils.typing import … except ModuleNotFoundError: from chassis.typing import …``

    ``chassis`` is first-party — just first-party in the OTHER layout — so a directory scan of
    this tier alone would report all 23 shipped helpers as reaching for a vendor.

    Parameters
    ----------
    path_src : pathlib.Path
        The ``src/`` directory.
    dict_policy : dict
        The parsed policy, read for ``first_party_extra``.

    Returns
    -------
    set of str
        Directory names under ``src/``, ``src`` itself, and any declared extras.
    """
    set_scanned = {p.name for p in path_src.iterdir() if p.is_dir()} | {_SRC_ROOT}
    return set_scanned | set(dict_policy.get("first_party_extra") or [])


def annotation_node_ids(cls_tree: ast.Module) -> set[int]:
    """Collect the ids of every AST node that sits inside a type annotation.

    Includes ``if TYPE_CHECKING:`` bodies, which exist precisely to hold imports that are
    only ever referenced from annotations.

    Parameters
    ----------
    cls_tree : ast.Module
        The parsed module.

    Returns
    -------
    set of int
        ``id()`` of each node reachable from an annotation or a TYPE_CHECKING block.
    """
    set_ids: set[int] = set()

    def _mark(cls_node: ast.AST | None) -> None:
        if cls_node is None:
            return
        for cls_child in ast.walk(cls_node):
            set_ids.add(id(cls_child))

    for cls_node in ast.walk(cls_tree):
        _mark(getattr(cls_node, "annotation", None))
        _mark(getattr(cls_node, "returns", None))
        if isinstance(cls_node, ast.If):
            str_test = ast.dump(cls_node.test)
            if "TYPE_CHECKING" in str_test:
                for cls_stmt in cls_node.body:
                    _mark(cls_stmt)
    return set_ids


def imported_names(cls_node: ast.Import | ast.ImportFrom) -> list[tuple[str, str]]:
    """Return ``(root_module, local_alias)`` for each name an import statement binds.

    Parameters
    ----------
    cls_node : ast.Import or ast.ImportFrom
        The import statement.

    Returns
    -------
    list of tuple of (str, str)
        One entry per bound name; the alias is what the module body refers to.
    """
    list_out: list[tuple[str, str]] = []
    if isinstance(cls_node, ast.Import):
        for cls_alias in cls_node.names:
            str_local = cls_alias.asname or cls_alias.name.split(".")[0]
            list_out.append((cls_alias.name.split(".")[0], str_local))
        return list_out
    if cls_node.level:  # a relative import is first-party by construction
        return list_out
    str_root = (cls_node.module or "").split(".")[0]
    for cls_alias in cls_node.names:
        list_out.append((str_root, cls_alias.asname or cls_alias.name))
    return list_out


def find_file_problems(
    path_file: pathlib.Path, str_layer: str, dict_policy: dict, set_first_party: set[str]
) -> list[str]:
    """Return every import-policy violation in one file (never raises).

    Parameters
    ----------
    path_file : pathlib.Path
        The module to check.
    str_layer : str
        The layer the file belongs to (its first path component under ``src/``).
    dict_policy : dict
        The parsed ``.layer-policy.yaml``.
    set_first_party : set of str
        Top-level package names that belong to this project.

    Returns
    -------
    list of str
        Human-readable problems; empty when the file complies.
    """
    try:
        cls_tree = ast.parse(path_file.read_text(encoding="utf-8"))
    except SyntaxError as cls_exc:
        return [f"{path_file}: could not parse ({cls_exc})"]

    dict_layers = dict_policy.get("layers", {})
    dict_allow = (dict_layers.get(str_layer) or {}).get("allow") or {}
    dict_annotation_only = dict_policy.get("annotation_only") or {}

    set_annotation_ids = annotation_node_ids(cls_tree)
    list_functions = [
        (cls_n.lineno, max(getattr(c, "lineno", cls_n.lineno) for c in ast.walk(cls_n)))
        for cls_n in ast.walk(cls_tree)
        if isinstance(cls_n, ast.FunctionDef | ast.AsyncFunctionDef)
    ]

    list_problems: list[str] = []
    dict_annotation_aliases: dict[str, str] = {}
    set_reported: set[tuple[int, str]] = set()

    for cls_node in ast.walk(cls_tree):
        if not isinstance(cls_node, ast.Import | ast.ImportFrom):
            continue
        for str_root, str_alias in imported_names(cls_node):
            if str_root in sys.stdlib_module_names or str_root in set_first_party:
                continue
            if str_root in dict_allow:
                continue
            if str_root in dict_annotation_only:
                dict_annotation_aliases[str_alias] = str_root
                continue
            # One statement binding several names is ONE violation, not one per name.
            if (cls_node.lineno, str_root) in set_reported:
                continue
            set_reported.add((cls_node.lineno, str_root))

            bool_in_function = any(a < cls_node.lineno <= b for a, b in list_functions)
            str_where = " (inside a function — deferring the import does not change the verdict)"
            list_problems.append(
                f"{path_file}:{cls_node.lineno}: '{str_root}' is not allowed in layer "
                f"'{str_layer}'{str_where if bool_in_function else ''}. "
                f"Reach it through a seam in utils/, or add it to '{str_layer}'.allow in "
                f"{_POLICY_FILE} with a written reason."
            )

    for str_alias, str_root in dict_annotation_aliases.items():
        for cls_node in ast.walk(cls_tree):
            if not isinstance(cls_node, ast.Name) or cls_node.id != str_alias:
                continue
            if id(cls_node) in set_annotation_ids:
                continue
            list_problems.append(
                f"{path_file}:{cls_node.lineno}: '{str_root}' may be used as a TYPE only in "
                f"layer '{str_layer}' — this is a call/attribute use. "
                f"{dict_annotation_only.get(str_root, '')}"
            )
    return list_problems


def main() -> int:
    """Check every module under ``src/`` against the layer policy.

    Returns
    -------
    int
        ``0`` when the tree complies (or no policy is present), ``1`` otherwise.
    """
    path_root = pathlib.Path.cwd()
    dict_policy = load_policy(path_root)
    if dict_policy is None:
        return 0

    path_src = path_root / _SRC_ROOT
    if not path_src.is_dir():
        return 0

    set_first_party = first_party_roots(path_src, dict_policy)
    list_all: list[str] = []
    for path_file in sorted(path_src.rglob("*.py")):
        if "__pycache__" in path_file.parts:
            continue
        tuple_rel = path_file.relative_to(path_src).parts
        if len(tuple_rel) < 2:
            continue
        list_all.extend(
            find_file_problems(path_file, tuple_rel[0], dict_policy, set_first_party)
        )

    for str_problem in list_all:
        print(f"❌ {str_problem}")
    if list_all:
        print(f"\n{len(list_all)} layer-import violation(s).")
        return 1
    return 0


if __name__ == "__main__":
    # Windows' stdout defaults to cp1252, which cannot encode the status glyphs this
    # script prints: it would die with UnicodeEncodeError before reporting anything. And
    # because this backs an always_run pre-commit hook, that crash blocks EVERY commit from
    # a Windows checkout rather than failing the file under check. Fixed at the I/O seam so
    # the glyphs stay; a test pins it with PYTHONIOENCODING=cp1252.
    for _cls_stream in (sys.stdout, sys.stderr):
        if hasattr(_cls_stream, "reconfigure"):
            _cls_stream.reconfigure(encoding="utf-8", errors="replace")

    sys.exit(main())
