"""Unit tests for the sidecar-metadata seam (locate / fetch-or-None / parse).

Doubles as the worked example: a reader builds the descriptor URL (:func:`cvm_meta_url` or a
sibling locator), fetches it to the bronze layer with :func:`fetch_sidecar_text` (getting the
text back, or ``None`` when the source has none), and parses it with
:func:`parse_sidecar_metadata` to define the contract.
"""

from pathlib import Path

# Bare ``utils.`` prefix (not ``src.utils.``), matching the repo's cross-module test convention
# (see test_provenance / test_logs_emitter): a second module copy under the ``src.`` prefix
# breaks type identity for a beartype-checked seam.
from utils.sidecar_metadata import cvm_meta_url, fetch_sidecar_text, parse_sidecar_metadata


_META_TEXT = "Campo;Descricao;Tipo;Tamanho\nCNPJ;CNPJ do fundo;string;14\nVALOR;Valor;number;18\n"


def test_cvm_meta_url_builds_meta_path() -> None:
	"""The reference locator inserts ``META/meta_<key>.txt`` under the base URL."""
	str_url = cvm_meta_url("https://dados.cvm.gov.br/dados/FI/DOC/CAD/", "cad_fi")
	assert str_url == "https://dados.cvm.gov.br/dados/FI/DOC/CAD/META/meta_cad_fi.txt"


def test_parse_sidecar_metadata_maps_fields_by_first_column() -> None:
	"""Each field keys the remaining columns by their header name."""
	dict_meta = parse_sidecar_metadata(_META_TEXT)
	assert set(dict_meta) == {"CNPJ", "VALOR"}
	assert dict_meta["CNPJ"] == {"Descricao": "CNPJ do fundo", "Tipo": "string", "Tamanho": "14"}


def test_parse_sidecar_metadata_empty_when_no_data_rows() -> None:
	"""A header-only (or blank) descriptor parses to an empty map, not an error."""
	assert parse_sidecar_metadata("Campo;Tipo\n") == {}
	assert parse_sidecar_metadata("") == {}


def test_fetch_sidecar_text_returns_none_when_source_has_no_sidecar(tmp_path: Path) -> None:
	"""A failed download (the source publishes no sidecar) yields ``None``, never raises."""

	def _absent(_str_url: str, _path_dest: Path) -> Path:
		raise OSError("404 Not Found")

	assert fetch_sidecar_text("https://x/META/meta_none.txt", tmp_path / "m.txt", _absent) is None


def test_fetch_sidecar_text_persists_and_returns_text(tmp_path: Path) -> None:
	"""A present sidecar is written to the bronze path and its decoded text is returned."""
	path_dest = tmp_path / "raw" / "meta_cad_fi.txt"

	def _writes(_str_url: str, path_target: Path) -> Path:
		path_target.parent.mkdir(parents=True, exist_ok=True)
		path_target.write_bytes(_META_TEXT.encode("utf-8"))
		return path_target

	str_text = fetch_sidecar_text("https://x/META/meta_cad_fi.txt", path_dest, _writes)
	assert path_dest.exists()  # persisted to bronze (the runtime half)
	assert str_text == _META_TEXT  # returned for contract definition (the dev-time half)
