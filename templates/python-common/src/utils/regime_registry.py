"""Resolve a period to the schema regime that owns it — shared, layout-agnostic lookup.

Part of the per-regime adapter pattern (issue #148). See :mod:`utils.regime_window` for what
one regime window is; this registry is the lookup across every known regime. Mirrors
``model.regime_registry.RegimeRegistry`` (mvc-service-native-db, blueprintx#289) so the two
share vocabulary, while living in the shared ``utils/`` seam any skeleton can import from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.regime_window import RegimeWindow


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). See src/utils/CLAUDE.md.
if TYPE_CHECKING:
	from utils.typing import TypeChecker, type_checker
else:
	try:
		from utils.typing import TypeChecker, type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from chassis.typing import TypeChecker, type_checker


# ⚠️ AMBIGUITY IS RESOLVED AT CONSTRUCTION, NEVER AT LOOKUP.
#
# `resolve` returns the FIRST covering window, so with two overlapping windows the schema a
# period binds to depends on list order — and the docstring promises "in any order". The
# reader would then parse a real file against the wrong published header and produce numbers
# nobody flags: the silent wrong answer this module exists to prevent. Rejecting here means a
# registry that survives construction cannot answer ambiguously.
@type_checker
def _reject_ambiguous_windows(  # complexity-ok: pairwise overlap IS the check
	list_windows: list[RegimeWindow],
) -> None:
	"""Raise when two windows share a name or cover a common period.

	Parameters
	----------
	list_windows : list of RegimeWindow
		The windows a registry is being built from, in any order.

	Raises
	------
	ValueError
		When a regime name repeats, or two windows overlap.
	"""
	list_names = [cls_window.str_name for cls_window in list_windows]
	set_repeated = {str_name for str_name in list_names if list_names.count(str_name) > 1}
	if set_repeated:
		raise ValueError(f"regime names must be unique; repeated: {sorted(set_repeated)}")
	# Sorting by start puts an open start first, so overlap can only occur between neighbours.
	list_sorted = sorted(
		list_windows,
		key=lambda cls_window: (
			cls_window.int_period_start is not None,
			cls_window.int_period_start or 0,
		),
	)
	for cls_earlier, cls_later in zip(list_sorted, list_sorted[1:], strict=False):
		if _windows_overlap(cls_earlier, cls_later):
			raise ValueError(
				f"regime windows overlap: {cls_earlier.str_name} and {cls_later.str_name} "
				f"both cover at least one period, so resolve() would depend on list order"
			)


@type_checker
def _windows_overlap(cls_earlier: RegimeWindow, cls_later: RegimeWindow) -> bool:
	"""Return whether two windows share at least one period.

	Parameters
	----------
	cls_earlier : RegimeWindow
		The window with the earlier (or equally open) start.
	cls_later : RegimeWindow
		The window that starts at or after ``cls_earlier``.

	Returns
	-------
	bool
		``True`` when the earlier window has no end, or its end reaches the later's start.
	"""
	if cls_earlier.int_period_end is None:
		return True
	return (
		cls_later.int_period_start is None
		or cls_earlier.int_period_end >= cls_later.int_period_start
	)


class RegimeRegistry(metaclass=TypeChecker):
	"""Look up which regime window covers a period, or the newest period a closed one covers.

	Parameters
	----------
	list_windows : list of RegimeWindow
		Every regime this registry knows, in any order.
	"""

	def __init__(self, list_windows: list[RegimeWindow]) -> None:
		_reject_ambiguous_windows(list_windows)
		self.list_windows = list_windows

	@type_checker
	def resolve(  # complexity-ok: scanning windows for the covering one is the lookup itself
		self, int_period: int
	) -> RegimeWindow:
		"""Return the regime window covering ``int_period``.

		Parameters
		----------
		int_period : int
			The period to resolve, ``YYYYMM``.

		Returns
		-------
		RegimeWindow
			The window whose :meth:`RegimeWindow.covers` is ``True`` for ``int_period``.

		Raises
		------
		ValueError
			No known regime covers ``int_period``. Names every known window so the caller
			sees where the period would belong, instead of a bare "not found".
		"""
		for cls_window in self.list_windows:
			if cls_window.covers(int_period):
				return cls_window
		raise ValueError(
			f"No regime covers period {int_period}. Known regimes: {self._describe_windows()}."
		)

	@type_checker
	def default_period(  # complexity-ok: name lookup + open/closed check IS the validation
		self, str_name: str
	) -> int:
		"""Return the newest period the named CLOSED regime covers.

		A closed regime has no "today" to fall back on — it was superseded by a later one,
		so its sensible no-args default is its own last covered period, never the wall
		clock. (An open regime's default, if it needs one, is the caller's concern.)

		Parameters
		----------
		str_name : str
			The target regime's :attr:`RegimeWindow.str_name`.

		Returns
		-------
		int
			``int_period_end`` of the named regime.

		Raises
		------
		ValueError
			The name is unknown, or the regime is still open (``int_period_end is None``).
		"""
		cls_match = self._find_by_name(str_name)
		if cls_match is None:
			raise ValueError(
				f"Unknown regime: {str_name!r}. Known regimes: {self._describe_windows()}."
			)
		if not cls_match.is_closed:
			raise ValueError(f"Regime {str_name!r} is open; it has no closed-regime default.")
		return cls_match.int_period_end  # type: ignore[return-value]  # is_closed guarantees not None

	def _find_by_name(  # complexity-ok: scanning windows for the named one is the lookup itself
		self, str_name: str
	) -> RegimeWindow | None:
		"""Return the window named ``str_name``, or ``None`` when no window matches.

		Parameters
		----------
		str_name : str
			The regime name to look up.

		Returns
		-------
		RegimeWindow | None
			The matching window, or ``None``.
		"""
		for cls_window in self.list_windows:
			if cls_window.str_name == str_name:
				return cls_window
		return None

	def _describe_windows(self) -> str:
		"""Render every known window as ``name [start-end]`` for an error message.

		Returns
		-------
		str
			Comma-separated ``name [start-end]`` entries, ``open`` standing in for ``None``.
		"""
		return ", ".join(
			f"{cls_window.str_name} [{cls_window.int_period_start or 'open'}-"
			f"{cls_window.int_period_end or 'open'}]"
			for cls_window in self.list_windows
		)
