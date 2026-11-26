"""Detect a PR that turns a red test green by weakening its assertion (blueprintx#324).

THE DEFECT. `check_gate_integrity.py` (blueprintx#309/#313) watches CONFIGURATION — a
pre-commit hook removed, a rule dropped from `ruff.toml`. But the cheapest way to make a red
build green is not in any config file, it is editing the assertion itself:

    - assert to_decimal_strict("1.999", 2) == Decimal("1.99")
    + assert to_decimal_strict("1.999", 2) == Decimal("2.00")

That diff turns a money-truncation BUG into a green suite, and nothing in the repo objects.
blueprintx#323 hit exactly this shape for real, and blueprintx#289's review caught a human
doing the operator-level version by hand (`==` weakened to `in`).

WHY A NEW FILE, NOT AN EXTENSION OF `check_gate_integrity.py`. The two files audit different
QUESTIONS (config weakening vs. assertion weakening). This file duplicates a small slice of
that script's git-diffing plumbing (`_git`, `show`, `changed_paths`, `default_branch`,
`resolve_base`, `pr_body_text`, `apply_root_flag`) rather than importing a sibling gate, which
would couple it to an interface that may move.

WHAT IS DECIDABLE (measured against real history before being written — see the PR body for
the count). Comparing an assertion's AST shape between the merge-base version of a test file
and the index (staged/HEAD) version, for a function whose name is unchanged, catches:

- a test function DELETED, or a whole test file deleted
- a test's assertion COUNT decreased (an assertion removed) between old and new
- an assertion trivialised to a bare truthy constant (`assert True`)
- an `==` comparison weakened by OPERATOR to `in` / `not in` / `>` / `<` / `>=` / `<=` / `!=`
  (blueprintx#289's live example)
- a `self.assertEqual`-family call weakened to a looser call (`assertTrue`,
  `assertIsNotNone`, `assertIn`, ...)
- `pytest.raises(<SpecificError>)` broadened to no type, `Exception`, or `BaseException`
- a `@pytest.mark.skip` / `skipif` / `xfail` marker or a `pytest.skip()` call, newly added to a
  test that did not carry it
- an `assertEqual`/`==` EXPECTED VALUE changed on one side while a non-test file *also*
  changed in the same diff — the #323 shape. Gated on production code changing in the same
  diff on purpose: a test correction in a PR that touches no production code is legitimate
  and must pass (issue's should-fail witness #3).

NOT decidable, and deliberately not attempted: whether a changed value is the *right* one.
That requires knowing what the test means, which a gate cannot know and must not guess.

MATCHING IS POSITIONAL, not semantic. Assertions inside one function are compared by their
appearance ORDER, old vs new. A reordering that leaves the same set of checks intact can
misreport — noted as the one deliberate simplification measurement did not need to narrow
further (ponytail: escape hatch below covers the rare false positive).

OUT OF SCOPE, deliberately: a skip applied from a fixture or from ``conftest.py`` (an autouse
fixture that calls ``pytest.skip()``, ``pytest_collection_modifyitems`` adding a marker). The
gate compares one test file against its merge-base version and never reads a second file, so
such a skip is invisible to it. The same holds for a guard whose evaluation time differs from
its spelling (a module-level ``skipif(flag)`` and a run-time ``if flag: pytest.skip()`` share
the label ``skip(if):flag``) and for ``and``/``or`` operands, which are compared sorted and so
ignore short-circuit order.

THE ESCAPE HATCH mirrors `check_gate_integrity.py`'s convention: a `test-change-ok: <reason>`
line, with a non-empty reason, in the PR body (`GITHUB_EVENT_PATH`) or as a trailer on any
commit since the merge-base. The PR body is CI-only, and the commit being created cannot
carry its own trailer at `pre-commit` time (earlier branch commits' trailers are read).
Locally, set `TEST_CHANGE_OK='<reason>'` for the commit (blueprintx#941); it is ignored
unless the run is a local `pre-commit` with a terminal and no CI marker (`gate_env.is_ci`, #981).

CI must check out with `fetch-depth: 0` — a shallow clone has no common ancestor to resolve.
"""

import ast
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from gate_env import is_ci, no_terminal_note  # noqa: E402
from gate_rename import deleted_message, rename_pairs  # noqa: E402


PATH_ROOT = pathlib.Path(__file__).resolve().parent.parent


RE_JUSTIFICATION = re.compile(r"^\s*test-change-ok:\s*(\S.*)$", re.I | re.M)
RE_TEST_PATH = re.compile(r"(^|/)tests/.*test_[^/]+\.py$")
RE_DOC_PATH = re.compile(r"\.md$|(^|/)docs/")
RE_TEST_TREE = re.compile(r"(^|/)tests/")

STR_INDEX_REF = ""

_SKIP_MARKERS = frozenset({"skip", "skipif", "xfail"})
_RUNTIME_OFF = frozenset({"skip", "importorskip", "xfail"})
_BOUND_FROM_PYTEST = frozenset({"mark", *_RUNTIME_OFF})
_APPLY_MARKER_METHODS = frozenset({"applymarker", "add_marker"})
_DEFAULT_NAMES = {"pytest": "pytest", **{str_n: str_n for str_n in _RUNTIME_OFF}}

_INT_MIN_FIELDS = 2
_MIN_EQ_ARGS = 2

_OP_SYMBOLS = {
    "In": "in",
    "NotIn": "not in",
    "Gt": ">",
    "Lt": "<",
    "GtE": ">=",
    "LtE": "<=",
    "NotEq": "!=",
}
_WEAK_FROM_EQ = frozenset(_OP_SYMBOLS)

_WEAKER_ASSERT_CALLS = {
    "assertEqual": frozenset(
        {
            "assertTrue",
            "assertIsNotNone",
            "assertIn",
            "assertIsInstance",
            "assertFalse",
            "assertIsNone",
            "assertGreater",
            "assertLess",
            "assertGreaterEqual",
            "assertLessEqual",
        }
    ),
    "assertIs": frozenset({"assertIsNotNone", "assertTrue"}),
    "assertListEqual": frozenset({"assertTrue", "assertIn"}),
    "assertDictEqual": frozenset({"assertTrue", "assertIn"}),
}


def _git(list_args: list) -> str:
    """Run a read-only git command and return stdout (empty string on failure).

    Parameters
    ----------
    list_args : list of str
        Arguments after ``git``.

    Returns
    -------
    str
        Captured stdout, stripped.
    """
    try:
        cls_proc = subprocess.run(  # noqa: S603
            ["git", *list_args],  # noqa: S607
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            cwd=PATH_ROOT,
        )
    except OSError:
        return ""
    return cls_proc.stdout


def show(str_ref: str, *, str_path: str) -> str | None:
    """Return a blob's text content at a git ref/path, or ``None`` when unreadable.

    Parameters
    ----------
    str_ref : str
        A commit-ish, or ``""`` for the index (``STR_INDEX_REF``).
    str_path : str
        Repository-relative path.

    Returns
    -------
    str or None
        The blob's content; ``None`` when ``git show`` exits non-zero (no such path there) or
        the blob is not valid UTF-8 (mirrors ``check_gate_integrity.py::show``: a binary defines
        nothing to compare). A ``git`` that cannot be spawned raises, so the gate stops instead
        of reporting a comparison it never made.
    """
    cls_proc = subprocess.run(  # noqa: S603
        ["git", "show", f"{str_ref}:{str_path}"],  # noqa: S607
        capture_output=True,
        check=False,
        cwd=PATH_ROOT,
    )
    if cls_proc.returncode != 0:
        return None
    try:
        return cls_proc.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None


def default_branch() -> str:
    """Return a resolvable ref for the repository's default branch.

    Returns
    -------
    str
        ``origin/<name>`` when only the remote-tracking branch exists, else a local
        ``<name>``; falls back to the literal ``"main"``. See
        ``check_gate_integrity.py::default_branch`` (blueprintx#313) for why the remote
        prefix is kept rather than stripped.
    """
    str_ref = _git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"]).strip()
    if str_ref:
        return str_ref
    for str_candidate in ("main", "master"):
        for str_full in (f"origin/{str_candidate}", str_candidate):
            if _git(["rev-parse", "--verify", "--quiet", str_full]).strip():
                return str_full
    return "main"


def changed_paths(str_base: str) -> list:
    """Return the branch's cumulative changed paths with their status, INDEX included.

    Parameters
    ----------
    str_base : str
        The merge-base commit to diff against.

    Returns
    -------
    list of tuple
        ``(status_letter, source_path, destination_path)``. The two paths differ only for
        a rename; the base version lives at the source, the head version at the
        destination (blueprintx#590).
    """
    str_out = _git(["diff", "--cached", "--name-status", "--find-renames", str_base])
    list_rows = []
    for str_line in str_out.splitlines():
        list_parts = str_line.split("\t")
        if len(list_parts) >= _INT_MIN_FIELDS:
            list_rows.append((list_parts[0][0], list_parts[1], list_parts[-1]))
    return list_rows


def pr_body_text() -> str:
    """Return the current PR's body from the GitHub Actions event payload (I/O seam).

    Returns
    -------
    str
        The PR body, or ``""`` outside a ``pull_request`` workflow run.
    """
    str_event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not str_event_path:
        return ""
    try:
        dict_event = json.loads(pathlib.Path(str_event_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    dict_pr = dict_event.get("pull_request") or {}
    return str(dict_pr.get("body") or "")


def env_reason() -> str:
    """Return the ``TEST_CHANGE_OK`` reason from the environment, or ``""`` (I/O seam).

    Returns
    -------
    str
        The non-empty, stripped value of ``TEST_CHANGE_OK`` — the one escape hatch reachable
        at local ``pre-commit`` time (blueprintx#941), with the same intent as ``GATE_CHANGE_OK``
        in ``check_gate_integrity.py`` (both share ``gate_env.is_ci``, #981).
        ``""`` under CI, so a workflow ``env:`` line cannot stand in for a justification a PR
        reviewer can read.
    """
    if is_ci():
        return ""
    return os.environ.get("TEST_CHANGE_OK", "").strip()


def justification_reason(str_base: str) -> str:
    """Return the ``test-change-ok`` reason from the env, the PR body or a commit trailer.

    Parameters
    ----------
    str_base : str
        The merge-base commit — commit messages since it are searched for a trailer.

    Returns
    -------
    str
        The non-empty reason text, or ``""`` when no valid justification is present. The
        ``TEST_CHANGE_OK`` environment variable is checked first: it needs neither a
        finished commit nor a PR.
    """
    str_env = env_reason()
    if str_env:
        return str_env
    str_trailers = _git(["log", "--encoding=UTF-8", f"{str_base}..HEAD", "--format=%B"])
    for str_text in (pr_body_text(), str_trailers):
        cls_match = RE_JUSTIFICATION.search(str_text)
        if cls_match and cls_match.group(1).strip():
            return cls_match.group(1).strip()
    return ""


def apply_root_flag(list_argv: list) -> bool:
    """Parse a leading ``--root <dir>`` flag, updating ``PATH_ROOT`` in place.

    Parameters
    ----------
    list_argv : list of str
        The raw argv tail.

    Returns
    -------
    bool
        ``False`` on bad usage (already reported to stdout); ``True`` otherwise.
    """
    global PATH_ROOT  # noqa: PLW0603
    if list_argv[:1] != ["--root"]:
        return True
    if len(list_argv) < 2:  # noqa: PLR2004
        print("❌ --root needs a directory")
        return False
    PATH_ROOT = pathlib.Path(list_argv[1]).resolve()
    return True


def merge_heads() -> list:
    """Return every incoming commit of a merge in progress (several for an octopus).

    Mid-merge the index already holds the incoming side's files but HEAD is still the
    pre-merge tip, so a base taken from HEAD alone charges the incoming delta to this branch.
    ``rev-parse MERGE_HEAD`` resolves only the first line, so the file itself is read.

    Returns
    -------
    list of str
        One commit hash per incoming head; empty when no merge is in progress.
    """
    str_path = _git(["rev-parse", "--git-path", "MERGE_HEAD"]).strip()
    path_file = pathlib.Path(str_path) if str_path else None
    if path_file is None:
        return []
    if not path_file.is_absolute():
        path_file = PATH_ROOT / path_file
    return path_file.read_text(encoding="utf-8").split() if path_file.is_file() else []


def resolve_base() -> str | None:
    """Resolve the merge-base to diff against.

    Returns
    -------
    str or None
        ``None`` means a real skip: HEAD already IS the resolved ref. An empty string means
        no ref could be resolved at all, and is never treated as a skip — ``main()`` fails
        the run on it instead of passing it silently (mirrors blueprintx#313).
    """
    str_ref = default_branch()
    str_base = _git(["merge-base", str_ref, "HEAD", *merge_heads()]).strip()
    if not str_base:
        print(f"❌ could not resolve a merge-base against {str_ref!r} — refusing to pass blind.")
        return ""
    str_head = _git(["rev-parse", "HEAD"]).strip()
    if str_base == str_head:
        print("✅ assertion-weakening check skipped — on the default branch (nothing to diff).")
        return None
    return str_base


def _dump(node: ast.AST) -> str:
    """Return a location-independent structural fingerprint of an AST node.

    Parameters
    ----------
    node : ast.AST
        Any expression node.

    Returns
    -------
    str
        ``ast.dump`` output with no line/column noise, so two structurally identical
        expressions compare equal regardless of where they sit in the file.
    """
    return ast.dump(node, annotate_fields=False, include_attributes=False)


def _is_trivial_assert_test(node_test: ast.expr) -> bool:
    """Return whether an ``assert`` test is a bare truthy constant (``assert True``, ``1``).

    Parameters
    ----------
    node_test : ast.expr
        The expression after ``assert``.

    Returns
    -------
    bool
        ``True`` only for a truthy ``ast.Constant`` — an assertion that can never fail.
    """
    return isinstance(node_test, ast.Constant) and bool(node_test.value)


def _call_attr(node_call: ast.Call) -> str | None:
    """Return a call's method name when it is an attribute call (``self.assertX(...)``).

    Parameters
    ----------
    node_call : ast.Call
        The call node.

    Returns
    -------
    str or None
        The attribute name, or ``None`` for a bare-name call.
    """
    func = node_call.func
    return func.attr if isinstance(func, ast.Attribute) else None


def _is_assert_call(node_call: ast.Call) -> bool:
    """Return whether a call is a unittest-style ``self.assertX(...)`` assertion.

    Parameters
    ----------
    node_call : ast.Call
        The call node.

    Returns
    -------
    bool
        ``True`` when the attribute name starts with ``assert``.
    """
    str_attr = _call_attr(node_call)
    return str_attr is not None and str_attr.startswith("assert")


def _raises_func_name(node_call: ast.Call) -> str | None:
    """Return the callable name of a context-manager call (``pytest.raises`` / ``raises``).

    Parameters
    ----------
    node_call : ast.Call
        A ``with`` item's context expression.

    Returns
    -------
    str or None
        ``"raises"`` when matched, else ``None``.
    """
    func = node_call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _is_raises_with(node_with: ast.With) -> bool:
    """Return whether a ``with`` block is a ``pytest.raises(...)`` context.

    Parameters
    ----------
    node_with : ast.With
        The ``with`` statement.

    Returns
    -------
    bool
        ``True`` when any item's context expression calls ``raises``.
    """
    for item in node_with.items:
        expr = item.context_expr
        if isinstance(expr, ast.Call) and _raises_func_name(expr) == "raises":
            return True
    return False


def _raises_exception_name(node_with: ast.With) -> str | None:
    """Return the exception type name a ``pytest.raises(...)`` block declares.

    Parameters
    ----------
    node_with : ast.With
        A ``with`` statement already known to be a ``raises`` context.

    Returns
    -------
    str or None
        The exception name (``"tuple"`` for a multi-type tuple), or ``None`` when
        ``raises`` was called with no positional exception type.
    """
    for item in node_with.items:
        expr = item.context_expr
        if not (isinstance(expr, ast.Call) and _raises_func_name(expr) == "raises"):
            continue
        list_kw = [kw.value for kw in expr.keywords if kw.arg == "expected_exception"]
        list_exc = expr.args or list_kw
        if not list_exc:
            return None
        arg0 = list_exc[0]
        if isinstance(arg0, ast.Name):
            return arg0.id
        if isinstance(arg0, ast.Attribute):
            return arg0.attr
        if isinstance(arg0, ast.Tuple):
            return "tuple"
        return None
    return None


def _function_checks(node_fn: ast.FunctionDef) -> list:
    """Return the ordered ``(kind, node)`` assertion-like checks inside a function.

    Parameters
    ----------
    node_fn : ast.FunctionDef
        The test function (or method).

    Returns
    -------
    list of tuple
        ``("assert" | "call" | "raises", ast.AST)``, in source order. Does not descend
        into nested function/lambda definitions — those are their own unit.
    """
    list_checks: list = []

    def _walk(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
                continue
            if isinstance(child, ast.Assert):
                list_checks.append(("assert", child))
            elif isinstance(child, ast.With) and _is_raises_with(child):
                list_checks.append(("raises", child))
            elif (
                isinstance(child, ast.Expr)
                and isinstance(child.value, ast.Call)
                and _is_assert_call(child.value)
            ):
                list_checks.append(("call", child.value))
            _walk(child)

    _walk(node_fn)
    return list_checks


def _skip_or_xfail_markers(
    node_fn: ast.FunctionDef, *, dict_names: dict[str, str] | None = None
) -> set:
    """Return the ``skip``/``xfail`` marker names decorating a test function.

    Parameters
    ----------
    node_fn : ast.FunctionDef
        The test function.
    dict_names : dict of str to str, optional
        The module's pytest name table; the unaliased names when omitted.

    Returns
    -------
    set of str
        Decorator labels (``skip``, ``xfail``, ``skipif:<condition>``), plus ``skip()`` for a
        ``pytest.skip(...)`` call outside any ``if`` and ``skip(if):<test>`` for a guarded one.
    """
    dict_known = _local_names(
        node_fn, dict_names=_DEFAULT_NAMES if dict_names is None else dict_names
    )
    set_out = _marker_labels(node_fn.decorator_list)
    set_out.update(_body_skip_labels(node_fn.body, tuple_guards=(), dict_names=dict_known))
    return set_out


def _local_names(node_fn: ast.FunctionDef, *, dict_names: dict[str, str]) -> dict[str, str]:
    """Return the pytest name table as the body of a function sees it.

    Parameters
    ----------
    node_fn : ast.FunctionDef
        The test function.
    dict_names : dict of str to str
        The module's pytest name table.

    Returns
    -------
    dict of str to str
        A copy where a parameter (a fixture named ``skip``) shadows the module name and the
        function's own imports and assignments rebind it, as at module level.
    """
    dict_local = dict(dict_names)
    cls_args = node_fn.args
    for cls_arg in [*cls_args.posonlyargs, *cls_args.args, *cls_args.kwonlyargs]:
        dict_local.pop(cls_arg.arg, None)
    for cls_extra in (cls_args.vararg, cls_args.kwarg):
        dict_local.pop(cls_extra.arg if cls_extra else "", None)
    return _scoped_names(node_fn.body, dict_start=dict_local)


def _marker_labels(list_exprs: list) -> set:
    """Return the labels of the ``skip``/``skipif``/``xfail`` markers among some expressions.

    Parameters
    ----------
    list_exprs : list of ast.expr
        Decorators, or the value of a ``pytestmark`` assignment.

    Returns
    -------
    set of str
        One label per marker; anything that is not such a marker adds none.
    """
    set_out = set()
    for dec in list_exprs:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr in _SKIP_MARKERS:
            set_out.add(_marker_label(dec, str_name=target.attr))
    return set_out


def _body_skip_labels(
    list_body: list, *, tuple_guards: tuple[str, ...], dict_names: dict[str, str]
) -> set:
    """Return the labels of ``pytest.skip()`` calls in a body, nested defs and lambdas excluded.

    Parameters
    ----------
    list_body : list
        Statements (or expressions) to read.
    tuple_guards : tuple of str
        The enclosing guards, outermost first; empty when the call always runs.
    dict_names : dict of str to str
        The module's pytest name table, from ``_pytest_names``.

    Returns
    -------
    set
        ``skip()`` (or ``importorskip()``/``xfail()``) for an unguarded call, ``skip(if):<guards>``
        otherwise.
        ``with`` and a ``try`` body are not guards; an ``except`` handler, an ``else``, a loop
        or ``match`` body, a ``try`` ``else``, an ``if``/conditional-expression branch are.
    """
    set_out = set()
    for node in list_body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef):
            continue
        str_call = _skip_call_name(node, dict_names=dict_names)
        if str_call:
            set_out.add(_skip_label(tuple_guards, str_call=str_call))
        for list_child, tuple_inner in _guarded_children(node, tuple_guards=tuple_guards):
            set_out |= _body_skip_labels(
                list_child, tuple_guards=tuple_inner, dict_names=dict_names
            )
    return set_out


def _canon_node(cls_node: ast.expr) -> ast.expr:
    """Return a condition in a form two spellings of the same guard share.

    Parameters
    ----------
    cls_node : ast.expr
        A guard or marker condition.

    Returns
    -------
    ast.expr
        A string condition (``skipif("sys.platform == 'win32'")``) parsed to the expression it
        evaluates, ``not not c`` reduced to ``c``, and the operands of ``and``/``or`` sorted, so
        ``a and b`` equals ``b and a``.
    """
    if isinstance(cls_node, ast.UnaryOp) and isinstance(cls_node.op, ast.Not):
        cls_inner = cls_node.operand
        is_double = isinstance(cls_inner, ast.UnaryOp) and isinstance(cls_inner.op, ast.Not)
        if is_double:
            return _canon_node(cls_inner.operand)
        return ast.UnaryOp(op=ast.Not(), operand=_canon_node(cls_inner))
    if not isinstance(cls_node, ast.BoolOp):
        return cls_node
    list_flat: list[ast.expr] = []
    for cls_value in map(_canon_node, cls_node.values):
        is_same_op = isinstance(cls_value, ast.BoolOp) and isinstance(
            cls_value.op, type(cls_node.op)
        )
        list_flat.extend(cls_value.values if is_same_op else [cls_value])
    if any(isinstance(cls_sub, ast.NamedExpr) for cls_sub in ast.walk(cls_node)):
        return ast.BoolOp(op=cls_node.op, values=list_flat)
    return ast.BoolOp(op=cls_node.op, values=sorted(list_flat, key=ast.unparse))


def _canon(cls_node: ast.expr) -> str:
    """Return the source text of a condition after ``_canon_node``.

    Parameters
    ----------
    cls_node : ast.expr
        A guard or marker condition.

    Returns
    -------
    str
        The canonical source.
    """
    return ast.unparse(_canon_node(cls_node))


def _marker_canon(cls_node: ast.expr) -> str:
    """Return ``_canon`` of a marker condition, parsing a top-level string as pytest evaluates it.

    Parameters
    ----------
    cls_node : ast.expr
        An argument of ``skipif``/``xfail``.

    Returns
    -------
    str
        The canonical source; a string is only an expression here, a truthy constant in a guard.
    """
    if isinstance(cls_node, ast.Constant) and isinstance(cls_node.value, str):
        try:
            return _canon(ast.parse(cls_node.value, mode="eval").body)
        except (SyntaxError, ValueError):
            pass
    return _canon(cls_node)


def _join_conditions(list_text: list[str], *, cls_op: ast.boolop) -> str:
    """Join condition sources with ``and``/``or``, parenthesising exactly where precedence needs.

    Parameters
    ----------
    list_text : list of str
        Condition sources; a guard that is not an expression (``except X``) is kept whole.
    cls_op : ast.boolop
        ``ast.And()`` or ``ast.Or()``.

    Returns
    -------
    str
        The joined source, the sole condition unchanged.
    """
    if len(list_text) == 1:
        return list_text[0]
    try:
        list_nodes = [ast.parse(str_t, mode="eval").body for str_t in list_text]
    except SyntaxError:
        str_op = " and " if isinstance(cls_op, ast.And) else " or "
        return str_op.join(f"({str_t})" for str_t in list_text)
    list_flat = [
        cls_leaf
        for cls_node in list_nodes
        for cls_leaf in (
            cls_node.values
            if isinstance(cls_node, ast.BoolOp) and isinstance(cls_node.op, type(cls_op))
            else [cls_node]
        )
    ]
    return _canon(ast.BoolOp(op=cls_op, values=list_flat))


def _skip_label(tuple_guards: tuple[str, ...], *, str_call: str) -> str:
    """Return ``<call>()`` for no guards, else ``<call>(if):`` and the guards joined by ``and``.

    Parameters
    ----------
    tuple_guards : tuple of str
        The enclosing guards.
    str_call : str
        ``skip``, ``importorskip`` or ``xfail``.

    Returns
    -------
    str
        The label.
    """
    if not tuple_guards:
        return f"{str_call}()"
    return f"{str_call}(if):" + _join_conditions(list(tuple_guards), cls_op=ast.And())


def _guarded_children(node: ast.AST, *, tuple_guards: tuple[str, ...]) -> list:
    """Split a node's children by the guard each one runs under.

    Parameters
    ----------
    node : ast.AST
        Any node.
    tuple_guards : tuple of str
        The guards enclosing the node.

    Returns
    -------
    list
        ``(children, guards)`` pairs.
    """
    if isinstance(node, ast.If | ast.IfExp):
        str_test = _canon(node.test)
        list_body = node.body if isinstance(node.body, list) else [node.body]
        list_else = node.orelse if isinstance(node.orelse, list) else [node.orelse]
        return [
            ([node.test], tuple_guards),
            (list_body, (*tuple_guards, str_test)),
            (list_else, (*tuple_guards, _canon(ast.UnaryOp(op=ast.Not(), operand=node.test)))),
        ]
    if isinstance(node, ast.Try | ast.TryStar):
        return [
            ([*node.body, *node.finalbody], tuple_guards),
            *[
                (
                    cls_handler.body,
                    (
                        *tuple_guards,
                        _except_guard(node, cls_handler=cls_handler, str_after=_try_calls(node)),
                    ),
                )
                for cls_handler in node.handlers
            ],
            (node.orelse, (*tuple_guards, "try-else")),
        ]
    if isinstance(node, ast.Match):
        return [
            ([node.subject], tuple_guards),
            *[
                (
                    [*([cls_case.guard] if cls_case.guard else []), *cls_case.body],
                    (*tuple_guards, _case_guard(node, cls_case=cls_case)),
                )
                for cls_case in node.cases
            ],
        ]
    if isinstance(node, ast.BoolOp):
        return [
            ([cls_value], (*tuple_guards, *_short_circuit_guards(node, int_index=int_index)))
            for int_index, cls_value in enumerate(node.values)
        ]
    str_kind = _guard_kind(node)
    tuple_inner = (*tuple_guards, str_kind) if str_kind else tuple_guards
    return [(list(ast.iter_child_nodes(node)), tuple_inner)]


def _except_guard(
    cls_try: ast.Try | ast.TryStar, *, cls_handler: ast.ExceptHandler, str_after: str
) -> str:
    """Return the guard of an ``except`` body: its type and a key of its ``try`` body.

    Two handlers for the same type guard different failures when the ``try`` bodies differ, so
    the type alone would let one stand in for the other.

    Parameters
    ----------
    cls_try : ast.Try or ast.TryStar
        The statement that owns the handler.
    cls_handler : ast.ExceptHandler
        One of its handlers.
    str_after : str
        The key of the ``try`` body: its callees (``_try_calls``) for a test body, where an edited
        argument must not re-report an unchanged handler, a digest of the whole statement for a
        module-level ``pytestmark``, where two ``try`` blocks with no call must stay distinct.

    Returns
    -------
    str
        ``except <type> after <key>``.
    """
    str_caught = ast.unparse(cls_handler.type) if cls_handler.type else ""
    list_before = [
        ast.unparse(cls_prior.type) if cls_prior.type else ""
        for cls_prior in cls_try.handlers[: cls_try.handlers.index(cls_handler)]
    ]
    str_type = f"except {str_caught}".strip()
    if list_before:
        str_type += " not after " + ",".join(list_before)
    return f"{str_type} after {str_after}"


def _try_calls(cls_try: ast.Try | ast.TryStar) -> str:
    """Return the sorted callee names a ``try`` body calls, the key of its ``except`` guards.

    Parameters
    ----------
    cls_try : ast.Try or ast.TryStar
        The statement that owns the handlers.

    Returns
    -------
    str
        ``f(), g()`` for the distinct callees plus the module, level and names of each import,
        ``nothing`` for a body with neither. Editing an argument leaves the key alone, so an
        unchanged ``except E: pytest.skip()`` is not reported again; adding or removing a callee
        or import changes it. Known limit, accepted for that trade: a second ``try`` that calls
        the same callees and catches the same type shares the first one's label, so a skip added
        there is not reported while the first one stays.
    """
    set_names: set[str] = set()
    for cls_stmt in cls_try.body:
        for cls_node in ast.walk(cls_stmt):
            if isinstance(cls_node, ast.Call):
                set_names.add(f"{ast.unparse(cls_node.func)}()")
            elif isinstance(cls_node, ast.Import):
                set_names.add("import " + ",".join(cls_a.name for cls_a in cls_node.names))
            elif isinstance(cls_node, ast.ImportFrom):
                str_from = "." * cls_node.level + (cls_node.module or "")
                set_names.add(
                    f"from {str_from} import " + ",".join(cls_a.name for cls_a in cls_node.names)
                )
    return ", ".join(sorted(set_names)) or "nothing"


def _case_guard(cls_match: ast.Match, *, cls_case: ast.match_case) -> str:
    """Return the guard of a ``case`` body: the subject, the pattern and the ``if`` guard.

    Parameters
    ----------
    cls_match : ast.Match
        The ``match`` statement.
    cls_case : ast.match_case
        One of its cases.

    Returns
    -------
    str
        ``match <subject>: <pattern>``, plus `` if <guard>`` when the case has one.
    """
    str_guard = f" if {_canon(cls_case.guard)}" if cls_case.guard else ""
    return f"match {ast.unparse(cls_match.subject)}: {ast.unparse(cls_case.pattern)}{str_guard}"


def _short_circuit_guards(cls_bool: ast.BoolOp, *, int_index: int) -> tuple[str, ...]:
    """Return what must hold for operand ``int_index`` of ``a and b`` / ``a or b`` to be evaluated.

    Parameters
    ----------
    cls_bool : ast.BoolOp
        The expression.
    int_index : int
        Position of the operand.

    Returns
    -------
    tuple of str
        Every earlier operand for ``and``, every earlier operand negated for ``or``; empty for
        the first operand, which always runs.
    """
    list_before = cls_bool.values[:int_index]
    if isinstance(cls_bool.op, ast.And):
        return tuple(_canon(cls_value) for cls_value in list_before)
    return tuple(_canon(ast.UnaryOp(op=ast.Not(), operand=cls_value)) for cls_value in list_before)


def _guard_kind(node: ast.AST) -> str | None:
    """Return a guard text for a node whose children may not run, ``None`` otherwise.

    Parameters
    ----------
    node : ast.AST
        Any node.

    Returns
    -------
    str or None
        ``for <iterable>`` or the ``while`` test (``while True`` is no guard).
    """
    if isinstance(node, ast.For | ast.AsyncFor):
        return f"for {ast.unparse(node.iter)}"
    if isinstance(node, ast.While):
        is_always = isinstance(node.test, ast.Constant) and bool(node.test.value)
        return None if is_always else f"while {ast.unparse(node.test)}"
    return None


def _marker_label(dec: ast.expr, *, str_name: str) -> str:
    """Return the label of a marker decorator, carrying its condition where it has one.

    Parameters
    ----------
    dec : ast.expr
        The decorator expression.
    str_name : str
        The marker name after ``pytest.mark.``.

    Returns
    -------
    str
        ``skipif:<conditions joined by or>``; ``xfail:<conditions>`` plus ``;lax`` unless
        ``strict=True``; otherwise the bare name.
    """
    if str_name == "skip":
        return "skip"
    if not isinstance(dec, ast.Call):
        return "xfail:;lax" if str_name == "xfail" else str_name
    list_kw = [kw.value for kw in dec.keywords if kw.arg == "condition"]
    list_cond = list_kw or list(dec.args)
    str_cond = _join_conditions([_marker_canon(cond) for cond in list_cond], cls_op=ast.Or())
    if str_name == "skipif":
        return f"skipif:{str_cond}"
    is_strict = any(kw.arg == "strict" and ast.unparse(kw.value) == "True" for kw in dec.keywords)
    return f"xfail:{str_cond}{_xfail_scope(dec)}" + ("" if is_strict else ";lax")


def _xfail_scope(dec: ast.Call) -> str:
    """Return the ``raises=`` and ``run=`` arguments of an ``xfail`` as label text.

    Parameters
    ----------
    dec : ast.Call
        The ``xfail(...)`` decorator.

    Returns
    -------
    str
        ``;raises=<types>`` (a tuple sorted, so its order does not matter) and
        ``;run=<value>`` for the ones present, ``""`` for neither. A dropped
        ``raises`` lets any failure count as expected, and ``run=False`` stops
        the test from running at all, so both belong to the marker's identity.
    """
    dict_kw = {cls_kw.arg: ast.unparse(cls_kw.value) for cls_kw in dec.keywords}
    cls_raises = next((cls_kw.value for cls_kw in dec.keywords if cls_kw.arg == "raises"), None)
    if isinstance(cls_raises, ast.Tuple):
        dict_kw["raises"] = (
            "(" + ", ".join(sorted(ast.unparse(cls_t) for cls_t in cls_raises.elts)) + ")"
        )
    if dict_kw.get("run") == "True":
        del dict_kw["run"]
    return "".join(
        f";{str_key}={dict_kw[str_key]}" for str_key in ("raises", "run") if str_key in dict_kw
    )


def _marker_condition(str_marker: str) -> str | None:
    """Return the condition source of a conditional skip label, ``None`` for any other label.

    Parameters
    ----------
    str_marker : str
        A label from ``_skip_or_xfail_markers``.

    Returns
    -------
    str or None
        The text after ``skipif:`` or ``<call>(if):``.
    """
    cls_late = _RE_LATE_SKIPIF.match(str_marker)
    if cls_late:
        return cls_late.group(1)
    str_head, str_sep, str_tail = str_marker.partition(":")
    is_late = str_head.startswith("applymarker-")
    is_conditional = not is_late and (str_head == "skipif" or str_head.endswith("(if)"))
    return str_tail if str_sep and is_conditional else None


_RE_XFAIL_RAISES = re.compile(r";raises=([^;]*)")


_RE_LATE_SKIPIF = re.compile(r"^applymarker-skipif:(.*)\(\)$")


_RE_LATE_XFAIL = re.compile(r"^applymarker-(xfail:.*?)(\(\)|\(if\):.*)$")


def _xfail_tightens(str_new: str, *, set_old: set) -> bool:
    """Return whether an ``xfail`` label only tightens one the old test already carried.

    Parameters
    ----------
    str_new : str
        A label from the new version.
    set_old : set
        The labels before the change.

    Returns
    -------
    bool
        ``True`` when an old ``xfail`` on the same condition and ``run`` becomes ``strict`` or
        gains ``raises=``, and does not lose a ``raises=`` or become lax.
    """
    cls_late = _RE_LATE_XFAIL.match(str_new)
    if cls_late:
        set_same = {
            f"{cls_old.group(1)}"
            for str_old in set_old
            if (cls_old := _RE_LATE_XFAIL.match(str_old)) and cls_old.group(2) == cls_late.group(2)
        }
        return _xfail_tightens(cls_late.group(1), set_old=set_same)
    if not str_new.startswith("xfail:"):
        return False
    return any(
        _xfail_core(str_new)
        in {_xfail_core(str_old), _xfail_core(str_old).removesuffix(";run=False")}
        and (str_old.endswith(";lax") or not str_new.endswith(";lax"))
        and _xfail_raises(str_old) in {"", _xfail_raises(str_new)}
        for str_old in set_old
        if str_old.startswith("xfail:")
    )


def _xfail_core(str_label: str) -> str:
    """Return an ``xfail`` label without its ``;lax`` suffix and ``;raises=`` part.

    Parameters
    ----------
    str_label : str
        An ``xfail:`` label.

    Returns
    -------
    str
        The condition and ``run`` argument that identify the marker.
    """
    return _RE_XFAIL_RAISES.sub("", str_label.removesuffix(";lax"))


def _xfail_raises(str_label: str) -> str:
    """Return the ``raises=`` types of an ``xfail`` label, ``""`` when it names none.

    Parameters
    ----------
    str_label : str
        An ``xfail:`` label.

    Returns
    -------
    str
        The source text of the ``raises`` argument.
    """
    cls_match = _RE_XFAIL_RAISES.search(str_label)
    return cls_match.group(1) if cls_match else ""


def _newly_marked(*, set_old: set, set_new: set) -> set:
    """Return the labels newly added, minus restatements of what the old test already skipped.

    Parameters
    ----------
    set_old : set
        Labels before the change.
    set_new : set
        Labels after the change.

    Returns
    -------
    set
        Newly added labels. Adding ``strict=True`` to an ``xfail`` is a tightening, not a new
        marker. An unconditional ``skip``/``skip()`` is the same as the other
        spelling; a conditional skip is exempt when the old test was unconditionally skipped, or
        already skipped on the very same condition in the other form (``@skipif(c)`` and
        ``if c: pytest.skip()``).
    """
    set_added = {
        str_m for str_m in set_new - set_old if not _xfail_tightens(str_m, set_old=set_old)
    }
    set_conds = {_marker_condition(str_m) for str_m in set_old} - {None}
    has_unconditional = bool(set_old & {"skip", "skip()"})
    if has_unconditional:
        set_added -= {"skip", "skip()", "importorskip()", "xfail()"}
    if "skip" in set_old:
        set_added = {str_m for str_m in set_added if not str_m.startswith("xfail:")}
    return {
        str_m
        for str_m in set_added
        if not (
            (cond := _marker_condition(str_m)) is not None
            and (has_unconditional or cond in set_conds)
        )
    }


def _pytest_names(cls_tree: ast.Module) -> dict[str, str]:
    """Return the local names a module binds to pytest and to its run-time outcome functions.

    Parameters
    ----------
    cls_tree : ast.Module
        The parsed file.

    Returns
    -------
    dict of str to str
        ``{local name: "pytest"}`` for ``import pytest [as x]`` and ``{local name: function}``
        for ``from pytest import skip [as y]``, read from every statement that runs at import
        time, ``try``/``if`` and ``for``/``with``/``match`` bodies included. ``pytest`` and the
        bare ``skip``/``xfail``/``importorskip`` stay recognised unless the module defines or
        imports that name from somewhere else, which makes it a helper and not pytest's. A name
        that any guarded arm (``try``/``except``, ``if``/``else``) binds to pytest stays pytest's,
        whatever the other arms bind: arms are alternatives, not a sequence, and the gate errs
        toward reporting.
    """
    return _scoped_names(cls_tree.body, dict_start=_DEFAULT_NAMES)


def _scoped_names(list_body: list, *, dict_start: dict[str, str]) -> dict[str, str]:
    """Return the name table after a body, with a name any guarded arm binds to pytest kept.

    Parameters
    ----------
    list_body : list of ast.stmt
        The statements of a module or function body.
    dict_start : dict of str to str
        The table before the body.

    Returns
    -------
    dict of str to str
        A new table. Statements rebind in sequence, then every binding a ``try``/``if`` arm
        made wins: arms are alternatives, and the gate errs toward reporting.
    """
    dict_names = dict(dict_start)
    dict_guarded: dict[str, str] = {}
    for cls_stmt, str_guard in _flat_stmts(list_body):
        _bind_names(cls_stmt, dict_names=dict_names)
        if str_guard:
            dict_arm: dict[str, str] = {}
            _bind_names(cls_stmt, dict_names=dict_arm)
            dict_guarded.update(dict_arm)
    return {**dict_names, **dict_guarded}


def _bind_names(cls_stmt: ast.AST, *, dict_names: dict[str, str]) -> None:
    """Update the pytest name table for one statement.

    Parameters
    ----------
    cls_stmt : ast.AST
        A statement; compound ones are read by the caller through their bodies.
    dict_names : dict of str to str
        The table, changed in place.
    """
    if isinstance(cls_stmt, ast.Import):
        for cls_alias in cls_stmt.names:
            str_local = cls_alias.asname or cls_alias.name.split(".")[0]
            dict_names.pop(str_local, None)
            if cls_alias.name == "pytest":
                dict_names[str_local] = "pytest"
    elif isinstance(cls_stmt, ast.ImportFrom):
        for cls_alias in cls_stmt.names:
            str_local = cls_alias.asname or cls_alias.name
            is_pytest = cls_stmt.module == "pytest" and cls_alias.name in _BOUND_FROM_PYTEST
            dict_names.pop(str_local, None)
            if is_pytest:
                dict_names[str_local] = cls_alias.name
    elif isinstance(cls_stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        dict_names.pop(cls_stmt.name, None)
    else:
        _unbind_assigned(cls_stmt, dict_names=dict_names)


def _unbind_assigned(cls_stmt: ast.AST, *, dict_names: dict[str, str]) -> None:
    """Remove from the pytest name table every name an assignment rebinds.

    Parameters
    ----------
    cls_stmt : ast.AST
        A module-level statement; anything but an assignment changes nothing.
    dict_names : dict of str to str
        The table, changed in place.
    """
    if not isinstance(cls_stmt, ast.Assign | ast.AnnAssign | ast.AugAssign):
        return
    list_targets = cls_stmt.targets if isinstance(cls_stmt, ast.Assign) else [cls_stmt.target]
    for cls_target in list_targets:
        for cls_name in ast.walk(cls_target):
            if isinstance(cls_name, ast.Name):
                dict_names.pop(cls_name.id, None)


def _outcome_of(cls_func: ast.expr | None, *, dict_names: dict[str, str]) -> str | None:
    """Return the run-time outcome function an expression names, ``None`` for anything else.

    Parameters
    ----------
    cls_func : ast.expr or None
        The callee of a call, or the base of ``<outcome>.Exception``.
    dict_names : dict of str to str
        The module's pytest name table.

    Returns
    -------
    str or None
        ``skip``, ``importorskip`` or ``xfail`` for ``<pytest alias>.<name>`` or a bare imported
        name.
    """
    if isinstance(cls_func, ast.Name):
        str_kind = dict_names.get(cls_func.id, "")
        return str_kind if str_kind in _RUNTIME_OFF else None
    if isinstance(cls_func, ast.Attribute) and cls_func.attr in _RUNTIME_OFF:
        is_pytest = isinstance(cls_func.value, ast.Name) and (
            dict_names.get(cls_func.value.id) == "pytest"
        )
        return cls_func.attr if is_pytest else None
    return None


def _is_pytest_mark(cls_expr: ast.expr, *, dict_names: dict[str, str]) -> bool:
    """Return whether an expression is ``<pytest alias>.mark``.

    Parameters
    ----------
    cls_expr : ast.expr
        The receiver of a marker attribute.
    dict_names : dict of str to str
        The module's pytest name table.

    Returns
    -------
    bool
        ``True`` for ``pytest.mark`` through any alias the table knows, or a name imported with
        ``from pytest import mark``.
    """
    if isinstance(cls_expr, ast.Name):
        return dict_names.get(cls_expr.id) == "mark"
    return (
        isinstance(cls_expr, ast.Attribute)
        and cls_expr.attr == "mark"
        and isinstance(cls_expr.value, ast.Name)
        and dict_names.get(cls_expr.value.id) == "pytest"
    )


def _applied_marker(cls_call: ast.Call, *, dict_names: dict[str, str]) -> str | None:
    """Return a label for ``request.applymarker(pytest.mark.<name>(...))``.

    Parameters
    ----------
    cls_call : ast.Call
        Any call.
    dict_names : dict of str to str
        The module's pytest name table.

    Returns
    -------
    str or None
        ``applymarker-xfail:...`` for an ``xfail`` marker, ``applymarker-skipif:<condition>``
        for ``skipif`` (so moving ``@skipif(c)`` into the call stays the same condition),
        ``applymarker-skip`` for ``skip``; ``None`` when the call applies no such marker on
        ``pytest.mark``.
    """
    cls_func = cls_call.func
    if not (isinstance(cls_func, ast.Attribute) and cls_func.attr in _APPLY_MARKER_METHODS):
        return None
    cls_arg = cls_call.args[0] if cls_call.args else None
    cls_mark = cls_arg.func if isinstance(cls_arg, ast.Call) else cls_arg
    if not (isinstance(cls_mark, ast.Attribute) and cls_mark.attr in _SKIP_MARKERS):
        return None
    if not _is_pytest_mark(cls_mark.value, dict_names=dict_names):
        return None
    if cls_mark.attr == "skip":
        return "applymarker-skip"
    return "applymarker-" + _marker_label(cls_arg, str_name=cls_mark.attr)


def _skip_call_name(node: ast.AST, *, dict_names: dict[str, str] | None = None) -> str | None:
    """Return ``skip``, ``importorskip`` or ``xfail`` for code that turns a test off at run time.

    Parameters
    ----------
    node : ast.AST
        Any node.
    dict_names : dict of str to str, optional
        The module's pytest name table; the unaliased names when omitted.

    Returns
    -------
    str or None
        The function name for ``pytest.<name>(...)``, a bare ``<name>(...)`` (the
        ``from pytest import skip`` spelling), either through an import alias, a
        ``raise pytest.skip.Exception(...)``, or ``request.applymarker(pytest.mark.skip)``;
        ``None`` for anything else.
    """
    dict_known = _DEFAULT_NAMES if dict_names is None else dict_names
    if isinstance(node, ast.Raise):
        cls_exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
        is_outcome = isinstance(cls_exc, ast.Attribute) and cls_exc.attr == "Exception"
        return _outcome_of(cls_exc.value, dict_names=dict_known) if is_outcome else None
    if not isinstance(node, ast.Call):
        return None
    return _outcome_of(node.func, dict_names=dict_known) or _applied_marker(
        node, dict_names=dict_known
    )


def _is_literal_ish(node: ast.expr) -> bool:
    """Return whether a node is a literal, or a plain aggregate/call of literals.

    Parameters
    ----------
    node : ast.expr
        An expression to classify.

    Returns
    -------
    bool
        ``True`` for ``ast.Constant``, a signed constant, a tuple/list/set of literals,
        or a call (``Decimal("1.99")``, ``date(2026, 6, 8)``) whose every argument is
        itself literal-ish. ``False`` for anything referencing a name, attribute value,
        or subscript — those are CODE, not an expected value, and conflating the two is
        a measured false positive (a rewritten call-under-test wrongly read as a
        tampered expectation; see the module docstring's PR history note).
    """
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
        return _is_literal_ish(node.operand)
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        return all(_is_literal_ish(elt) for elt in node.elts)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name | ast.Attribute):
        return all(_is_literal_ish(a) for a in node.args) and all(
            _is_literal_ish(kw.value) for kw in node.keywords
        )
    return False


def _value_side_changed(cmp_old: ast.Compare, *, cmp_new: ast.Compare) -> bool:
    """Return whether a LITERAL side of an ``==`` comparison changed, the other unchanged.

    Parameters
    ----------
    cmp_old : ast.Compare
        The comparison at the merge-base.
    cmp_new : ast.Compare
        The comparison in this change.

    Returns
    -------
    bool
        ``True`` only when one side is unchanged CODE and the other side is a literal
        in both versions with a different value — an expected-value edit, never a
        rewrite of the call/expression under test (measured: ``dict_calls["n"]`` ->
        ``cls_call.call_count`` on an unchanged ``== 1`` must NOT fire; ``Decimal("1.99")``
        -> ``Decimal("2.00")`` on an unchanged left side MUST).
    """
    str_ol, str_nl = _dump(cmp_old.left), _dump(cmp_new.left)
    str_or, str_nr = _dump(cmp_old.comparators[0]), _dump(cmp_new.comparators[0])
    if str_ol == str_nl and str_or != str_nr:
        return _is_literal_ish(cmp_old.comparators[0]) and _is_literal_ish(cmp_new.comparators[0])
    if str_or == str_nr and str_ol != str_nl:
        return _is_literal_ish(cmp_old.left) and _is_literal_ish(cmp_new.left)
    return False


def _compare_assert(old_node: ast.Assert, *, new_node: ast.Assert, bool_prod_changed: bool) -> str:
    """Return a weakening message for an ``assert``-to-``assert`` pair, or ``""``.

    Parameters
    ----------
    old_node : ast.Assert
        The assertion at the merge-base.
    new_node : ast.Assert
        The assertion in this change.
    bool_prod_changed : bool
        Whether a non-test file also changed in this diff — gates the value-changed rule.

    Returns
    -------
    str
        A human-readable finding, or ``""`` when nothing decidable weakened.
    """
    cmp_old, cmp_new = old_node.test, new_node.test
    if _is_trivial_assert_test(cmp_new) and not _is_trivial_assert_test(cmp_old):
        return "trivialised to a bare truthy constant (assert True)"
    if not (isinstance(cmp_old, ast.Compare) and isinstance(cmp_new, ast.Compare)):
        return ""
    if len(cmp_old.ops) != 1 or len(cmp_new.ops) != 1:
        return ""
    str_old_op, str_new_op = type(cmp_old.ops[0]).__name__, type(cmp_new.ops[0]).__name__
    if str_old_op == "Eq" and str_new_op in _WEAK_FROM_EQ:
        return f"operator weakened from == to {_OP_SYMBOLS.get(str_new_op, str_new_op)}"
    bool_value_edit = str_old_op == "Eq" and str_new_op == "Eq" and bool_prod_changed
    if bool_value_edit and _value_side_changed(cmp_old, cmp_new=cmp_new):
        return "expected value changed while production code changed in the same diff"
    return ""


def _compare_call(old_node: ast.Call, *, new_node: ast.Call, bool_prod_changed: bool) -> str:
    """Return a weakening message for a unittest-style call pair, or ``""``.

    Parameters
    ----------
    old_node : ast.Call
        The ``self.assertX(...)`` call at the merge-base.
    new_node : ast.Call
        The call in this change.
    bool_prod_changed : bool
        Whether a non-test file also changed in this diff.

    Returns
    -------
    str
        A human-readable finding, or ``""``.
    """
    str_old_attr, str_new_attr = _call_attr(old_node), _call_attr(new_node)
    if str_old_attr is None or str_new_attr is None:
        return ""
    if str_new_attr in _WEAKER_ASSERT_CALLS.get(str_old_attr, frozenset()):
        return f"{str_old_attr}() weakened to {str_new_attr}()"
    if (
        str_old_attr == str_new_attr == "assertEqual"
        and bool_prod_changed
        and len(old_node.args) >= _MIN_EQ_ARGS
        and len(new_node.args) >= _MIN_EQ_ARGS
    ):
        str_oa0, str_na0 = _dump(old_node.args[0]), _dump(new_node.args[0])
        str_oa1, str_na1 = _dump(old_node.args[1]), _dump(new_node.args[1])
        bool_a1_is_the_edit = (
            str_oa0 == str_na0
            and str_oa1 != str_na1
            and _is_literal_ish(old_node.args[1])
            and _is_literal_ish(new_node.args[1])
        )
        bool_a0_is_the_edit = (
            str_oa1 == str_na1
            and str_oa0 != str_na0
            and _is_literal_ish(old_node.args[0])
            and _is_literal_ish(new_node.args[0])
        )
        if bool_a1_is_the_edit or bool_a0_is_the_edit:
            return "expected value changed while production code changed in the same diff"
    return ""


def _compare_raises(old_node: ast.With, *, new_node: ast.With) -> str:
    """Return a weakening message for a ``pytest.raises`` pair, or ``""``.

    Parameters
    ----------
    old_node : ast.With
        The ``raises`` block at the merge-base.
    new_node : ast.With
        The ``raises`` block in this change.

    Returns
    -------
    str
        A human-readable finding, or ``""``.
    """
    str_old_exc = _raises_exception_name(old_node)
    str_new_exc = _raises_exception_name(new_node)
    set_broad = {None, "Exception", "BaseException"}
    if str_old_exc and str_old_exc not in set_broad and str_new_exc in set_broad:
        str_shown_new = str_new_exc or "no exception type"
        return f"pytest.raises broadened from {str_old_exc} to {str_shown_new}"
    return ""


def _compare_pair(tuple_old: tuple, *, tuple_new: tuple, bool_prod_changed: bool) -> str:
    """Dispatch a same-position check pair to its comparator by kind.

    Parameters
    ----------
    tuple_old : tuple
        ``(kind, node)`` at the merge-base.
    tuple_new : tuple
        ``(kind, node)`` in this change.
    bool_prod_changed : bool
        Whether a non-test file also changed in this diff.

    Returns
    -------
    str
        A human-readable finding, or ``""`` when the pair carries no decidable weakening
        (including every kind-mismatch other than a ``raises`` block replaced outright).
    """
    old_kind, old_node = tuple_old
    new_kind, new_node = tuple_new
    if old_kind == "raises" and new_kind != "raises":
        return "pytest.raises removed or replaced by a plain assertion"
    if old_kind == "raises" and new_kind == "raises":
        return _compare_raises(old_node, new_node=new_node)
    if old_kind == "assert" and new_kind == "assert":
        return _compare_assert(old_node, new_node=new_node, bool_prod_changed=bool_prod_changed)
    if old_kind == "call" and new_kind == "call":
        return _compare_call(old_node, new_node=new_node, bool_prod_changed=bool_prod_changed)
    if old_kind == "call" and new_kind == "assert":
        return _compare_call_to_assert(old_node, new_node=new_node)
    return ""


_CALL_AS_OPERATOR = {
    "assertEqual": "Eq",
    "assertListEqual": "Eq",
    "assertDictEqual": "Eq",
    "assertIn": "In",
    "assertIs": "Is",
    "assertIsNot": "IsNot",
    "assertNotEqual": "NotEq",
}


def _compare_call_to_assert(old_node: ast.Call, *, new_node: ast.Assert) -> str:
    """Return a weakening message when a unittest call became a weaker bare ``assert``.

    Rewriting ``self.assertEqual(a, b)`` as ``assert a in b`` changes the assertion's kind, so
    a same-kind comparison never sees it and the check count stays identical. Normalising the
    call to the operator it is equivalent to makes the pair comparable.

    Parameters
    ----------
    old_node : ast.Call
        The ``self.assertX(...)`` call at the merge-base.
    new_node : ast.Assert
        The bare ``assert`` statement on the branch. Its ``.test`` carries the comparison --
        the checks list stores the statement, not the expression.

    Returns
    -------
    str
        A human-readable finding, or ``""`` when the rewrite is not a decidable weakening
        (an unlisted call, or a new form that is not a simple comparison).
    """
    if not isinstance(old_node.func, ast.Attribute):
        return ""
    str_old_op = _CALL_AS_OPERATOR.get(old_node.func.attr, "")
    if not str_old_op:
        return ""
    expr_new = new_node.test if isinstance(new_node, ast.Assert) else new_node
    if _is_trivial_assert_test(expr_new):
        return f"{old_node.func.attr} trivialised to a bare truthy constant"
    if not isinstance(expr_new, ast.Compare) or len(expr_new.ops) != 1:
        return ""
    str_new_op = type(expr_new.ops[0]).__name__
    if str_old_op == "Eq" and str_new_op in _WEAK_FROM_EQ:
        str_symbol = _OP_SYMBOLS.get(str_new_op, str_new_op)
        return f"{old_node.func.attr} weakened to a bare assert with {str_symbol}"
    return ""


def parse_functions(str_source: str) -> dict | None:
    """Return every ``test_*`` function/method defined in a source file, by name.

    Parameters
    ----------
    str_source : str
        Full file content.

    Returns
    -------
    dict or None
        ``{name: ast.FunctionDef}``, or ``None`` when the source does not parse — a
        distinct state from "parses clean with zero tests" (three states: flagged /
        clean / could not parse).
    """
    try:
        cls_tree = ast.parse(str_source)
    except SyntaxError:
        return None
    dict_funcs = {}
    _index_tests(cls_tree, str_prefix="", dict_funcs=dict_funcs)
    return dict_funcs


def _index_tests(node_parent: ast.AST, *, str_prefix: str, dict_funcs: dict) -> None:
    """Index every ``test_*`` function under ``node_parent`` by its qualified name.

    Qualified, not bare: two classes in one module routinely define the same method name, and
    a bare key silently overwrites the first -- so weakening the overwritten one produced no
    finding. See the backlog note.

    Parameters
    ----------
    node_parent : ast.AST
        Module or class body to walk. Only direct children are visited; nested classes
        recurse with an extended prefix.
    str_prefix : str
        Dotted prefix accumulated from enclosing classes, ``""`` at module level.
    dict_funcs : dict
        Accumulator, mutated in place: qualified name to AST node.
    """
    for node in ast.iter_child_nodes(node_parent):
        if isinstance(node, ast.ClassDef):
            _index_tests(node, str_prefix=f"{str_prefix}{node.name}.", dict_funcs=dict_funcs)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test_"
        ):
            dict_funcs[f"{str_prefix}{node.name}"] = node


def _marker_table(str_source: str) -> tuple[dict[str, str], dict[str, set]]:
    """Return what one file says about markers outside any test body.

    Parameters
    ----------
    str_source : str
        Full file content.

    Returns
    -------
    tuple of (dict, dict)
        The pytest name table, and the labels each test inherits from a module ``pytestmark``
        and from class decorators or a class ``pytestmark``, by qualified test name.
    """
    dict_inherited: dict[str, set] = {}
    try:
        cls_tree = ast.parse(str_source)
    except SyntaxError:
        return dict(_DEFAULT_NAMES), dict_inherited
    _index_inherited(
        cls_tree,
        str_prefix="",
        set_inherited=_pytestmark_labels(cls_tree.body),
        dict_out=dict_inherited,
    )
    return _pytest_names(cls_tree), dict_inherited


def _flat_stmts(list_body: list, *, str_guard: str = "") -> list:
    """Return a body's statements, each with the guard of the block it sits under.

    Parameters
    ----------
    list_body : list of ast.stmt
        A module or class body.
    str_guard : str, optional
        The guard text of the enclosing block, ``""`` at the top level.

    Returns
    -------
    list of tuple
        ``(statement, guard)`` for every statement that runs at import time.
    """
    list_out: list = []
    for cls_stmt in list_body:
        list_out.append((cls_stmt, str_guard))
        for list_arm, str_arm in _stmt_arms(cls_stmt):
            str_next = _compose(str_guard, str_inner=str_arm)
            list_out.extend(_flat_stmts(list_arm, str_guard=str_next))
    return list_out


def _stmt_arms(cls_stmt: ast.stmt) -> list:
    """Return the nested bodies of a compound statement, each with the guard it runs under.

    Parameters
    ----------
    cls_stmt : ast.stmt
        A module or class level statement.

    Returns
    -------
    list of tuple
        ``(body, guard)`` for an ``if``, ``try``/``try*``, ``for``/``while``, ``with`` or
        ``match`` (a ``with`` adds no guard); empty for any other statement.
    """
    if isinstance(cls_stmt, ast.If):
        str_else = _canon(ast.UnaryOp(op=ast.Not(), operand=cls_stmt.test))
        return [(cls_stmt.body, _canon(cls_stmt.test)), (cls_stmt.orelse, str_else)]
    if isinstance(cls_stmt, ast.Try | ast.TryStar):
        str_digest = hashlib.sha256(ast.unparse(cls_stmt).encode()).hexdigest()[:8]
        list_arms = [([*cls_stmt.body, *cls_stmt.orelse], f"try #{str_digest}")]
        list_arms += [
            (
                cls_handler.body,
                _except_guard(cls_stmt, cls_handler=cls_handler, str_after=str_digest),
            )
            for cls_handler in cls_stmt.handlers
        ]
        return [*list_arms, (cls_stmt.finalbody, "")]
    if isinstance(cls_stmt, ast.For | ast.AsyncFor | ast.While):
        return [([*cls_stmt.body, *cls_stmt.orelse], _guard_kind(cls_stmt) or "")]
    if isinstance(cls_stmt, ast.With | ast.AsyncWith):
        return [(cls_stmt.body, "")]
    if isinstance(cls_stmt, ast.Match):
        return [
            (cls_case.body, _case_guard(cls_stmt, cls_case=cls_case))
            for cls_case in cls_stmt.cases
        ]
    return []


def _compose(str_outer: str, *, str_inner: str) -> str:
    """Return the guard of a block nested in another: both must hold.

    Parameters
    ----------
    str_outer : str
        The enclosing guard, ``""`` at the top level.
    str_inner : str
        The nested block's own guard.

    Returns
    -------
    str
        ``str_inner`` alone at the top level, else the two joined by ``and``.
    """
    if not str_outer or not str_inner:
        return str_outer or str_inner
    return _join_conditions([str_outer, str_inner], cls_op=ast.And())


_RE_XFAIL_COND = re.compile(r"^xfail:(.*?)((?:;(?:raises|run)=|;lax).*)?$")


def _guarded_label(str_label: str, *, str_guard: str) -> str:
    """Return a marker label with the guard of the block that assigns it folded in.

    Parameters
    ----------
    str_label : str
        A label from ``_marker_labels``.
    str_guard : str
        The ``if``/``try`` guard around the assignment, ``""`` for none.

    Returns
    -------
    str
        An outright ``skip`` becomes ``skip(if):<guard>``; ``skipif`` and ``xfail`` conditions
        are joined to the guard by ``and``.
    """
    if not str_guard:
        return str_label
    if str_label == "skip":
        return f"skip(if):{str_guard}"
    if str_label.startswith("skipif:"):
        str_cond = str_label.removeprefix("skipif:")
        return "skipif:" + _compose(str_guard, str_inner=str_cond)
    cls_match = _RE_XFAIL_COND.match(str_label)
    if cls_match:
        str_cond, str_rest = cls_match.group(1), cls_match.group(2) or ""
        str_joined = _compose(str_guard, str_inner=str_cond) if str_cond else str_guard
        return f"xfail:{str_joined}{str_rest}"
    return str_label


def _pytestmark_labels(list_body: list) -> set:
    """Return the labels of the markers a body assigns to ``pytestmark``.

    Parameters
    ----------
    list_body : list of ast.stmt
        A module or class body.

    Returns
    -------
    set of str
        One label per ``skip``/``skipif``/``xfail`` marker, whether assigned singly or as a list.
    """
    set_out: set = set()
    for cls_stmt, str_guard in _flat_stmts(list_body):
        list_targets = (
            cls_stmt.targets
            if isinstance(cls_stmt, ast.Assign)
            else [cls_stmt.target]
            if isinstance(cls_stmt, ast.AnnAssign | ast.AugAssign)
            else []
        )
        is_mark = cls_stmt.value is not None if list_targets else False
        if is_mark and any(
            isinstance(cls_t, ast.Name) and cls_t.id == "pytestmark" for cls_t in list_targets
        ):
            cls_value = cls_stmt.value
            is_many = isinstance(cls_value, ast.List | ast.Tuple)
            for cls_expr in cls_value.elts if is_many else [cls_value]:
                for str_label in _marker_labels([cls_expr]):
                    set_out.add(_guarded_label(str_label, str_guard=str_guard))
    return set_out


def _index_inherited(
    node_parent: ast.AST, *, str_prefix: str, set_inherited: set, dict_out: dict[str, set]
) -> None:
    """Record, for every test under ``node_parent``, the marker labels it inherits.

    Parameters
    ----------
    node_parent : ast.AST
        Module or class to walk.
    str_prefix : str
        Dotted prefix of the enclosing classes.
    set_inherited : set of str
        Labels already inherited from outside ``node_parent``.
    dict_out : dict
        Accumulator, changed in place: qualified test name to labels.
    """
    for node in ast.iter_child_nodes(node_parent):
        if isinstance(node, ast.ClassDef):
            set_class = (
                set_inherited | _marker_labels(node.decorator_list) | _pytestmark_labels(node.body)
            )
            _index_inherited(
                node,
                str_prefix=f"{str_prefix}{node.name}.",
                set_inherited=set_class,
                dict_out=dict_out,
            )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test_"
        ):
            dict_out[f"{str_prefix}{node.name}"] = set_inherited


def _labels_of(
    node_fn: ast.FunctionDef, *, tuple_table: tuple[dict[str, str], dict[str, set]], str_name: str
) -> set:
    """Return a test's own skip/xfail labels plus those it inherits.

    Parameters
    ----------
    node_fn : ast.FunctionDef
        The test.
    tuple_table : tuple of (dict, dict)
        From ``_marker_table``.
    str_name : str
        The test's qualified name.

    Returns
    -------
    set of str
        Decorator, body, class and module labels together.
    """
    dict_names, dict_inherited = tuple_table
    return _skip_or_xfail_markers(node_fn, dict_names=dict_names) | dict_inherited.get(
        str_name, set()
    )


def _function_findings(
    str_path: str,
    *,
    str_name: str,
    node_old: ast.FunctionDef,
    node_new: ast.FunctionDef,
    bool_prod_changed: bool,
    set_old_marks: set,
    set_new_marks: set,
) -> list:
    """Return every weakening finding for one test function present in both versions.

    Parameters
    ----------
    str_path : str
        Repository-relative path, for message prefixing.
    str_name : str
        The test function's name.
    node_old : ast.FunctionDef
        The function at the merge-base.
    node_new : ast.FunctionDef
        The function in this change.
    bool_prod_changed : bool
        Whether a non-test file also changed in this diff.
    set_old_marks : set
        Skip/xfail labels of the old test, inherited class and module markers included.
    set_new_marks : set
        The same for the new test.

    Returns
    -------
    list of str
        Findings, in the order the underlying checks appear.
    """
    list_problems = []
    set_new_markers = _newly_marked(set_old=set_old_marks, set_new=set_new_marks)
    if set_new_markers:
        str_markers = "/".join(sorted(set_new_markers))
        list_problems.append(f"{str_path}: {str_name}() newly marked {str_markers}")

    list_old_checks = _function_checks(node_old)
    list_new_checks = _function_checks(node_new)
    if len(list_new_checks) < len(list_old_checks):
        list_problems.append(
            f"{str_path}: {str_name}() lost {len(list_old_checks) - len(list_new_checks)} "
            f"assertion(s) (had {len(list_old_checks)}, now {len(list_new_checks)})"
        )
    for tuple_old, tuple_new in zip(list_old_checks, list_new_checks, strict=False):
        str_msg = _compare_pair(
            tuple_old, tuple_new=tuple_new, bool_prod_changed=bool_prod_changed
        )
        if str_msg:
            list_problems.append(f"{str_path}: {str_name}() line {tuple_new[1].lineno}: {str_msg}")
    return list_problems


def _file_findings(
    str_path: str, *, str_old_text: str, str_new_text: str, bool_prod_changed: bool
) -> list:
    """Return every weakening finding for one changed test file.

    Parameters
    ----------
    str_path : str
        Repository-relative path.
    str_old_text : str
        Content at the merge-base.
    str_new_text : str
        Content in this change.
    bool_prod_changed : bool
        Whether a non-test file also changed in this diff.

    Returns
    -------
    list of str
        One ``could not parse`` finding when either version fails to parse (a file not
        checked is a finding in its own right, never read as clean); otherwise the
        combined per-function findings.
    """
    dict_old_funcs = parse_functions(str_old_text)
    dict_new_funcs = parse_functions(str_new_text)
    if dict_old_funcs is None or dict_new_funcs is None:
        return [f"{str_path}: could not parse — not checked"]
    list_problems = []
    list_free = [str_n for str_n in dict_new_funcs if str_n not in dict_old_funcs]
    dict_renames = rename_pairs(
        {str_n: cls_f for str_n, cls_f in dict_old_funcs.items() if str_n not in dict_new_funcs},
        dict_added={str_n: dict_new_funcs[str_n] for str_n in list_free},
    )
    list_free = [str_n for str_n in list_free if str_n not in dict_renames.values()]
    tuple_old_table = _marker_table(str_old_text)
    tuple_new_table = _marker_table(str_new_text)
    for str_name, node_old in dict_old_funcs.items():
        str_now = dict_renames.get(str_name, str_name)
        node_new = dict_new_funcs.get(str_now)
        if node_new is None:
            list_problems.append(
                deleted_message(str_path, str_name=str_name, list_unpaired_added=list_free)
            )
            continue
        list_problems.extend(
            _function_findings(
                str_path,
                str_name=str_now,
                node_old=node_old,
                node_new=node_new,
                bool_prod_changed=bool_prod_changed,
                set_old_marks=_labels_of(node_old, tuple_table=tuple_old_table, str_name=str_name),
                set_new_marks=_labels_of(node_new, tuple_table=tuple_new_table, str_name=str_now),
            )
        )
    return list_problems


def _touches_production_code(list_changed: list) -> bool:
    """Return whether the diff touches anything besides tests and docs.

    Parameters
    ----------
    list_changed : list of tuple
        ``(status_letter, source_path, destination_path)`` rows from ``changed_paths``.

    Returns
    -------
    bool
        ``True`` when at least one changed path is neither a test file nor
        documentation — the signal that gates the expected-value-changed rule.
    """
    for str_status, str_src, str_path in list_changed:
        tuple_paths = (str_src, str_path) if str_status == "R" else (str_path,)
        if any(
            not (RE_TEST_TREE.search(str_p) or RE_DOC_PATH.search(str_p)) for str_p in tuple_paths
        ):
            return True
    return False


def _test_file_removed(str_status: str, *, str_src: str, str_path: str) -> bool:
    """Return whether a row takes a test file out of the suite (deleted, or moved off tests/).

    Parameters
    ----------
    str_status : str
        The row's status letter.
    str_src : str
        The row's source path.
    str_path : str
        The row's destination path.

    Returns
    -------
    bool
        ``True`` for ``D`` on a test path, or ``R`` from a test path to a non-test path.
    """
    if str_status == "D":
        return bool(RE_TEST_PATH.search(str_path))
    moved_off = RE_TEST_PATH.search(str_src) and not RE_TEST_PATH.search(str_path)
    return str_status == "R" and bool(moved_off)


def _removed_findings(str_base: str, *, str_path: str) -> list:
    """Return the findings for a test file that left the suite.

    Parameters
    ----------
    str_base : str
        The merge-base commit.
    str_path : str
        The test file's path at the base.

    Returns
    -------
    list of str
        One finding when the base file held tests (or cannot be parsed), else empty.
    """
    str_old = show(str_base, str_path=str_path)
    dict_old_funcs = parse_functions(str_old) if str_old is not None else {}
    if str_old is not None and dict_old_funcs is None:
        return [f"{str_path}: could not parse the removed test file — not checked"]
    if dict_old_funcs:
        int_n = len(dict_old_funcs)
        return [f"{str_path}: entire test file deleted or moved out of tests/ ({int_n} test(s))"]
    return []


def collect_problems(list_changed: list, *, str_base: str) -> list:
    """Return every weakening finding across the branch's changed test files.

    Parameters
    ----------
    list_changed : list of tuple
        ``(status_letter, source_path, destination_path)`` rows from ``changed_paths``.
    str_base : str
        The merge-base commit.

    Returns
    -------
    list of str
        Combined findings from deleted test files and modified ones.
    """
    list_problems = []
    bool_prod_changed = _touches_production_code(list_changed)
    for str_status, str_src, str_path in list_changed:
        if _test_file_removed(str_status, str_src=str_src, str_path=str_path):
            list_problems.extend(_removed_findings(str_base, str_path=str_src))
            continue
        if not RE_TEST_PATH.search(str_path):
            continue
        str_new = show(STR_INDEX_REF, str_path=str_path)
        str_old = show(str_base, str_path=str_src) if RE_TEST_PATH.search(str_src) else None
        if str_new is None or str_old is None:
            continue
        list_problems.extend(
            _file_findings(
                str_path,
                str_old_text=str_old,
                str_new_text=str_new,
                bool_prod_changed=bool_prod_changed,
            )
        )
    return list_problems


def unjustified_advice() -> str:
    """Return the fix to print for an unjustified finding, specific to where it runs.

    Returns
    -------
    str
        Under CI, only the PR-body / trailer line (``TEST_CHANGE_OK`` is ignored there).
        Locally, the per-command env var, the warning against exporting it, and the fact
        that CI still needs a line a reviewer can read.
    """
    str_line = "add a 'test-change-ok: <reason>' line to the PR body or a commit trailer."
    if is_ci():
        str_ci = f"To justify it, {str_line} TEST_CHANGE_OK is ignored under CI."
        return str_ci + no_terminal_note()
    return (
        "Locally, prefix this one commit: `TEST_CHANGE_OK='<reason>' git commit -m ...` "
        "(never export it: one stale reason would cover every later finding). "
        f"CI ignores the variable, so also {str_line} A bare marker with no reason fails. "
        "One commit does both: `TEST_CHANGE_OK='<reason>' git commit -m ... "
        "-m 'test-change-ok: <reason>'` (pre-commit reads the variable, CI the trailer)."
    )


def report(list_problems: list, *, str_base: str, int_changed_count: int) -> int:
    """Print findings and the verdict, resolving the justification escape hatch.

    Parameters
    ----------
    list_problems : list of str
        Findings from ``collect_problems``.
    str_base : str
        The merge-base commit — passed through to ``justification_reason``.
    int_changed_count : int
        Total changed-path count, shown on a clean pass.

    Returns
    -------
    int
        0 when clean or justified, 1 on an unjustified weakening.
    """
    if not list_problems:
        print(f"✅ assertion-weakening check OK ({int_changed_count} changed file(s) checked)")
        return 0

    for str_problem in list_problems:
        print(f"⚠️  {str_problem}")

    str_reason = justification_reason(str_base)
    if str_reason:
        print(f"\n✅ justified: test-change-ok: {str_reason}")
        return 0

    print(
        f"\n❌ {len(list_problems)} assertion-weakening change(s) with no justification. "
        f"{unjustified_advice()}"
    )
    return 1


def main(list_argv: list) -> int:
    """Check the branch's cumulative diff for an unjustified assertion weakening.

    Parameters
    ----------
    list_argv : list of str
        ``["--root", <dir>]`` or empty.

    Returns
    -------
    int
        0 when clean or justified, 1 on an unjustified weakening.
    """
    if not apply_root_flag(list_argv):
        return 1

    str_base = resolve_base()
    if str_base is None:
        return 0
    if not str_base:
        return 1

    list_changed = changed_paths(str_base)
    list_problems = collect_problems(list_changed, str_base=str_base)
    return report(list_problems, str_base=str_base, int_changed_count=len(list_changed))


if __name__ == "__main__":
    for cls_stream in (sys.stdout, sys.stderr):
        if hasattr(cls_stream, "reconfigure"):
            cls_stream.reconfigure(encoding="utf-8", errors="replace")

    sys.exit(main(sys.argv[1:]))
