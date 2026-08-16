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
	for cls_node in cls_tree.body:
		if isinstance(cls_node, ast.Assign) and any(
			isinstance(cls_target, ast.Name) and cls_target.id == "LOGGER"
			for cls_target in cls_node.targets
		):
			return cls_node.lineno
	raise AssertionError("startup.py no longer assigns a module-level LOGGER")


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

	set_guarded: set[int] = set()
	for cls_node in ast.walk(cls_tree):
		if isinstance(cls_node, ast.Try):
			for cls_inner in ast.walk(cls_node):
				set_guarded.add(id(cls_inner))

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
	for cls_try in list_config_tries:
		for cls_handler in cls_try.handlers:
			assert isinstance(cls_handler.type, ast.Name)
			assert cls_handler.type.id == "Exception"
