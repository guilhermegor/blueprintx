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
# Layer name for modules sitting directly under src/ (an entrypoint such as src/main.py).
_ROOT_LAYER = "__root__"


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


def resolve_layer_policy(dict_policy: dict, str_layer: str) -> tuple[dict, dict]:
	"""Return the allow-list and annotation-only map that govern one layer.

	The annotation-only map is layered: a file-wide default, overridden per layer. A layer
	may narrow a vendor to annotations even where a sibling layer legitimately calls it.
	Measured: the ORM tier's controller names ``Engine`` only in signatures, while its model
	genuinely CONSTRUCTS with ``DeclarativeBase``/``mapped_column`` — one global verdict
	cannot serve both, and the loose one would be the one that survives.

	Parameters
	----------
	dict_policy : dict
		The parsed ``.layer-policy.yaml``.
	str_layer : str
		The layer being checked.

	Returns
	-------
	tuple of dict
		``(dict_allow, dict_annotation_only)`` for this layer.
	"""
	dict_layer = (dict_policy.get("layers", {}) or {}).get(str_layer) or {}
	dict_annotation_only = {
		**(dict_policy.get("annotation_only") or {}),
		**(dict_layer.get("annotation_only") or {}),
	}
	return dict_layer.get("allow") or {}, dict_annotation_only


def function_line_spans(cls_tree: ast.AST) -> list:
	"""Return the (first, last) line of every function in the tree.

	Parameters
	----------
	cls_tree : ast.AST
		The parsed module.

	Returns
	-------
	list of tuple
		One ``(int_first, int_last)`` pair per function, used only to phrase the message —
		an import deferred into a function is judged exactly like a top-level one.
	"""
	return [
		(cls_n.lineno, max(getattr(c, "lineno", cls_n.lineno) for c in ast.walk(cls_n)))
		for cls_n in ast.walk(cls_tree)
		if isinstance(cls_n, ast.FunctionDef | ast.AsyncFunctionDef)
	]


def disallowed_import_problems(
	cls_tree: ast.AST,
	path_file: pathlib.Path,
	str_layer: str,
	dict_allow: dict,
	dict_annotation_only: dict,
	set_first_party: set[str],
) -> tuple[list, dict]:
	"""Report every import this layer may not take, and collect the annotation-only aliases.

	Parameters
	----------
	cls_tree : ast.AST
		The parsed module.
	path_file : pathlib.Path
		The module being checked, for the message.
	str_layer : str
		The layer the file belongs to.
	dict_allow : dict
		Vendors this layer may import outright.
	dict_annotation_only : dict
		Vendors this layer may name in annotations only.
	set_first_party : set of str
		Top-level package names that belong to this project.

	Returns
	-------
	tuple
		``(list_problems, dict_annotation_aliases)`` — the findings, and the local names
		bound to annotation-only vendors, for the second pass to police.
	"""
	list_functions = function_line_spans(cls_tree)
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
	return list_problems, dict_annotation_aliases


def annotation_only_misuse_problems(
	cls_tree: ast.AST,
	path_file: pathlib.Path,
	str_layer: str,
	dict_annotation_aliases: dict,
	dict_annotation_only: dict,
) -> list:
	"""Report every use of an annotation-only vendor that is not an annotation.

	``-> pd.DataFrame`` in a signature is the vocabulary the layers share and couples
	nothing; ``pd.read_sql(...)`` is a call every copied file inherits.

	Parameters
	----------
	cls_tree : ast.AST
		The parsed module.
	path_file : pathlib.Path
		The module being checked, for the message.
	str_layer : str
		The layer the file belongs to.
	dict_annotation_aliases : dict
		Local name → vendor root, for vendors restricted to annotations.
	dict_annotation_only : dict
		Vendor root → the written reason, quoted back in the message.

	Returns
	-------
	list of str
		Human-readable problems; empty when every use is an annotation.
	"""
	set_annotation_ids = annotation_node_ids(cls_tree)
	list_problems: list[str] = []

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

	dict_allow, dict_annotation_only = resolve_layer_policy(dict_policy, str_layer)
	list_problems, dict_annotation_aliases = disallowed_import_problems(
		cls_tree, path_file, str_layer, dict_allow, dict_annotation_only, set_first_party
	)
	list_problems += annotation_only_misuse_problems(
		cls_tree, path_file, str_layer, dict_annotation_aliases, dict_annotation_only
	)
	return list_problems + direction_problems(cls_tree, path_file, str_layer, dict_policy)


def direction_problems(
	cls_tree: ast.Module, path_file: pathlib.Path, str_layer: str, dict_policy: dict
) -> list[str]:
	"""Return every import that points the WRONG WAY between first-party layers.

	The vendor half of this gate asks "may this layer reach outside the project?". This half
	asks the opposite question — "may this layer reach that layer?" — and they are genuinely
	different: ``utils/`` importing ``model/`` involves no vendor at all, yet it is the design
	error that turns a seam into a cycle. Both rules were prose only
	(``src/utils/CLAUDE.md``: *"utils/ is imported by them, never the reverse"*), and prose
	does not fail a build.

	⚠️ Silent when a layer declares no ``deny_layers``. That is deliberate and is NOT the
	self-skip this gate was just fixed for: the vendor policy is deny-by-default because the
	set of vendors is open-ended, while the set of layers is small, named in the same file,
	and each project decides its own direction. An absent entry means "this layer may reach
	its siblings", which is a real answer rather than an unasked question.

	Parameters
	----------
	cls_tree : ast.Module
		The parsed module.
	path_file : pathlib.Path
		The module's path, for the message.
	str_layer : str
		The layer the file belongs to.
	dict_policy : dict
		The parsed ``.layer-policy.yaml``.

	Returns
	-------
	list of str
		Human-readable problems; empty when the file complies.
	"""
	dict_layer = (dict_policy.get("layers", {}) or {}).get(str_layer) or {}
	dict_deny = dict_layer.get("deny_layers") or {}
	if not dict_deny:
		return []

	# Scope does not change the verdict here either: an import deferred into a function still
	# couples the layers, exactly as it does for a vendor.
	return [
		f"{path_file}:{cls_node.lineno}: layer '{str_layer}' must not import "
		f"'{str_root}'. {dict_deny[str_root]}"
		for cls_node in ast.walk(cls_tree)
		if isinstance(cls_node, ast.Import | ast.ImportFrom)
		for str_root, _ in imported_names(cls_node)
		if str_root in dict_deny
	]


def _report_absent_policy(int_modules: int) -> int:
	"""Explain a missing policy and return the exit code it deserves.

	⚠️ A tree WITH modules and NO policy is a FAILURE, not a skip. The gate used to return 0
	in silence here, so three of the five Python tiers shipped with no import boundary at all
	while their CI stayed green — a gate reporting its own blindness as OK, which is the exact
	failure mode this repo writes gates to prevent. A tree with nothing in it is different:
	nothing to check is not the same as failing to check.

	The two causes of "no policy" are told apart because the remedies differ — an unimportable
	parser is a broken environment, an absent file is a tier nobody wrote one for.

	Parameters
	----------
	int_modules : int
		How many modules were discovered under the source root.

	Returns
	-------
	int
		``1`` when there was code to check, ``0`` when there was not.
	"""
	if int_modules == 0:
		print(f"No {_POLICY_FILE} and no modules to check — nothing to do.")
		return 0
	if yaml is None:
		print(
			"❌ PyYAML is not importable, so the layer policy cannot be read. The gate "
			"checked NOTHING. Install it (it is a declared dependency) rather than letting "
			"an unreadable policy pass for a satisfied one."
		)
	else:
		print(
			f"❌ {int_modules} module(s) under {_SRC_ROOT}/ and no {_POLICY_FILE}. "
			f"Deny-by-default cannot deny anything without a policy, so this tree has no "
			f"import boundary. Add {_POLICY_FILE} at the project root."
		)
	return 1


def main() -> int:
	"""Check every module under ``src/`` against the layer policy.

	Returns
	-------
	int
		``0`` when the tree complies (or no policy is present), ``1`` otherwise.
	"""
	path_root = pathlib.Path.cwd()
	path_src = path_root / _SRC_ROOT
	if not path_src.is_dir():
		print(f"No {_SRC_ROOT}/ directory — skipping the layer-import check.")
		return 0

	list_modules = [
		path_file
		for path_file in sorted(path_src.rglob("*.py"))
		if "__pycache__" not in path_file.parts
	]
	dict_policy = load_policy(path_root)
	if dict_policy is None:
		return _report_absent_policy(len(list_modules))

	# How many leading path components to strip before the layer is named. 0 for a flat
	# layout (src/<layer>/…); lib-minimal nests its layers inside the distributable package
	# (src/<pkg>/_internal/<layer>/…) and sets 2, so one engine serves both shapes instead
	# of the layer silently resolving to the package name and matching no policy entry.
	int_prefix = int(dict_policy.get("src_prefix_depth", 0))

	set_first_party = first_party_roots(path_src, dict_policy)
	list_all: list[str] = []
	for path_file in list_modules:
		tuple_rel = path_file.relative_to(path_src).parts[int_prefix:]
		# A module sitting directly under the layer root has no directory to name its layer,
		# but it is exactly where an entrypoint lives — skipping it would let src/main.py
		# import any vendor and bypass the policy entirely. It gets its own layer name so the
		# policy can speak about it; deny-by-default then applies as everywhere else.
		str_layer = tuple_rel[0] if len(tuple_rel) > 1 else _ROOT_LAYER
		list_all.extend(find_file_problems(path_file, str_layer, dict_policy, set_first_party))

	for str_problem in list_all:
		print(f"❌ {str_problem}")
	if list_all:
		print(f"\n{len(list_all)} layer-import violation(s).")
		return 1
	# Print WHAT was checked: a silent gate cannot be told from an absent one.
	print(f"✅ layer-import policy OK ({len(list_modules)} module(s) checked).")
	return 0


if __name__ == "__main__":
	# Windows' stdout defaults to cp1252, which cannot encode the status glyphs this
	# script prints: it would die with UnicodeEncodeError before reporting anything. And
	# because this backs an always_run pre-commit hook, that crash blocks EVERY commit from
	# a Windows checkout rather than failing the file under check. Fixed at the I/O seam so
	# the glyphs stay; a test pins it with PYTHONIOENCODING=cp1252.
	for cls_stream in (sys.stdout, sys.stderr):
		if hasattr(cls_stream, "reconfigure"):
			cls_stream.reconfigure(encoding="utf-8", errors="replace")

	sys.exit(main())
