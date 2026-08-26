"""One schema regime's period coverage.

Part of the per-regime adapter pattern (issue #148): a published series can change its
column set **mid-series**, under one unchanged filename pattern — each contract pinned to
its own published header, never derived from a sibling's. This value object names the
window of periods one such regime covers.
"""

from __future__ import annotations

from dataclasses import dataclass

from utils.typing import TypeChecker


@dataclass(frozen=True)
class RegimeWindow(metaclass=TypeChecker):
	"""The period range one schema regime covers.

	Parameters
	----------
	str_name : str
		The regime's name. Name it after what changed (the columns), never after a
		regulation or a guessed cutover date — only a pinned-header fixture proves either,
		and a wrong date-derived name is an assertion nothing re-checks.
	int_period_start : int | None
		First period this regime covers, ``YYYYMM``. ``None`` means no known earlier bound.
	int_period_end : int | None
		Last period this regime covers, ``YYYYMM``. ``None`` means the regime is still open
		(the currently published schema) — it has no closed-regime default (see
		:class:`model.regime_registry.RegimeRegistry`).
	"""

	str_name: str
	int_period_start: int | None
	int_period_end: int | None

	def covers(  # complexity-ok: a two-sided open-bound range check is the validation itself
		self, int_period: int
	) -> bool:
		"""Return whether ``int_period`` falls inside this window.

		Parameters
		----------
		int_period : int
			The period to check, ``YYYYMM``.

		Returns
		-------
		bool
			``True`` when ``int_period`` is within ``[int_period_start, int_period_end]``
			(either bound may be open).
		"""
		bool_after_start = self.int_period_start is None or int_period >= self.int_period_start
		bool_before_end = self.int_period_end is None or int_period <= self.int_period_end
		return bool_after_start and bool_before_end

	@property
	def is_closed(self) -> bool:
		"""Whether this regime has a known last period (superseded by a later one).

		Returns
		-------
		bool
			``True`` when ``int_period_end`` is set.
		"""
		return self.int_period_end is not None
