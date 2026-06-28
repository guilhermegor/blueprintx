"""Unit tests for the env-wise config-file selector."""

from pathlib import Path

import pytest

from src.config.env_config import resolve_config_path


def test_plain_file_wins_regardless_of_env(tmp_path: Path) -> None:
	"""When a plain <kind>.yaml exists it is returned for any ENV value.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest-provided throwaway directory holding the config file.
	"""
	(tmp_path / "inputs.yaml").write_text("a: 1\n", encoding="utf-8")
	assert resolve_config_path("anything", "inputs", tmp_path) == tmp_path / "inputs.yaml"


def test_env_wise_selects_suffix(tmp_path: Path) -> None:
	"""With no plain file, ENV picks the dev/prd suffixed file.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest-provided throwaway directory holding the env-wise config files.
	"""
	(tmp_path / "inputs_dev.yaml").write_text("a: 1\n", encoding="utf-8")
	(tmp_path / "inputs_prd.yaml").write_text("a: 2\n", encoding="utf-8")
	assert resolve_config_path("production", "inputs", tmp_path) == tmp_path / "inputs_prd.yaml"
	assert resolve_config_path("dev", "inputs", tmp_path) == tmp_path / "inputs_dev.yaml"


@pytest.mark.parametrize(
	"str_env",
	["PRODUCTION", " prod ", "Produção", "PRD", "produção"],
)
def test_env_spelling_variants_resolve(tmp_path: Path, str_env: str) -> None:
	"""Case, trailing spaces and diacritics on a known ENV value all resolve (normalised).

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest-provided throwaway directory holding the env-wise config files.
	str_env : str
		A spelling variant of a known ENV value that must normalise to ``prd``.
	"""
	(tmp_path / "inputs_prd.yaml").write_text("a: 1\n", encoding="utf-8")
	assert resolve_config_path(str_env, "inputs", tmp_path) == tmp_path / "inputs_prd.yaml"


def test_unknown_env_aborts(tmp_path: Path) -> None:
	"""In env-wise mode an unknown ENV fails loud (SystemExit 2).

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest-provided throwaway directory holding the env-wise config file.
	"""
	(tmp_path / "inputs_dev.yaml").write_text("a: 1\n", encoding="utf-8")
	with pytest.raises(SystemExit) as exc:
		resolve_config_path("staging", "inputs", tmp_path)
	assert exc.value.code == 2


def test_missing_env_file_aborts(tmp_path: Path) -> None:
	"""A valid ENV with no matching file fails loud (SystemExit 2).

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest-provided throwaway directory holding the env-wise config file.
	"""
	(tmp_path / "inputs_dev.yaml").write_text("a: 1\n", encoding="utf-8")
	with pytest.raises(SystemExit) as exc:
		resolve_config_path("production", "inputs", tmp_path)  # only _dev exists
	assert exc.value.code == 2
