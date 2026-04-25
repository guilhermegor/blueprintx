"""Post-load semantic validation for binary artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SanityCheck:
	"""Validates a loaded artifact against expected structural constraints.

	Separates semantic validation (caller's responsibility) from persistence
	integrity (handler's responsibility). Use after ``JoblibHandler.read()``.

	Parameters
	----------
	expected_class_name : str or None, optional
		Exact ``__name__`` of the expected class, e.g. ``"RandomForestClassifier"``.
		Pass ``None`` to skip class name checking.
	required_attrs : list of str, optional
		Attribute names the loaded object must expose, e.g. ``["predict", "fit"]``.

	Examples
	--------
	>>> cls_check = SanityCheck(expected_class_name="Pipeline", required_attrs=["predict"])
	>>> cls_check.validate(cls_model)
	"""

	expected_class_name: str | None = None
	required_attrs: list[str] = field(default_factory=list)

	def validate(self, obj: Any) -> None:
		"""Assert that the object satisfies all configured constraints.

		Parameters
		----------
		obj : Any
			The loaded object to validate.

		Raises
		------
		TypeError
			If ``expected_class_name`` is set and ``type(obj).__name__`` does not match.
		AttributeError
			If any attribute in ``required_attrs`` is absent from ``obj``.
		"""

		if self.expected_class_name is not None and type(obj).__name__ != self.expected_class_name:
			raise TypeError(
				f"Expected class {self.expected_class_name!r}, got {type(obj).__name__!r}"
			)
		for str_attr in self.required_attrs:
			if not hasattr(obj, str_attr):
				raise AttributeError(f"Loaded object missing required attribute: {str_attr!r}")
