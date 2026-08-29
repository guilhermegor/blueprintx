"""Unit tests for the per-regime adapter pattern (issue #148).

The oracle is unit tests against a fixed, measured cutover date — never an invented one.
The issue names it explicitly: a monthly fund-profile series published 106 columns keyed
``CNPJ_FUNDO`` through period ``202311``, then 107 columns keyed
``TP_FUNDO_CLASSE``/``CNPJ_FUNDO_CLASSE`` from ``202312`` on. Every fixture below uses those
two periods as the cutover.
"""

import pytest

# Bare `model.` imports (not `src.model.`) — RegimeRegistry/RegimeReader import RegimeWindow
# the same way internally; a `src.`-prefixed import here would create a SECOND, distinct
# RegimeWindow class under pytest's dual `pythonpath = . src`, and beartype's nominal
# isinstance check on `list[RegimeWindow]` would reject fixture instances built from it.
from model.regime_reader import RegimeReader
from model.regime_registry import RegimeRegistry
from model.regime_window import RegimeWindow


# --------------------------
# Fixtures
# --------------------------
@pytest.fixture
def cls_registry() -> RegimeRegistry:
	"""Build the two-regime registry from the issue's measured cutover (202311 / 202312).

	Returns
	-------
	RegimeRegistry
		A registry with the legacy ``cnpj_keyed`` regime (closed at ``202311``) and the
		current ``cnpj_classe_keyed`` regime (open from ``202312``).
	"""
	return RegimeRegistry(
		[
			RegimeWindow(str_name="cnpj_keyed", int_period_start=None, int_period_end=202311),
			RegimeWindow(
				str_name="cnpj_classe_keyed", int_period_start=202312, int_period_end=None
			),
		]
	)


# --------------------------
# RegimeWindow.covers
# --------------------------
def test_window_covers_period_at_its_closed_end(cls_registry: RegimeRegistry) -> None:
	"""The legacy window covers its own last published period, 202311.

	Parameters
	----------
	cls_registry : RegimeRegistry
		The two-regime fixture registry.

	Returns
	-------
	None
	"""
	assert cls_registry.resolve(202311).str_name == "cnpj_keyed"


def test_window_covers_period_at_the_new_regimes_start(cls_registry: RegimeRegistry) -> None:
	"""The current window covers the first period published under the new schema, 202312.

	Parameters
	----------
	cls_registry : RegimeRegistry
		The two-regime fixture registry.

	Returns
	-------
	None
	"""
	assert cls_registry.resolve(202312).str_name == "cnpj_classe_keyed"


# --------------------------
# RegimeRegistry.resolve — out-of-regime refusal
# --------------------------
def test_resolve_out_of_regime_period_raises_naming_known_regimes() -> None:
	"""A period no registered window covers raises, naming every known regime.

	Uses a registry with only the closed legacy window (bounded on both sides) so a period
	before its start is genuinely out of regime — the two-regime fixture above has no gap.

	Returns
	-------
	None
	"""
	cls_bounded_registry = RegimeRegistry(
		[RegimeWindow(str_name="cnpj_keyed", int_period_start=200001, int_period_end=202311)]
	)
	with pytest.raises(ValueError, match="cnpj_keyed"):
		cls_bounded_registry.resolve(202312)


# --------------------------
# RegimeRegistry.default_period — closed-regime default
# --------------------------
def test_default_period_for_closed_regime_returns_its_last_covered_period(
	cls_registry: RegimeRegistry,
) -> None:
	"""A closed regime's default is its own newest covered period, not wall-clock "today".

	Parameters
	----------
	cls_registry : RegimeRegistry
		The two-regime fixture registry.

	Returns
	-------
	None
	"""
	assert cls_registry.default_period("cnpj_keyed") == 202311


def test_default_period_for_open_regime_raises(cls_registry: RegimeRegistry) -> None:
	"""An open regime has no closed-regime default — it is the caller's concern.

	Parameters
	----------
	cls_registry : RegimeRegistry
		The two-regime fixture registry.

	Returns
	-------
	None
	"""
	with pytest.raises(ValueError, match="open"):
		cls_registry.default_period("cnpj_classe_keyed")


# --------------------------
# RegimeReader — constructor contract
# --------------------------
def test_reader_with_no_period_defaults_to_its_regimes_last_covered_period(
	cls_registry: RegimeRegistry,
) -> None:
	"""A no-args reader for a CLOSED regime resolves to that regime's own last period.

	Parameters
	----------
	cls_registry : RegimeRegistry
		The two-regime fixture registry.

	Returns
	-------
	None
	"""
	cls_reader = RegimeReader(cls_registry, "cnpj_keyed")
	assert cls_reader.int_period == 202311


def test_reader_accepts_a_period_within_its_own_regime(cls_registry: RegimeRegistry) -> None:
	"""A reader bound to a regime accepts a period that regime actually covers.

	Parameters
	----------
	cls_registry : RegimeRegistry
		The two-regime fixture registry.

	Returns
	-------
	None
	"""
	cls_reader = RegimeReader(cls_registry, "cnpj_classe_keyed", int_period=202312)
	assert cls_reader.cls_window.str_name == "cnpj_classe_keyed"


def test_reader_refuses_a_period_belonging_to_a_sibling_regime(
	cls_registry: RegimeRegistry,
) -> None:
	"""A reader bound to one regime refuses a period the sibling regime actually owns.

	Parameters
	----------
	cls_registry : RegimeRegistry
		The two-regime fixture registry.

	Returns
	-------
	None
	"""
	with pytest.raises(ValueError, match="cnpj_classe_keyed"):
		RegimeReader(cls_registry, "cnpj_keyed", int_period=202312)


@pytest.mark.parametrize(
	"int_bad_period",
	[202313, 202400, 20241, 2024011],
)
def test_regime_window_rejects_a_non_yyyymm_bound(int_bad_period: int) -> None:
	"""A bound that is not a ``YYYYMM`` period is refused at construction.

	Without this, ``covers()`` silently answers questions about a period that cannot exist,
	and ``RegimeRegistry.default_period`` can hand back an end its own window does not cover.

	Parameters
	----------
	int_bad_period : int
		An invalid period bound under test.

	Returns
	-------
	None
	"""
	with pytest.raises(ValueError, match="YYYYMM"):
		RegimeWindow(str_name="bad", int_period_start=int_bad_period, int_period_end=None)


def test_regime_window_rejects_a_backwards_range() -> None:
	"""A window whose start is after its end is refused at construction.

	Returns
	-------
	None
	"""
	with pytest.raises(ValueError, match="after period end"):
		RegimeWindow(str_name="bad", int_period_start=202412, int_period_end=202401)


def test_regime_window_still_accepts_open_bounds() -> None:
	"""``None`` on either side remains legal — it is how an open-ended regime is expressed.

	Returns
	-------
	None
	"""
	cls_window = RegimeWindow(str_name="open", int_period_start=None, int_period_end=None)
	assert cls_window.covers(202406) is True
