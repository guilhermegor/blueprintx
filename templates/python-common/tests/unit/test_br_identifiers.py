"""Unit tests for the Brazilian identifier helpers (CNPJ / CPF)."""

from src.utils.br_identifiers import (
	is_valid_cnpj,
	is_valid_cpf,
	mask_cnpj,
	mask_cpf,
	unmask_cnpj,
	unmask_cpf,
)


# --- CNPJ: unmask ---------------------------------------------------------------


def test_unmask_cnpj_masked_value_returns_bare_digits() -> None:
	"""A punctuated CNPJ unmasks to its 14 bare digits."""
	assert unmask_cnpj("11.222.333/0001-81") == "11222333000181"


def test_unmask_cnpj_float_artifact_drops_trailing_zero_decimal() -> None:
	"""A float→str ``.0`` tail is stripped before normalisation."""
	assert unmask_cnpj("11222333000181.0") == "11222333000181"


def test_unmask_cnpj_short_numeric_left_zero_pads_to_14() -> None:
	"""A short purely-numeric CNPJ is left-zero-padded to 14."""
	assert unmask_cnpj("1222333000181") == "01222333000181"


def test_unmask_cnpj_alphanumeric_uppercases_and_keeps_letters() -> None:
	"""An alphanumeric CNPJ is uppercased with letters preserved."""
	assert unmask_cnpj("12.abc.345/01de-35") == "12ABC34501DE35"


def test_unmask_cnpj_empty_returns_empty() -> None:
	"""An empty input yields an empty string."""
	assert unmask_cnpj("") == ""


# --- CNPJ: mask -----------------------------------------------------------------


def test_mask_cnpj_bare_value_returns_punctuated() -> None:
	"""A bare CNPJ is formatted as ``XX.XXX.XXX/XXXX-XX``."""
	assert mask_cnpj("11222333000181") == "11.222.333/0001-81"


def test_mask_cnpj_invalid_length_passes_through_unmasked() -> None:
	"""An alphanumeric value that cannot reach 14 chars passes through unmasked.

	A short *numeric* value is left-zero-padded to 14 by ``unmask_cnpj`` and then
	masked, so the pass-through branch only triggers for non-14 alphanumeric input.
	"""
	assert mask_cnpj("12ABC") == "12ABC"


# --- CNPJ: validate -------------------------------------------------------------


def test_is_valid_cnpj_legacy_numeric_true() -> None:
	"""A correct legacy numeric CNPJ validates."""
	assert is_valid_cnpj("11.222.333/0001-81") is True


def test_is_valid_cnpj_alphanumeric_2026_format_true() -> None:
	"""The official 2026 alphanumeric CNPJ example validates."""
	assert is_valid_cnpj("12.ABC.345/01DE-35") is True


def test_is_valid_cnpj_wrong_check_digit_false() -> None:
	"""A CNPJ with a wrong check digit is rejected."""
	assert is_valid_cnpj("11222333000182") is False


def test_is_valid_cnpj_all_zeros_false() -> None:
	"""An all-zeros CNPJ is rejected."""
	assert is_valid_cnpj("00000000000000") is False


def test_is_valid_cnpj_wrong_length_false() -> None:
	"""A CNPJ of the wrong length is rejected."""
	assert is_valid_cnpj("112223330001") is False


# --- CPF ------------------------------------------------------------------------


def test_unmask_cpf_masked_value_returns_bare_digits() -> None:
	"""A punctuated CPF unmasks to its 11 bare digits."""
	assert unmask_cpf("529.982.247-25") == "52998224725"


def test_unmask_cpf_float_artifact_drops_trailing_zero_decimal() -> None:
	"""A float→str ``.0`` tail is stripped from a CPF."""
	assert unmask_cpf("52998224725.0") == "52998224725"


def test_unmask_cpf_short_numeric_left_zero_pads_to_11() -> None:
	"""A short CPF is left-zero-padded to 11."""
	assert unmask_cpf("1234567") == "00001234567"


def test_mask_cpf_bare_value_returns_punctuated() -> None:
	"""A bare CPF is formatted as ``XXX.XXX.XXX-XX``."""
	assert mask_cpf("52998224725") == "529.982.247-25"


def test_is_valid_cpf_valid_value_true() -> None:
	"""A correct CPF validates."""
	assert is_valid_cpf("529.982.247-25") is True


def test_is_valid_cpf_wrong_check_digit_false() -> None:
	"""A CPF with a wrong check digit is rejected."""
	assert is_valid_cpf("52998224726") is False


def test_is_valid_cpf_repeated_digits_false() -> None:
	"""A repeated-digit CPF is rejected."""
	assert is_valid_cpf("11111111111") is False
