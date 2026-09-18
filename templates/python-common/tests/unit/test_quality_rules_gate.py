"""Unit tests for the quality-rules registry gate (blueprintx#432).

**Silence is the failure mode under test.** This gate's own restricted parser used to
drop any line it did not recognise, so a valid-looking ``- id: rule # comment`` parsed to
nothing, ``main`` then checked zero rules, and the run reported success — a registry
that describes nothing passes exactly like a registry that describes everything
(blueprintx#503). Every test below pins one way that silence can come back:

- the parser must REJECT what it cannot consume rather than skip it;
- an empty parse must be a finding, never a clean run;
- each declared config assertion must be checked, not just the first one;
- an explicit ``status:``/``overridden_by:`` exception must still count as coverage,
  since rejecting it would push authors back to the omission this registry forbids.
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


_BIN = Path(__file__).resolve().parents[2] / "bin"


def _load(str_name: str) -> ModuleType:
	"""Load a ``bin/`` script by path (``bin/`` is not a package).

	Parameters
	----------
	str_name : str
		Module stem under ``bin/``.

	Returns
	-------
	ModuleType
		The imported module.
	"""
	cls_spec = importlib.util.spec_from_file_location(str_name, _BIN / f"{str_name}.py")
	cls_module = importlib.util.module_from_spec(cls_spec)
	sys.modules[str_name] = cls_module
	cls_spec.loader.exec_module(cls_module)
	return cls_module


gate = _load("check_quality_rules")


_STR_MINIMAL = """- id: sample
  intent: "Something is prohibited."
  docs: docs/quality-rules.md#sample
  python:
    tool: ruff
    rule: C901
"""


def _write(path_dir: Path, str_body: str) -> Path:
	"""Write a registry file and return its path.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory to write into.
	str_body : str
		Registry contents.

	Returns
	-------
	pathlib.Path
		The written file.
	"""
	path_yaml = path_dir / "quality-rules.yaml"
	path_yaml.write_text(str_body, encoding="utf-8")
	return path_yaml


# --------------------------
# The parser rejects what it cannot consume
# --------------------------


def test_an_inline_comment_on_an_id_is_rejected_not_dropped(tmp_path: Path) -> None:
	"""``- id: rule # comment`` is valid YAML this parser does not support.

	It must say so. Dropping the line silently produced an empty parse that read as a
	clean run — the defect this gate exists to prevent, inside the gate itself.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_yaml = _write(tmp_path, _STR_MINIMAL.replace("- id: sample", "- id: sample # note"))
	with pytest.raises(gate.RegistryError):
		gate.parse_registry(path_yaml)


def test_malformed_nonempty_content_is_rejected(tmp_path: Path) -> None:
	"""Content that matches no key pattern is a finding, not a no-op.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_yaml = _write(tmp_path, _STR_MINIMAL + "        deeply: indented\n")
	with pytest.raises(gate.RegistryError):
		gate.parse_registry(path_yaml)


def test_content_before_the_first_entry_is_rejected(tmp_path: Path) -> None:
	"""A stray key above the first ``- id:`` has no rule to belong to.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_yaml = _write(tmp_path, "  intent: \"orphan\"\n" + _STR_MINIMAL)
	with pytest.raises(gate.RegistryError):
		gate.parse_registry(path_yaml)


def test_an_empty_registry_is_rejected(tmp_path: Path) -> None:
	"""A file of only comments parses to nothing, which must not read as success.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	path_yaml = _write(tmp_path, "# only a comment\n")
	with pytest.raises(gate.RegistryError):
		gate.parse_registry(path_yaml)


def test_a_wellformed_registry_still_parses(tmp_path: Path) -> None:
	"""The negative control: strictness must not reject the real schema.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	list_rules = gate.parse_registry(_write(tmp_path, _STR_MINIMAL))
	assert [dict_rule["id"] for dict_rule in list_rules] == ["sample"]


# --------------------------
# Every declared assertion is checked
# --------------------------


def test_every_declared_pattern_is_checked_not_only_the_first(tmp_path: Path) -> None:
	"""A second declared value drifting is a finding.

	One ``pattern:`` per entry meant the registry asserted one number while vouching for
	several — the later ceilings could drift with nothing reporting it.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	(tmp_path / "conf.txt").write_text("first_value=1\n", encoding="utf-8")
	dict_entry = {"file": "conf.txt", "patterns": ["first_value=1", "second_value=2"]}
	list_problems = gate.config_pattern_problems([{"id": "r", "python": dict_entry}], tmp_path)
	assert len(list_problems) == 1
	assert "second_value=2" in list_problems[0]


def test_a_single_pattern_entry_still_works(tmp_path: Path) -> None:
	"""The older one-assertion form keeps working alongside ``patterns:``.

	Parameters
	----------
	tmp_path : pathlib.Path
		A throwaway directory pytest provides per test.
	"""
	(tmp_path / "conf.txt").write_text("only_value=7\n", encoding="utf-8")
	dict_entry = {"file": "conf.txt", "pattern": "only_value=7"}
	assert gate.config_pattern_problems([{"id": "r", "python": dict_entry}], tmp_path) == []


# --------------------------
# Coverage accepts an explicit exception
# --------------------------


def test_an_exception_only_entry_counts_as_coverage() -> None:
	"""``status:``/``overridden_by:`` without tool/rule is a documented, valid entry.

	Rejecting it would force an author to invent a tool name or leave the language out
	entirely — the omission this registry exists to forbid.
	"""
	dict_rule = {
		"id": "r",
		"python": {"tool": "ruff", "rule": "C901"},
		"typescript": {"status": "not-implemented", "note": "tracked in an issue"},
	}
	assert gate.language_coverage_problems([dict_rule], {"python", "typescript"}) == []


def test_an_unrecognised_status_value_does_not_buy_coverage() -> None:
	"""Only a declared status waives tool+rule; any other string is still an omission.

	The check read ``bool(entry.get("status"))``, so a typo (``not_implemented``) or an
	invented value (``planned``) satisfied coverage without a tool or a rule — the gate
	failing open on the one field whose whole job is to grant an exemption.
	"""
	for str_bogus in ("planned", "not_implemented", "todo", "wip"):
		dict_rule = {
			"id": "r",
			"python": {"tool": "ruff", "rule": "C901"},
			"typescript": {"status": str_bogus, "note": "tracked in an issue"},
		}
		list_problems = gate.language_coverage_problems([dict_rule], {"python", "typescript"})
		assert len(list_problems) == 1, f"{str_bogus!r} was accepted as coverage"
		assert "typescript" in list_problems[0]


def test_an_entry_with_neither_implementation_nor_exception_is_flagged() -> None:
	"""The negative control for the test above: a bare note is still an omission."""
	dict_rule = {
		"id": "r",
		"python": {"tool": "ruff", "rule": "C901"},
		"typescript": {"note": "no tool, no rule, no stated exception"},
	}
	list_problems = gate.language_coverage_problems([dict_rule], {"python", "typescript"})
	assert len(list_problems) == 1
	assert "typescript" in list_problems[0]
