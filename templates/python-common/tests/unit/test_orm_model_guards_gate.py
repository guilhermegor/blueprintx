"""Unit tests for the ORM model-definition guards gate (blueprintx#361; offline, no network).

Each guard needs BOTH directions proven: the dangerous form must FAIL naming the file and the
line; the safe form must PASS. A gate that cannot fail is reporting its own blindness as OK —
the exact failure mode this repo's gates exist to prevent.
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


gate = _load("check_orm_model_guards")


def _python_file(path_dir: Path, str_source: str, str_name: str = "sample.py") -> Path:
	"""Write a Python source file and return its path.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory to write into.
	str_source : str
		File contents.
	str_name : str, optional
		Filename to use, by default ``"sample.py"``.

	Returns
	-------
	pathlib.Path
		The written file.
	"""
	path_file = path_dir / str_name
	path_file.write_text(str_source, encoding="utf-8")
	return path_file


# --------------------------
# 1. Bitwise &/|/~ inside .where()/.filter()
# --------------------------


def test_bitwise_and_inside_where_is_reported(tmp_path: Path) -> None:
	"""``&`` inside ``.where(...)`` is a precedence hazard, flagged unconditionally."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy import select\n\n"
		"stmt = select(User).where(User.age == 18 & User.is_active == True)\n",
	)

	list_problems, _ = gate.check_python_file(path_file)

	assert len(list_problems) == 1
	assert "bitwise operator" in list_problems[0]
	assert "orm-guard-ok:" in list_problems[0]


def test_bitwise_or_inside_filter_is_reported(tmp_path: Path) -> None:
	"""``|`` inside ``.filter(...)`` is the same hazard as ``&`` inside ``.where(...)``."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy.orm import Session\n\nsession.query(User).filter(User.a | User.b)\n",
	)

	assert len(gate.check_python_file(path_file)[0]) == 1


def test_and_or_house_form_inside_where_passes(tmp_path: Path) -> None:
	"""``and_()``/``or_()`` cannot be mis-parenthesised and must never be flagged."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy import select, and_\n\n"
		"stmt = select(User).where(and_(User.age == 18, User.is_active == True))\n",
	)

	assert gate.check_python_file(path_file)[0] == []


def test_bitwise_operator_outside_where_filter_is_not_flagged(tmp_path: Path) -> None:
	"""A ``&`` used elsewhere (e.g. real bit-flag arithmetic) is out of this gate's scope."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy import select\n\nint_mask = 0b1010 & 0b0110\n",
	)

	assert gate.check_python_file(path_file)[0] == []


def test_no_sqlalchemy_import_skips_the_bitwise_check(tmp_path: Path) -> None:
	"""A file with no ``sqlalchemy`` import is out of scope (e.g. a pandas ``.filter()``)."""
	path_file = _python_file(tmp_path, "df.filter(items=a & b)\n")

	assert gate.check_python_file(path_file)[0] == []


# --------------------------
# 2. Two Base / early create_all
# --------------------------


def test_two_declarative_base_subclasses_across_the_tree_are_reported(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A second ``DeclarativeBase`` subclass anywhere in ``src/`` is a violation for BOTH."""
	path_src = tmp_path / "src"
	path_src.mkdir()
	(path_src / "a.py").write_text(
		"from sqlalchemy.orm import DeclarativeBase\n\nclass Base(DeclarativeBase):\n\tpass\n",
		encoding="utf-8",
	)
	(path_src / "b.py").write_text(
		"from sqlalchemy.orm import DeclarativeBase\n\nclass Base2(DeclarativeBase):\n\tpass\n",
		encoding="utf-8",
	)
	monkeypatch.chdir(tmp_path)

	assert gate.main() == 1


def test_single_declarative_base_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""Exactly one ``DeclarativeBase`` subclass in the tree is the expected, safe shape."""
	path_src = tmp_path / "src"
	path_src.mkdir()
	(path_src / "a.py").write_text(
		"from sqlalchemy.orm import DeclarativeBase\n\nclass Base(DeclarativeBase):\n\tpass\n",
		encoding="utf-8",
	)
	monkeypatch.chdir(tmp_path)

	assert gate.main() == 0


def test_module_scope_create_all_is_reported(tmp_path: Path) -> None:
	"""``Base.metadata.create_all(...)`` at import time is a violation."""
	path_file = _python_file(
		tmp_path, "from .base import Base\n\nBase.metadata.create_all(engine)\n"
	)

	list_problems, _ = gate.check_python_file(path_file)

	assert len(list_problems) == 1
	assert "MODULE scope" in list_problems[0]


def test_create_all_inside_a_function_passes(tmp_path: Path) -> None:
	"""``create_all`` deferred into a function (run after models import) is the safe shape."""
	path_file = _python_file(
		tmp_path,
		"from .base import Base\n\ndef init() -> None:\n\tBase.metadata.create_all(engine)\n",
	)

	assert gate.check_python_file(path_file)[0] == []


def test_unrelated_create_all_method_is_not_flagged(tmp_path: Path) -> None:
	"""A ``.create_all()`` not chained off ``.metadata`` is out of scope (low false-positive)."""
	path_file = _python_file(tmp_path, "cache.create_all()\n")

	assert gate.check_python_file(path_file)[0] == []


# --------------------------
# 3. Duplicate constraint name= across a same-file mixin MRO
# --------------------------


def test_duplicate_constraint_name_across_mixins_is_reported(tmp_path: Path) -> None:
	"""Two mixins sharing a constraint ``name=`` silently overwrite one another in the MRO."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy import UniqueConstraint\n\n"
		"class MixinA:\n"
		"\t__table_args__ = (UniqueConstraint('a', name='uq_x'),)\n\n"
		"class MixinB:\n"
		"\t__table_args__ = (UniqueConstraint('b', name='uq_x'),)\n\n"
		"class Model(MixinA, MixinB):\n"
		"\tpass\n",
	)

	list_problems, _ = gate.check_python_file(path_file)

	assert len(list_problems) == 1
	assert "uq_x" in list_problems[0]
	assert "orm-guard-ok:" in list_problems[0]


def test_distinct_constraint_names_across_mixins_pass(tmp_path: Path) -> None:
	"""Distinctly named constraints across mixins compose without collision."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy import UniqueConstraint\n\n"
		"class MixinA:\n"
		"\t__table_args__ = (UniqueConstraint('a', name='uq_x'),)\n\n"
		"class MixinB:\n"
		"\t__table_args__ = (UniqueConstraint('b', name='uq_y'),)\n\n"
		"class Model(MixinA, MixinB):\n"
		"\tpass\n",
	)

	assert gate.check_python_file(path_file)[0] == []


def test_single_class_with_no_bases_never_flags_its_own_constraint(tmp_path: Path) -> None:
	"""A lone model with one constraint has nothing to collide with."""
	path_file = _python_file(
		tmp_path,
		"from sqlalchemy import UniqueConstraint\n\n"
		"class Model:\n"
		"\t__table_args__ = (UniqueConstraint('a', name='uq_x'),)\n",
	)

	assert gate.check_python_file(path_file)[0] == []


# --------------------------
# Escape hatch — present with a reason suppresses; empty/blank still fails
# --------------------------


def test_escape_hatch_with_reason_suppresses_the_finding(tmp_path: Path) -> None:
	"""A written reason after the marker is accepted."""
	path_file = _python_file(
		tmp_path,
		"from .base import Base\n\n"
		"Base.metadata.create_all(engine)  # orm-guard-ok: single-tenant script, reviewed\n",
	)

	assert gate.check_python_file(path_file)[0] == []


def test_escape_hatch_with_empty_reason_still_fails(tmp_path: Path) -> None:
	"""A bare marker with no reason (or whitespace only) is rejected, not accepted."""
	path_file = _python_file(
		tmp_path,
		"from .base import Base\n\nBase.metadata.create_all(engine)  # orm-guard-ok:   \n",
	)

	assert len(gate.check_python_file(path_file)[0]) == 1


# --------------------------
# Zero-discovery guard — a wrong cwd must FAIL, not report success silently
# --------------------------


def test_main_skips_when_src_is_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""No ``src/`` directory at all is a legitimate skip."""
	monkeypatch.chdir(tmp_path)

	assert gate.main() == 0


def test_main_fails_on_zero_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""``src/`` exists but holds no Python files — that must FAIL, not pass silently."""
	(tmp_path / "src").mkdir()
	monkeypatch.chdir(tmp_path)

	assert gate.main() == 1


def test_main_passes_on_a_clean_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""A real file with no violations reports success."""
	path_src = tmp_path / "src"
	path_src.mkdir()
	(path_src / "mod.py").write_text("int_x = 1\n", encoding="utf-8")
	monkeypatch.chdir(tmp_path)

	assert gate.main() == 0
