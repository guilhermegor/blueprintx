"""Structural guard on ``config/startup.py``'s fragility gradient.

An import-time singleton module has to build its **observability** before the first thing
that can break. When it does not, a failure has nowhere to be written: the process dies with
no log file, no traceback and no run folder, and the operator has nothing at all to read —
measured in the field as a job that printed one line from a dependency's logger and returned
to the prompt, costing a full day.

These tests read the SOURCE with :mod:`ast` rather than importing the module: importing
``startup`` builds directories and configures logging as a side effect, which a unit test
must not do.
"""

import ast
from collections.abc import Callable
from pathlib import Path


# --------------------------
# Module Utilities
# --------------------------


def _startup_tree() -> ast.Module:
	"""Parse ``src/config/startup.py`` without importing it.

	Returns
	-------
	ast.Module
		The parsed module.
	"""
	path_startup = Path(__file__).resolve().parents[2] / "src" / "config" / "startup.py"
	return ast.parse(path_startup.read_text(encoding="utf-8"))


def _load_pure_function(cls_tree: ast.Module, str_name: str) -> Callable[[dict, str], dict | None]:
	"""Extract a module-level function from the parsed ``startup`` module, without importing it.

	Only sound for a function with no reference to a startup.py global — the resolver tested
	below takes its config as an explicit argument, so lifting out its own AST node and
	exec'ing it in isolation is safe. The ``@type_checker`` decorator is stripped: the
	runtime-typing engine has its own test suite (``test_typing.py``), and proving it again
	here is not this module's job.

	Parameters
	----------
	cls_tree : ast.Module
		The parsed ``startup`` module (see ``_startup_tree``).
	str_name : str
		The function name to extract.

	Returns
	-------
	Callable[[dict, str], dict or None]
		The undecorated function, ready to call directly with a plain config mapping.
	"""
	list_matches = [
		cls_node
		for cls_node in cls_tree.body
		if isinstance(cls_node, ast.FunctionDef) and cls_node.name == str_name
	]
	assert list_matches, f"startup.py no longer defines {str_name}"
	cls_func = list_matches[0]
	cls_func.decorator_list = []
	cls_module = ast.Module(body=[cls_func], type_ignores=[])
	ast.fix_missing_locations(cls_module)
	dict_namespace: dict = {}
	exec(  # noqa: S102 — extracting one pure function's own AST node, not untrusted input
		compile(cls_module, "<startup-function>", "exec"), dict_namespace
	)
	return dict_namespace[str_name]


def _logger_lineno(cls_tree: ast.Module) -> int:
	"""Return the line on which the module-level ``LOGGER`` is assigned.

	Parameters
	----------
	cls_tree : ast.Module
		The parsed ``startup`` module.

	Returns
	-------
	int
		The 1-based line number of the ``LOGGER = …`` statement.
	"""
	# A generator plus next-with-default rather than a loop with a guard and a trailing raise.
	# Same answer, same failure, and mccabe charges a comprehension nothing while charging the
	# loop and its guard a point each. This tree is capped at complexity 1.
	list_lines = [
		cls_node.lineno
		for cls_node in cls_tree.body
		if isinstance(cls_node, ast.Assign)
		and any(
			isinstance(cls_target, ast.Name) and cls_target.id == "LOGGER"
			for cls_target in cls_node.targets
		)
	]
	assert list_lines, "startup.py no longer assigns a module-level LOGGER"
	return list_lines[0]


# --------------------------
# Tests
# --------------------------


def test_every_config_read_before_the_logger_is_guarded() -> None:
	"""No failable config resolution may run unguarded ahead of the logger.

	``resolve_config_path`` raises on a missing file and the YAML read raises on an
	unreadable one. Either one, executed above the ``LOGGER`` assignment and outside a
	``try``, reinstates the original defect exactly.
	"""
	cls_tree = _startup_tree()
	int_logger_line = _logger_lineno(cls_tree)

	# Every node sitting inside any try-block, collected in one comprehension rather than a
	# nested loop pair, which mccabe would charge 3 points against this tree's ceiling of 1.
	set_guarded = {
		id(cls_inner)
		for cls_node in ast.walk(cls_tree)
		if isinstance(cls_node, ast.Try)
		for cls_inner in ast.walk(cls_node)
	}

	list_unguarded = [
		cls_node.lineno
		for cls_node in ast.walk(cls_tree)
		if isinstance(cls_node, ast.Call)
		and isinstance(cls_node.func, ast.Name)
		and cls_node.func.id == "resolve_config_path"
		and cls_node.lineno < int_logger_line
		and id(cls_node) not in set_guarded
	]
	assert not list_unguarded, (
		f"resolve_config_path runs unguarded at line(s) {list_unguarded}, above the LOGGER at "
		f"line {int_logger_line} — a failure there has nowhere to be written"
	)


def test_a_captured_config_failure_is_reported_and_exits() -> None:
	"""Capturing the failure is only half the fix — it must still be reported and abort.

	Swallowing the error and running on fallback config is strictly worse than the original
	crash: the job would run against values nobody configured.
	"""
	cls_tree = _startup_tree()

	# Bind the assertions to the error branch itself. A substring search over everything
	# after the LOGGER assignment passes just as well when some unrelated branch logs, writes
	# to stderr and exits — it would prove the file contains those calls, not that THIS
	# failure reaches them.
	list_branches = [
		cls_node
		for cls_node in cls_tree.body
		if isinstance(cls_node, ast.If) and "_str_config_error" in ast.dump(cls_node.test)
	]
	assert list_branches, "the captured config failure is no longer acted on"

	str_branch = "\n".join(ast.dump(cls_stmt) for cls_stmt in list_branches[0].body)
	assert "critical" in str_branch, "the captured failure is never written to the log"
	assert "stderr" in str_branch, "the captured failure never reaches stderr"
	assert "SystemExit" in str_branch, "the run continues on fallback configuration"


def test_the_failable_block_catches_exception_not_baseexception() -> None:
	"""``SystemExit`` from the config helpers must pass through, not be reported as a read error.

	``env_config`` raises ``SystemExit(2)`` for an unknown ENV — a deliberate, already-explained
	failure. Catching ``BaseException`` would relabel it as a config read failure and hide the
	real cause.
	"""
	cls_tree = _startup_tree()

	# Scope to the try that actually wraps the config read — the module also carries a
	# legitimate `except ModuleNotFoundError` for the layout-agnostic typing shim.
	list_config_tries = [
		cls_node
		for cls_node in ast.walk(cls_tree)
		if isinstance(cls_node, ast.Try)
		and any(
			isinstance(cls_inner, ast.Call)
			and isinstance(cls_inner.func, ast.Name)
			and cls_inner.func.id == "resolve_config_path"
			for cls_inner in ast.walk(cls_node)
		)
	]
	assert list_config_tries, "the failable config block is no longer wrapped"
	# Flatten first, then assert once on the collected names. The loop form asserted N times
	# behind one green and stopped at the first bad handler; this reports every offender, and
	# keeps the test at the complexity 1 this tree is capped at.
	list_caught = [
		cls_handler.type.id if isinstance(cls_handler.type, ast.Name) else ast.dump(cls_handler)
		for cls_try in list_config_tries
		for cls_handler in cls_try.handlers
	]
	assert list_caught, "the failable config block catches nothing"
	assert set(list_caught) == {"Exception"}, (
		f"the config read must catch Exception, never BaseException — found {list_caught}"
	)


# --------------------------
# Tests — resolve_reference_spec (blueprintx#225)
# --------------------------
#
# The reference/golden-copy block in inputs.yaml is an OPTIONAL OVERRIDE: it must never force
# a project to declare a source's {dir, pattern} twice. These tests pin the fallback chain —
# override wins when present, the real input's own spec otherwise, None only when neither
# exists — with the absent-override path asserted explicitly: every existing generated
# project has no reference_files block, so that is the path a regression would hit first.
# Placed in this module (rather than a new file) because it exercises the same startup.py and
# a new tests/unit/*.py file needs its own scaffold copy-list wiring (bin/ci/check_test_copy_
# lists.py), which is out of scope for this change.


def test_reference_override_wins_over_real_spec() -> None:
	"""A source listed under ``reference_files`` returns that override, not its real spec."""
	fn_resolve = _load_pure_function(_startup_tree(), "resolve_reference_spec")
	dict_inputs = {
		"example_source": {"dir": "data/example_source", "pattern": "*.csv"},
		"reference_files": {"example_source": {"dir": "data/reference", "pattern": "*.csv"}},
	}
	assert fn_resolve(dict_inputs, "example_source") == {
		"dir": "data/reference",
		"pattern": "*.csv",
	}


def test_absent_override_falls_through_to_real_spec_unchanged() -> None:
	"""No ``reference_files`` entry: the source's reference IS its real-input spec, untouched.

	This is the regression-risk path: every existing generated project ships with no
	``reference_files`` block at all, so this behaviour must be identical to a project that
	never heard of the override.
	"""
	fn_resolve = _load_pure_function(_startup_tree(), "resolve_reference_spec")
	dict_inputs = {"example_source": {"dir": "data/example_source", "pattern": "*.csv"}}
	assert fn_resolve(dict_inputs, "example_source") == {
		"dir": "data/example_source",
		"pattern": "*.csv",
	}


def test_missing_reference_files_key_entirely_is_the_same_as_empty() -> None:
	"""A config with no ``reference_files`` key at all still resolves the real spec.

	Covers the literal shape of every project scaffolded before this issue: the key is not
	merely empty, it does not exist.
	"""
	fn_resolve = _load_pure_function(_startup_tree(), "resolve_reference_spec")
	dict_inputs = {
		"daily_infos_base_path": "logs",
		"daily_infos_dated": False,
		"example_source": {"dir": "data/example_source", "pattern": "*.csv"},
	}
	assert fn_resolve(dict_inputs, "example_source") == {
		"dir": "data/example_source",
		"pattern": "*.csv",
	}


def test_neither_override_nor_real_spec_returns_none() -> None:
	"""An unknown source with no override and no real input resolves to ``None``."""
	fn_resolve = _load_pure_function(_startup_tree(), "resolve_reference_spec")
	assert fn_resolve({}, "unknown_source") is None


def test_non_mapping_real_key_without_override_returns_none() -> None:
	"""A top-level scalar key (like ``daily_infos_base_path``) is never mistaken for a spec."""
	fn_resolve = _load_pure_function(_startup_tree(), "resolve_reference_spec")
	assert fn_resolve({"daily_infos_base_path": "logs"}, "daily_infos_base_path") is None
