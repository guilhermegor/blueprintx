"""Unit tests for the HTTP download seam (SSRF guards, plus a loopback redirect check)."""

from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import threading
from urllib import error

import pytest
from pytest_mock import MockerFixture

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
        download_file("   ", path_dest=tmp_path / "out.bin")


def test_download_rejects_non_http_scheme(tmp_path: Path) -> None:
    """A non-http(s) scheme is rejected before any network access."""
    with pytest.raises(ValueError, match="unsupported URL scheme"):
        download_file("ftp://example.com/x", path_dest=tmp_path / "out.bin")


def test_download_rejects_loopback_host(tmp_path: Path) -> None:
    """A loopback host is rejected by the SSRF guard."""
    with pytest.raises(ValueError, match="non-public address"):
        download_file("http://127.0.0.1/secret", path_dest=tmp_path / "out.bin")


def test_download_rejects_url_without_host(tmp_path: Path) -> None:
    """A URL with no host is rejected."""
    with pytest.raises(ValueError, match="without host"):
        download_file("http:///nohost", path_dest=tmp_path / "out.bin")


@pytest.mark.allow_network
def test_fetch_bytes_redirect_raises_runtimeerror_not_typeerror(str_redirect_url: str) -> None:
    """A 302 surfaces as the intended RuntimeError (non-retried), not a TypeChecker TypeError."""
    with pytest.raises(RuntimeError, match="redirect blocked"):
        _fetch_bytes(str_redirect_url, int_timeout_s=5)


def _http_error(int_code: int) -> error.HTTPError:
    """Build an ``HTTPError`` (an ``OSError`` subclass) carrying ``int_code``.

    Parameters
    ----------
    int_code : int
        The HTTP status.

    Returns
    -------
    urllib.error.HTTPError
        The error ``urlopen`` would raise.
    """
    return error.HTTPError("http://example.test/x", int_code, "boom", None, None)  # type: ignore[arg-type]


def _count_download_calls(
    *, mocker: MockerFixture, tmp_path: Path, exc_raised: OSError
) -> tuple[int, type[BaseException]]:
    """Run ``download_file`` against an opener that always raises ``exc_raised``.

    Parameters
    ----------
    mocker : pytest_mock.MockerFixture
        Patches the URL guard, the opener and the backoff sleep.
    tmp_path : pathlib.Path
        Destination directory.
    exc_raised : OSError
        What every ``open`` call raises.

    Returns
    -------
    tuple[int, type[BaseException]]
        ``open`` call count and the exception type that escaped.
    """
    mocker.patch("src.utils.http_downloader._assert_url_allowed")
    mocker.patch("time.sleep")
    mock_open = mocker.patch("src.utils.http_downloader._OPENER.open", side_effect=exc_raised)
    with pytest.raises(Exception) as cls_info:  # noqa: PT011 -- type is asserted by the caller
        download_file("http://example.test/x", path_dest=tmp_path / "out.bin")
    return mock_open.call_count, cls_info.type


@pytest.mark.parametrize("int_code", [301, 400, 401, 403, 404, 429])
def test_download_file_http_below_500_is_not_retried(
    *, mocker: MockerFixture, tmp_path: Path, int_code: int
) -> None:
    """An HTTP status below 500 fails on the first attempt."""
    int_calls, _ = _count_download_calls(
        mocker=mocker, tmp_path=tmp_path, exc_raised=_http_error(int_code)
    )
    assert int_calls == 1


def test_download_file_http_4xx_raises_runtimeerror(
    *, mocker: MockerFixture, tmp_path: Path
) -> None:
    """A 401 escapes as RuntimeError, not as a retryable OSError."""
    _, cls_type = _count_download_calls(
        mocker=mocker, tmp_path=tmp_path, exc_raised=_http_error(401)
    )
    assert cls_type is RuntimeError


@pytest.mark.parametrize("int_code", [500, 502, 503])
def test_download_file_http_5xx_is_retried(
    *, mocker: MockerFixture, tmp_path: Path, int_code: int
) -> None:
    """A 5xx is retried up to the attempt limit."""
    int_calls, _ = _count_download_calls(
        mocker=mocker, tmp_path=tmp_path, exc_raised=_http_error(int_code)
    )
    assert int_calls == 3


def test_download_file_timeout_is_retried(*, mocker: MockerFixture, tmp_path: Path) -> None:
    """A transient transport failure is retried up to the attempt limit."""
    int_calls, _ = _count_download_calls(
        mocker=mocker, tmp_path=tmp_path, exc_raised=error.URLError(TimeoutError("slow"))
    )
    assert int_calls == 3
