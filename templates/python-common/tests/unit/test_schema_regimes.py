"""Unit tests for the ``utils.schema_regimes`` seam over ``pure-schema-regimes``."""

import pure_schema_regimes
import pytest

from utils.schema_regimes import (
    RegimeBoundAdapter,
    RegimeRegistry,
    RegimeWindow,
    SpecGapRegistry,
)


@pytest.mark.parametrize(
    "cls_seam",
    [RegimeBoundAdapter, RegimeRegistry, RegimeWindow, SpecGapRegistry],
)
def test_seam_reexports_the_package_object(cls_seam: type) -> None:
    """Each name the seam exports is the package's own object.

    Parameters
    ----------
    cls_seam : type
        A class imported through the seam.

    Returns
    -------
    None
    """
    assert getattr(pure_schema_regimes, cls_seam.__name__) is cls_seam


@pytest.mark.parametrize(
    ("int_period", "str_expected"),
    [(202311, "cnpj_keyed"), (202312, "cnpj_classe_keyed")],
)
def test_registry_resolves_the_cvm_cutover(*, int_period: int, str_expected: str) -> None:
    """The CVM fund-profile cutover resolves to the regime that published the period.

    Parameters
    ----------
    int_period : int
        A ``YYYYMM`` period either side of the cutover.
    str_expected : str
        The regime name expected to cover it.

    Returns
    -------
    None
    """
    cls_registry = RegimeRegistry(
        [
            RegimeWindow(str_name="cnpj_keyed", int_period_start=None, int_period_end=202311),
            RegimeWindow(
                str_name="cnpj_classe_keyed", int_period_start=202312, int_period_end=None
            ),
        ]
    )
    assert cls_registry.resolve(int_period).str_name == str_expected
