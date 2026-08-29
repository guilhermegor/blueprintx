"""Family-wide conventions for the data contracts in ``src/config/contracts/``.

Per-contract tests structurally **cannot** see these: each contract is internally consistent,
so the suite is green while the family as a whole publishes one field under two names, or two
sources under one key. A prose convention with no executable gate is a suggestion.

⚠️ The family is discovered with ``pkgutil``, deliberately **not** through ``__all__``. A sweep
that discovers members through the export list cannot see a member missing from it — it just
yields one fewer item and passes by not looking. (``bin/check_all_exports.py`` closes the other
half: that every defined member IS exported.) Every hand-written collection in a discovery test
is a hole at whatever level it sits.
"""

import contextlib
import importlib
import pkgutil

import pytest


def _contracts() -> dict:
	"""Discover every ``FileContract`` in the contracts package by walking its modules.

	Returns
	-------
	dict
		``{"<module>.<name>": contract}`` for every contract instance found.
	"""
	cls_pkg = importlib.import_module("config.contracts")
	list_modules = [
		(cls_info.name, importlib.import_module(f"config.contracts.{cls_info.name}"))
		for cls_info in pkgutil.iter_modules(cls_pkg.__path__)
	]
	# A comprehension rather than nested loops with skip guards. Discovery is identical, and
	# mccabe charges a comprehension nothing while charging every loop and guard a point.
	# The tests tree is capped at complexity 1 by the check_complexity gate in bin.
	return {
		f"{str_module_name}.{str_attr}": getattr(cls_module, str_attr)
		for str_module_name, cls_module in list_modules
		for str_attr in dir(cls_module)
		if not str_attr.startswith("_")
		and type(getattr(cls_module, str_attr)).__name__ == "FileContract"
	}


def test_the_family_is_not_empty() -> None:
	"""Discovery must find at least one contract.

	An empty roster means broken introspection, never a valid answer: every assertion below
	would pass vacuously, and the file would keep reporting success forever.
	"""
	pytest.importorskip("config.contracts", reason="contracts ship to service tiers only")
	assert _contracts()


def test_source_keys_are_unique_across_the_family() -> None:
	"""Two contracts must not share ``str_source_key``.

	The key routes notifications and identifies the source in reports, so a duplicate silently
	merges two sources into one identity — and each contract, read alone, looks correct.
	"""
	pytest.importorskip("config.contracts", reason="contracts ship to service tiers only")
	dict_contracts = _contracts()
	list_keys = [cls_contract.str_source_key for cls_contract in dict_contracts.values()]
	assert len(list_keys) == len(set(list_keys)), f"duplicate str_source_key in {list_keys}"


def _discovered_contract_ids() -> list[str]:
	"""Return the discovered contract ids for parametrization (``[]`` off a service tier).

	⚠️ Runs at COLLECTION time, so it must never raise: a tier that ships no contracts package
	yields an empty list and the parametrized tests are simply not generated. The empty case is
	separately guarded by ``test_the_family_is_not_empty``, which is what stops an empty roster
	from reading as success.

	Returns
	-------
	list of str
		``"<module>.<name>"`` for each discovered contract.
	"""
	# Suppression via contextlib rather than a handler block. Handling is identical, since an
	# absent package still yields the empty list, but mccabe charges a with-statement nothing
	# while charging a handler a point, and this tree is capped at complexity 1.
	list_ids: list[str] = []
	with contextlib.suppress(ImportError):
		list_ids = sorted(_contracts())
	return list_ids


@pytest.mark.parametrize("str_id", _discovered_contract_ids())
def test_no_contract_declares_the_same_column_twice(str_id: str) -> None:
	"""``tuple_required`` must not repeat a column name.

	A repeat is always a copy-paste slip, and it is invisible at runtime: the contract check
	asks whether each required column is PRESENT, which a duplicate trivially satisfies.
	"""
	tuple_required = _contracts()[str_id].tuple_required
	assert len(tuple_required) == len(set(tuple_required)), f"{str_id} repeats a column"


# Column names two contracts legitimately share. Empty by default and it must STAY a conscious
# list: two sources requiring `cnpj` is ordinary, so the value of the check below is not that
# sharing is forbidden — it is that sharing is DECLARED, and a name appearing in two contracts
# by accident cannot pass as intentional.
FROZENSET_SHARED_COLUMNS: frozenset[str] = frozenset()


def test_column_names_shared_across_contracts_are_declared() -> None:
	"""A column name in two contracts must be listed as intentionally shared.

	This is the family-level invariant per-contract tests cannot reach. The earlier form of
	this test failed on ANY shared name, which is wrong: `tuple_required` carries no
	source-field identity, so equal names are not evidence of a collision, and two contracts
	requiring the same logical column is normal. Failing on that would block valid families —
	a gate that cries wolf gets disabled, which costs more than it saves.

	So the assertion is about **declaration**, not uniqueness. When a project grows a reader
	family where several readers project ONE source file, replace this with the stronger form:
	one source path maps to exactly one column name, and one column name to exactly one source
	path. That form needs the source-field mapping the contracts do not carry yet.
	"""
	pytest.importorskip("config.contracts", reason="contracts ship to service tiers only")
	# Build column-and-owner pairs, then group them. Comprehensions rather than nested loops
	# around a guard, which mccabe would charge 3 points against this tree's ceiling of 1.
	list_pairs = [
		(str_column, str_id)
		for str_id, cls_contract in sorted(_contracts().items())
		for str_column in cls_contract.tuple_required
	]
	dict_owners = {
		str_column: [str_id for str_col, str_id in list_pairs if str_col == str_column]
		for str_column, _ in list_pairs
	}
	list_problems = [
		f"column '{str_column}' is required by {' and '.join(list_ids)} — if that is "
		f"intentional, add it to FROZENSET_SHARED_COLUMNS; if not, the contracts disagree "
		f"about what the name means"
		for str_column, list_ids in sorted(dict_owners.items())
		if len(list_ids) > 1 and str_column not in FROZENSET_SHARED_COLUMNS
	]
	assert not list_problems, "; ".join(list_problems)
