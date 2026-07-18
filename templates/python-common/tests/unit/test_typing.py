"""Unit tests for the runtime type-checking helpers.

The engine ships to two layouts — ``src/utils/typing`` (MVC) and
``src/chassis/typing`` (DDD) — so the import is resolved through the same
layout-agnostic shim the shared helpers use.
"""

from unittest.mock import MagicMock

import pytest


try:
	from src.utils.typing import TypeChecker, type_checker
except ModuleNotFoundError:  # pragma: no cover - depends on the scaffolded layout
	from src.chassis.typing import TypeChecker, type_checker


class _Sample(metaclass=TypeChecker):
	"""Sample class exercising the metaclass on every method kind."""

	def __init__(self, n: int) -> None:
		"""Store ``n``.

		Parameters
		----------
		n : int
			A number.
		"""
		self.n = n

	@staticmethod
	def doubled(x: int) -> int:
		"""Return ``x`` doubled.

		Parameters
		----------
		x : int
			A number.

		Returns
		-------
		int
			``x * 2``.
		"""
		return x * 2

	def maybe(self, value: str | None) -> str:
		"""Return ``value`` or a placeholder.

		Parameters
		----------
		value : str | None
			Optional text.

		Returns
		-------
		str
			The value or ``"<none>"``.
		"""
		return value or "<none>"

	def total(self, values: list[int]) -> int:
		"""Sum ``values``.

		Parameters
		----------
		values : list[int]
			Numbers to add.

		Returns
		-------
		int
			The sum.
		"""
		return sum(values)


def test_metaclass_allows_valid_calls() -> None:
	"""Correctly-typed calls pass through unchanged."""
	cls_sample = _Sample(10)
	assert cls_sample.n == 10
	assert cls_sample.maybe("x") == "x"


def test_metaclass_staticmethod_via_instance_not_broken() -> None:
	"""A static method called via an instance does not receive ``self``."""
	assert _Sample(1).doubled(5) == 10
	assert _Sample.doubled(5) == 10


def test_metaclass_rejects_wrong_type() -> None:
	"""A wrong-typed argument raises ``TypeError``."""
	with pytest.raises(TypeError):
		_Sample(1).doubled("five")


def test_metaclass_pep604_optional_accepts_none() -> None:
	"""A PEP 604 ``str | None`` parameter accepts ``None``."""
	assert _Sample(1).maybe(None) == "<none>"


def test_metaclass_pep604_union_rejects_other_type() -> None:
	"""A PEP 604 union rejects a value outside the union."""
	with pytest.raises(TypeError):
		_Sample(1).maybe(123)


def test_decorator_checks_standalone_function() -> None:
	"""The decorator validates a standalone function's arguments."""

	@type_checker
	def add(a: int, b: int) -> int:
		"""Add two ints.

		Parameters
		----------
		a : int
			First addend.
		b : int
			Second addend.

		Returns
		-------
		int
			The sum.
		"""
		return a + b

	assert add(1, 2) == 3
	with pytest.raises(TypeError):
		add(1, "two")


def test_bool_is_not_accepted_as_int() -> None:
	"""``bool`` is rejected where ``int`` is annotated.

	PEP 484 makes ``bool`` a subtype of ``int``, which would let a stray ``True``
	silently count as ``1``. This project overrides that on purpose.
	"""
	with pytest.raises(TypeError):
		_Sample(1).doubled(True)


def test_bool_rejected_inside_a_generic_container() -> None:
	"""The strict-``int`` policy reaches inside a generic container.

	Only a single-element container is asserted deterministically: beartype's
	default ``O(1)`` strategy type-checks **one pseudo-randomly sampled item** per
	call rather than the whole container, so a bad element in a longer list is
	caught probabilistically (~1/len per call, across repeated calls in practice).
	Asserting on a multi-element list here would be a flaky test.
	"""
	assert _Sample(1).total([1, 2]) == 3
	with pytest.raises(TypeError):
		_Sample(1).total([True])


def test_bare_mock_is_rejected_but_specced_mock_passes() -> None:
	"""A bare ``Mock`` fails; a ``spec=``-ed one satisfies the annotation.

	``spec=`` rewrites the mock's ``__class__``, so it passes ``isinstance`` — the
	supported way to mock a typed collaborator.
	"""
	with pytest.raises(TypeError):
		_Sample(MagicMock())
	assert _Sample(MagicMock(spec=int)).n is not None
