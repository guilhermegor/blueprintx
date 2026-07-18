"""Core type-validation engine: ``validate_type`` and its method wrapper.

Backed by `beartype <https://github.com/beartype/beartype>`_ — a constant-time,
PEP-compliant runtime type checker — rather than a hand-rolled ``isinstance``
walker. beartype validates far more than the previous implementation (nested
generics, ``dict``/``tuple``/``set`` values, return types, ``TypeVar``), so the
seam gets deeper checking for less code.

Two project-specific policies are layered on top via :data:`CONF`:

* **Violations raise plain ``TypeError``.** beartype's own
  ``BeartypeCallHintParamViolation`` is *not* a ``TypeError`` subclass, so
  ``violation_type=TypeError`` keeps the documented contract intact.
* **``bool`` is not an ``int``.** PEP 484 makes ``bool`` a subtype of ``int``,
  which silently lets a stray ``True`` count as ``1``. The ``int`` hint is
  overridden to exclude ``bool`` (and to admit NumPy integers where NumPy is
  installed), and the override reaches inside generics such as ``list[int]``.

.. note::
   **Container checking is sampled, not exhaustive.** beartype's default
   ``BeartypeStrategy.O1`` type-checks a *single pseudo-randomly chosen item*
   per container per call — that constant-time guarantee is the whole point of
   the library. A bad element in a long list is therefore caught
   probabilistically (~``1/len`` per call), where the previous hand-rolled
   engine walked every element of a ``list[...]``. In exchange, containers the
   old engine never inspected at all (``dict``/``tuple``/``set`` values, nested
   generics) are now checked, along with return types. Do not rely on a single
   call to reject a malformed long container.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from beartype import BeartypeConf, BeartypeHintOverrides, beartype
from beartype.door import die_if_unbearable
from beartype.vale import Is


# NumPy is absent from the leaner tiers (``lib-minimal``), so the integer hint is
# widened only where NumPy actually ships. Keeping this conditional is what lets
# one engine serve every skeleton.
try:
	import numpy as _np

	_INT_BASE: Any = int | _np.integer
except ModuleNotFoundError:  # pragma: no cover - depends on the tier's deps
	_INT_BASE = int


# PEP 484 declares ``bool`` a subtype of ``int``; this project rejects that, so a
# boolean passed where a number is expected fails loudly instead of becoming 0/1.
_NOT_BOOL = Is[lambda obj: not isinstance(obj, bool)]
_INT_HINT = Annotated[_INT_BASE, _NOT_BOOL]


CONF = BeartypeConf(
	violation_type=TypeError,
	hint_overrides=BeartypeHintOverrides({int: _INT_HINT}),
)


_type_check = beartype(conf=CONF)


def validate_type(value: Any, expected_type: Any, param_name: str) -> None:
	"""Raise ``TypeError`` when ``value`` does not satisfy ``expected_type``.

	Parameters
	----------
	value : Any
		Value to validate.
	expected_type : Any
		Annotation to check against.
	param_name : str
		Parameter name shown in the error message.

	Raises
	------
	TypeError
		When the value does not match the expected type.
	"""
	die_if_unbearable(value, expected_type, conf=CONF, exception_prefix=f"{param_name} ")


def create_type_checked_method(original_method: Callable[..., Any]) -> Callable[..., Any]:
	"""Wrap ``original_method`` so each call validates its argument types.

	Parameters
	----------
	original_method : Callable[..., Any]
		Function or method to wrap.

	Returns
	-------
	Callable[..., Any]
		Wrapper that validates argument types before delegating.
	"""
	return _type_check(original_method)
