"""Measure assertion sites per ``test_*`` function, and block only the zero case (blueprintx#431).

BLUEPRINTX#431 asked for a gate that caps every test at ONE assertion, plus the refactor of the
188 tests (33%) that had more than one, measured 2026-09-06 by counting every assertion SITE —
``assert``, an ``assert_*()`` call (pandas/mock), and ``pytest.raises``/``pytest.warns`` used as
a context manager, not bare ``ast.Assert`` alone (a bare count misreads all 42 ``raises``-only
tests as "zero assertions").

THAT CAP IS NOT BUILT HERE, ON PURPOSE. ``tests/CLAUDE.md`` already settled this question, via
blueprintx#429, re-measuring the same tree at **554 tests, 205 (27%) with more than one
assertion** and finding the rule people actually follow is ONE BEHAVIOUR, not one assert: several
assertions pinning the *same* fact (a value and its dtype; a rendered message and the absence of
a secret in it) are one behaviour and belong in one test — splitting them duplicates the whole
*arrange* to prove nothing new. That doc names blueprintx#429/#431 by number and says explicitly:
"a ceiling on assert count would fail the legitimate multi-facet case above." The one narrow,
decidable slice of "one assert hides two facts" — ``assert a and b`` — is already ruff's ``PT018``
(0 violations in this tree); that is the linter's job, this gate's job is not to re-implement it.

So a hand-rolled cap wired into pre-commit/CI would be re-litigating a settled, measured
disagreement with the repo's own documented convention, on a false-positive rate this file's own
distribution table below can reproduce. What IS still undecided and still worth a gate: a
``test_*`` function with **zero** assertion sites asserts nothing, under any reading of "one
behaviour" — there is no legitimate multi-facet exception for zero facets, and nothing else in
this repo's gate family (``check_complexity.sh``'s tests/ ceiling of 1, ``PT018``) checks for it.
That is the one finding this gate reports BY DEFAULT.

The full per-test cap the issue asked for still ships, as an OPT-IN ``--max-per-test N`` flag —
useful for a project that wants the stricter rule with eyes open, or for re-running this file's
own measurement against a changed tree — but it is never invoked by any wired pre-commit hook or
CI job in this PR; see the PR body for the population re-measurement and the wiring decision.

Escape hatch, matching ``# complexity-ok: <reason>`` elsewhere in this repo: a
``# one-assert-ok: <reason>`` comment anywhere in a flagged function's source exempts it from
BOTH checks (zero-assertion and, when passed, the ``--max-per-test`` cap) — the reason is
required, a bare marker is rejected.

SELF-SKIPS when ``tests/`` is absent (this repo's own root, per ``CLAUDE.md``: "BlueprintX's own
tree has no ``src/`` or ``tests/``"). A ``tests/`` directory that exists but yields zero
``test_*.py`` files is NOT a skip — it is the broken-discovery failure this repo's gates exist to
catch (blueprintx#111's shape, recurring: `check_provenance.py`, `check_docstrings.py`).
"""

import ast
import pathlib
import re
import sys


RE_HATCH = re.compile(r"#\s*one-assert-ok:\s*(\S.*)$", re.M)

# Call names this gate treats as a `with`-block assertion — pytest.raises/warns is the
# context-manager form of a check, not the absence of one (blueprintx#431's own measurement
# note: bare ast.Assert alone misreads these as zero).
_SET_CTX_ASSERTIONS = frozenset({"raises", "warns"})


def parse_args(list_argv: list) -> tuple:
	"""Parse ``--root <dir>`` and the optional ``--max-per-test <int>`` flag.

	Parameters
	----------
	list_argv : list of str
		The raw argv tail.

	Returns
	-------
	tuple
		``(path_root, int_max, bool_ok)`` — ``int_max`` is ``None`` when the flag was not
		given (measurement-only mode); ``bool_ok`` is ``False`` on bad usage (already
		reported to stdout).
	"""
	path_root = pathlib.Path.cwd()
	int_max = None
	list_rest = list(list_argv)
	while list_rest:
		str_arg = list_rest.pop(0)
		if str_arg == "--root":
			if not list_rest:
				print("❌ --root needs a directory")
				return path_root, int_max, False
			path_root = pathlib.Path(list_rest.pop(0)).resolve()
		elif str_arg == "--max-per-test":
			if not list_rest or not list_rest[0].isdigit():
				print("❌ --max-per-test needs a positive integer")
				return path_root, int_max, False
			int_max = int(list_rest.pop(0))
		else:
			print(f"❌ unrecognised argument: {str_arg}")
			return path_root, int_max, False
	return path_root, int_max, True


def _test_files(path_root: pathlib.Path) -> list:
	"""Return every ``test_*.py`` file under ``<root>/tests/``.

	Parameters
	----------
	path_root : pathlib.Path
		The tree to scan.

	Returns
	-------
	list of pathlib.Path
		Sorted matches, empty when ``tests/`` holds none.
	"""
	path_tests = path_root / "tests"
	if not path_tests.is_dir():
		return []
	return sorted(path_tests.rglob("test_*.py"))


def _has_non_python_tests(path_tests: pathlib.Path) -> bool:
	"""Return whether ``tests/`` holds a ``test_*`` file in a non-Python language.

	Distinguishes "this tree tests in another language here" — BlueprintX's own root ships
	``tests/test_check_issue_scope.sh`` and two siblings, zero ``.py`` — from a genuinely
	empty or broken ``tests/``. Only the latter is a failure; the former is the same
	legitimate skip ``check_complexity.sh`` already grants this exact repo (its own
	``CLAUDE.md``: "BlueprintX's own tree has no src/ or tests/ [in the Python sense]").

	Parameters
	----------
	path_tests : pathlib.Path
		The ``tests/`` directory (already known to exist).

	Returns
	-------
	bool
		``True`` when at least one ``test_*.<ext>`` file exists with ``ext`` other than
		``py``.
	"""
	return any(path_file.suffix != ".py" for path_file in path_tests.rglob("test_*.*"))


def vacuous_discovery_reason(path_root: pathlib.Path) -> str | None:
	"""Return why a missing ``tests/`` directory is a legitimate skip, or ``None`` otherwise.

	Parameters
	----------
	path_root : pathlib.Path
		The tree to scan.

	Returns
	-------
	str or None
		A skip reason when ``tests/`` does not exist at all; ``None`` when it does (whether
		or not it holds any matching files — an existing-but-empty ``tests/`` is a broken
		discovery, handled by the caller as a failure, never a skip).
	"""
	if not (path_root / "tests").is_dir():
		return "no tests/ directory in this tree — skipping"
	return None


def _is_assert_call(node_call: ast.Call) -> bool:
	"""Return whether a call is an ``assert*`` check (unittest, pandas, mock, ...).

	Parameters
	----------
	node_call : ast.Call
		The call node.

	Returns
	-------
	bool
		``True`` for ``self.assertX(...)``, ``mock.assert_called_once()``,
		``pd.testing.assert_frame_equal(...)``, or a bare ``assert_x(...)`` free function.
	"""
	func = node_call.func
	if isinstance(func, ast.Attribute):
		return func.attr.startswith("assert")
	if isinstance(func, ast.Name):
		return func.id.startswith("assert_")
	return False


def _ctx_call_name(node_call: ast.Call) -> str | None:
	"""Return a ``with``-item's context-expression callable name.

	Parameters
	----------
	node_call : ast.Call
		A ``with`` item's context expression.

	Returns
	-------
	str or None
		The callable's bare or attribute name, or ``None`` when neither shape matches.
	"""
	func = node_call.func
	if isinstance(func, ast.Attribute):
		return func.attr
	if isinstance(func, ast.Name):
		return func.id
	return None


def _is_assertion_with(node_with: ast.With) -> bool:
	"""Return whether a ``with`` block is a ``pytest.raises``/``pytest.warns`` context.

	Parameters
	----------
	node_with : ast.With
		The ``with`` statement.

	Returns
	-------
	bool
		``True`` when any item's context expression calls ``raises`` or ``warns``.
	"""
	for item in node_with.items:
		expr = item.context_expr
		if isinstance(expr, ast.Call) and _ctx_call_name(expr) in _SET_CTX_ASSERTIONS:
			return True
	return False


def _assertion_sites(node_fn: ast.FunctionDef) -> list:
	"""Return the assertion-like nodes inside a test function, in source order.

	Parameters
	----------
	node_fn : ast.FunctionDef
		The test function (or method).

	Returns
	-------
	list of ast.AST
		One entry per ``assert`` statement, ``assert*()`` call, or ``raises``/``warns``
		``with`` block. Does not descend into a nested function/lambda — that is its own
		unit (mirrors ``check_assertion_weakening.py``'s identical walk).
	"""
	list_sites: list = []

	def _walk(node: ast.AST) -> None:
		for child in ast.iter_child_nodes(node):
			if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
				continue
			if isinstance(child, ast.Assert) or (
				isinstance(child, ast.With) and _is_assertion_with(child)
			):
				list_sites.append(child)
			elif (
				isinstance(child, ast.Expr)
				and isinstance(child.value, ast.Call)
				and _is_assert_call(child.value)
			):
				list_sites.append(child.value)
			_walk(child)

	_walk(node_fn)
	return list_sites


def _index_test_functions(cls_tree: ast.AST) -> dict:
	"""Return every ``test_*`` function/method under a module, keyed by qualified name.

	Parameters
	----------
	cls_tree : ast.AST
		The parsed module.

	Returns
	-------
	dict of str to ast.FunctionDef
		Qualified name (``ClassName.test_x`` or bare ``test_x``) to its node — qualified so
		two classes sharing a method name are tracked separately.
	"""
	dict_funcs: dict = {}

	def _walk(node_parent: ast.AST, str_prefix: str) -> None:
		for node in ast.iter_child_nodes(node_parent):
			if isinstance(node, ast.ClassDef):
				_walk(node, f"{str_prefix}{node.name}.")
			elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
				"test_"
			):
				dict_funcs[f"{str_prefix}{node.name}"] = node

	_walk(cls_tree, "")
	return dict_funcs


def _hatch_reason(str_source: str, node_fn: ast.FunctionDef) -> str:
	"""Return the ``# one-assert-ok: <reason>`` text inside a function, or ``""``.

	Parameters
	----------
	str_source : str
		The file's full source text.
	node_fn : ast.FunctionDef
		The function to scan.

	Returns
	-------
	str
		The non-empty reason, or ``""`` when no valid hatch is present — a bare marker with
		no reason does not exempt, matching ``# complexity-ok:``'s convention.
	"""
	# `ast.get_source_segment` stops at the function's last STATEMENT column, not the end of
	# that physical line — a trailing `# one-assert-ok: ...` on the same line as the last
	# statement sits past that boundary and would silently never match. Slice whole physical
	# lines instead, so a hatch anywhere in the function's line range is found regardless of
	# which column it starts on (mirrors check_complexity.sh's signature-hatch scan).
	list_lines = str_source.splitlines()
	int_end = node_fn.end_lineno or node_fn.lineno
	str_segment = "\n".join(list_lines[node_fn.lineno - 1 : int_end])
	cls_match = RE_HATCH.search(str_segment)
	return cls_match.group(1).strip() if cls_match and cls_match.group(1).strip() else ""


def _file_findings(path_file: pathlib.Path, path_root: pathlib.Path, int_max: int | None) -> tuple:
	"""Return the problems and per-function assertion-site counts for one test file.

	Parameters
	----------
	path_file : pathlib.Path
		The test file to check.
	path_root : pathlib.Path
		The tree root, for relative message paths.
	int_max : int or None
		The ``--max-per-test`` cap, or ``None`` when only the zero-assertion check applies.

	Returns
	-------
	tuple
		``(problems, counts)`` — ``problems`` is a list of str findings; ``counts`` is a
		list of int, one per ``test_*`` function found, for the distribution table.
	"""
	str_source = path_file.read_text(encoding="utf-8")
	str_rel = path_file.relative_to(path_root)
	try:
		cls_tree = ast.parse(str_source)
	except SyntaxError as cls_exc:
		return [f"{str_rel}: not valid Python ({cls_exc}) — not checked"], []

	dict_funcs = _index_test_functions(cls_tree)
	list_problems: list = []
	list_counts: list = []
	for str_name, node_fn in dict_funcs.items():
		int_count = len(_assertion_sites(node_fn))
		list_counts.append(int_count)
		if _hatch_reason(str_source, node_fn):
			continue
		if int_count == 0:
			list_problems.append(
				f"{str_rel}: {str_name}() line {node_fn.lineno}: asserts nothing — 0 assertion "
				f"sites (no assert, assert_*() call, or raises/warns block)"
			)
		elif int_max is not None and int_count > int_max:
			list_problems.append(
				f"{str_rel}: {str_name}() line {node_fn.lineno}: {int_count} assertion sites, "
				f"over the --max-per-test cap of {int_max}"
			)
	return list_problems, list_counts


def distribution_table(list_counts: list) -> str:
	"""Return a human-readable histogram of assertion-site counts, one line per count.

	Parameters
	----------
	list_counts : list of int
		Per-function assertion-site counts across every checked file.

	Returns
	-------
	str
		One ``"N assertion site(s): M test(s)"`` line per distinct count, sorted by count;
		``"0 test_* functions found"`` when the list is empty.
	"""
	if not list_counts:
		return "0 test_* functions found"
	dict_hist: dict = {}
	for int_count in list_counts:
		dict_hist[int_count] = dict_hist.get(int_count, 0) + 1
	return "\n".join(
		f"  {int_n} assertion site(s): {int_tests} test(s)"
		for int_n, int_tests in sorted(dict_hist.items())
	)


def main(list_argv: list) -> int:
	"""Check every ``test_*`` function under ``<root>/tests/`` for assertion sites.

	Parameters
	----------
	list_argv : list of str
		``["--root", <dir>]`` and/or ``["--max-per-test", <int>]``, in either order.

	Returns
	-------
	int
		0 when ``tests/`` is absent, holds only non-Python ``test_*`` files, or every
		function has at least one assertion site and (when given) stays within the cap; 1 on
		a broken (empty) discovery, an unparsable file, a zero-assertion test, or a cap
		violation.
	"""
	path_root, int_max, bool_ok = parse_args(list_argv)
	if not bool_ok:
		return 1

	str_skip = vacuous_discovery_reason(path_root)
	if str_skip is not None:
		print(f"✅ one-assert gate: {str_skip}")
		return 0

	list_files = _test_files(path_root)
	if not list_files:
		if _has_non_python_tests(path_root / "tests"):
			print(
				"✅ one-assert gate: no test_*.py files under tests/ (non-Python test file(s) "
				"found instead — this tree does not test in Python here)"
			)
			return 0
		print(
			"❌ tests/ exists but 0 test_*.py files were found — broken discovery, not a "
			"legitimate skip",
			file=sys.stderr,
		)
		return 1

	list_problems: list = []
	list_all_counts: list = []
	for path_file in list_files:
		list_file_problems, list_counts = _file_findings(path_file, path_root, int_max)
		list_problems.extend(list_file_problems)
		list_all_counts.extend(list_counts)

	print(f"assertion-site distribution across {len(list_all_counts)} test(s):")
	print(distribution_table(list_all_counts))

	if list_problems:
		for str_problem in list_problems:
			print(f"❌ {str_problem}", file=sys.stderr)
		print(
			f"\n{len(list_problems)} problem(s). Add '# one-assert-ok: <reason>' inside the "
			f"function to exempt a legitimate case — the reason is required.",
			file=sys.stderr,
		)
		return 1

	str_cap = f", --max-per-test {int_max}" if int_max is not None else " (measurement only)"
	print(
		f"✅ one-assert gate: {len(list_files)} file(s), {len(list_all_counts)} test(s) "
		f"checked{str_cap}, 0 findings"
	)
	return 0


if __name__ == "__main__":
	# Windows' stdout defaults to cp1252, which cannot encode the glyphs this script prints —
	# see check_dtypes.py's identical fix for the always_run hook it would otherwise crash.
	for cls_stream in (sys.stdout, sys.stderr):
		if hasattr(cls_stream, "reconfigure"):
			cls_stream.reconfigure(encoding="utf-8", errors="replace")
	sys.exit(main(sys.argv[1:]))
