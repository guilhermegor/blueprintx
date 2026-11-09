"""Unit tests for the HTTP download seam (SSRF guards, plus a loopback redirect check)."""

from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import threading

import pytest

from src.utils.http_downloader import _fetch_bytes, download_file


class _RedirectHandler(BaseHTTPRequestHandler):
    """Serve a 302 for every GET."""

    def do_GET(self) -> None:  # noqa: N802
        """Answer with a redirect to another path."""
        self.send_response(302)
        self.send_header("Location", "/elsewhere")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Silence request logging."""


@pytest.fixture
def str_redirect_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Yield the URL of a local server that always answers 302, bypassing any proxy.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Sets ``no_proxy`` so an ambient ``http_proxy`` cannot intercept the loopback call.

    Yields
    ------
    str
        The redirecting URL.
    """
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    cls_server = HTTPServer(("127.0.0.1", 0), _RedirectHandler)
    cls_thread = threading.Thread(target=cls_server.serve_forever, daemon=True)
    cls_thread.start()
    yield f"http://127.0.0.1:{cls_server.server_port}/start"
    cls_server.shutdown()
    cls_server.server_close()
    cls_thread.join(timeout=5)


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


@pytest.mark.allow_network
def test_fetch_bytes_redirect_raises_oserror_not_typeerror(str_redirect_url: str) -> None:
    """A 302 surfaces as the intended OSError, not a TypeChecker TypeError."""
    with pytest.raises(OSError, match="redirect blocked"):
        _fetch_bytes(str_redirect_url, 5)
