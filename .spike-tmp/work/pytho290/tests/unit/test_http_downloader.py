"""Unit tests for the HTTP download seam (offline — SSRF/validation guards only)."""

from pathlib import Path

import pytest

from src.utils.http_downloader import download_file


def test_download_rejects_empty_url(tmp_path: Path) -> None:
	"""An empty URL fails fast with ValueError (not retried)."""
	with pytest.raises(ValueError, match="empty download URL"):
		download_file("   ", tmp_path / "out.bin")


def test_download_rejects_non_http_scheme(tmp_path: Path) -> None:
	"""A non-http(s) scheme is rejected before any network access."""
	with pytest.raises(ValueError, match="unsupported URL scheme"):
		download_file("ftp://example.com/x", tmp_path / "out.bin")


def test_download_rejects_loopback_host(tmp_path: Path) -> None:
	"""A loopback host is rejected by the SSRF guard."""
	with pytest.raises(ValueError, match="non-public address"):
		download_file("http://127.0.0.1/secret", tmp_path / "out.bin")


def test_download_rejects_url_without_host(tmp_path: Path) -> None:
	"""A URL with no host is rejected."""
	with pytest.raises(ValueError, match="without host"):
		download_file("http:///nohost", tmp_path / "out.bin")
