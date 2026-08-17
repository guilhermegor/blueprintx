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
	dict_found: dict = {}
	for cls_info in pkgutil.iter_modules(cls_pkg.__path__):
		cls_module = importlib.import_module(f"config.contracts.{cls_info.name}")
		for str_attr in dir(cls_module):
			if str_attr.startswith("_"):
				continue
			cls_value = getattr(cls_module, str_attr)
			if type(cls_value).__name__ == "FileContract":
				dict_found[f"{cls_info.name}.{str_attr}"] = cls_value
	return dict_found


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


def test_no_contract_declares_the_same_column_twice() -> None:
	"""``tuple_required`` must not repeat a column name.

	A repeat is always a copy-paste slip, and it is invisible at runtime: the contract check
	asks whether each required column is PRESENT, which a duplicate trivially satisfies.
	"""
	pytest.importorskip("config.contracts", reason="contracts ship to service tiers only")
	for str_id, cls_contract in _contracts().items():
		tuple_required = cls_contract.tuple_required
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
	dict_owner: dict[str, str] = {}
	list_problems: list[str] = []
	for str_id, cls_contract in _contracts().items():
		for str_column in cls_contract.tuple_required:
			str_owner = dict_owner.setdefault(str_column, str_id)
			if str_owner != str_id and str_column not in FROZENSET_SHARED_COLUMNS:
				list_problems.append(
					f"column '{str_column}' is required by both {str_owner} and {str_id} — if "
					f"that is intentional, add it to FROZENSET_SHARED_COLUMNS; if not, the two "
					f"contracts disagree about what the name means"
				)
	assert not list_problems, "; ".join(list_problems)
