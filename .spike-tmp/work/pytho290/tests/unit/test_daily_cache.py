"""Unit tests for the daily on-disk vendor cache."""

from datetime import date, datetime
from pathlib import Path

import pytest

from src.utils.daily_cache import daily_cache_path, download_daily

# ⚠️ `utils.retry`, NOT `src.utils.retry`. `pytest.ini` puts both `.` and `src` on the path, so
# the same file is importable under two names and Python loads it TWICE — two distinct class
# objects. `daily_cache` resolves its annotation against `utils.retry` (the shipped convention
# for every module in this kit), so a subclass of `src.utils.retry.LogEmitter` is a different
# class and the nominal runtime check rejects it. The two names are interchangeable until a
# CLASS crosses between them; then they are not.
from utils.retry import LogEmitter


class _RecordingEmitter(LogEmitter):
	"""Emitter that keeps every line, so a test can assert WHICH branch ran.

	Subclasses :class:`LogEmitter` rather than duck-typing it: the runtime checker enforces
	NOMINAL types, so a structurally-identical stand-in is rejected at the call boundary.
	Injecting a subclass is the documented seam in ``utils/retry.py``.
	"""

	def __init__(self) -> None:
		super().__init__()
		self.list_messages: list[str] = []

	def log_message(self, str_message: str, str_level: str) -> None:
		"""Record one line.

		Parameters
		----------
		str_message : str
			The message.
		str_level : str
			The level name (unused here).
		"""
		self.list_messages.append(str_message)


class _DownloadRecorder:
	"""Callable download stub that records the URLs it was asked to fetch.

	⚠️ A class at module level rather than a ``def`` nested inside each test. mccabe adds 1
	to the enclosing function for every nested ``def``, and ``tests/`` is capped at
	complexity 1 (``bin/check_complexity.sh``) — so an inline stub, which contains no
	branching whatsoever, would spend the entire budget the cap exists to reserve FOR
	branching. A lambda costs 0 but cannot record state; a class costs the enclosing test
	nothing and each of its methods is measured on its own.
	"""

	def __init__(self, bytes_payload: bytes = b"payload") -> None:
		self.bytes_payload = bytes_payload
		self.list_calls: list[str] = []

	def __call__(self, str_url: str, path_dest: Path) -> Path:
		"""Record the URL and write the payload.

		Parameters
		----------
		str_url : str
			The URL requested.
		path_dest : pathlib.Path
			Where to write.

		Returns
		-------
		pathlib.Path
			``path_dest``, as the real downloader does.
		"""
		self.list_calls.append(str_url)
		path_dest.write_bytes(self.bytes_payload)
		return path_dest


def _download_that_dies_midway(str_url: str, path_dest: Path) -> Path:
	"""Write a truncated artifact, then fail — the partial-write case.

	Parameters
	----------
	str_url : str
		Unused; present to satisfy the downloader signature.
	path_dest : pathlib.Path
		Where the partial bytes land.

	Returns
	-------
	pathlib.Path
		Never returns; always raises.

	Raises
	------
	OSError
		Always, simulating a transfer dropped mid-write.
	"""
	path_dest.write_bytes(b"half a fi")  # non-empty, and wrong
	raise OSError("connection dropped mid-transfer")


def _download_that_writes_nothing(str_url: str, path_dest: Path) -> Path:
	"""Write a zero-byte artifact and return normally.

	Parameters
	----------
	str_url : str
		Unused; present to satisfy the downloader signature.
	path_dest : pathlib.Path
		Where the empty file lands.

	Returns
	-------
	pathlib.Path
		``path_dest``.
	"""
	path_dest.write_bytes(b"")
	return path_dest


def _call_download(
	path_root: Path,
	fn_download: object,
	dt_day: date = date(2026, 8, 17),
	cls_logger: LogEmitter | None = None,
) -> Path:
	"""Invoke ``download_daily`` with this module's fixed fixture arguments.

	Parameters
	----------
	path_root : pathlib.Path
		Cache root.
	fn_download : object
		The download stub to inject.
	dt_day : datetime.date, optional
		Reference day, by default 2026-08-17.
	cls_logger : LogEmitter or None, optional
		Logger to inject, by default ``None``.

	Returns
	-------
	pathlib.Path
		The cached artifact's path.
	"""
	return download_daily(
		"https://example.com/a.csv",
		path_root,
		"src",
		dt_day,
		".csv",
		cls_logger=cls_logger,
		fn_download=fn_download,
	)


def _fake_download(bytes_payload: bytes = b"payload") -> tuple:
	"""Build a download stub plus the list recording its calls.

	Parameters
	----------
	bytes_payload : bytes, optional
		Bytes to write, by default ``b"payload"``.

	Returns
	-------
	tuple
		``(fn_download, list_calls)``.
	"""
	cls_recorder = _DownloadRecorder(bytes_payload)
	return cls_recorder, cls_recorder.list_calls


def test_daily_cache_path_keys_on_the_reference_date(tmp_path: Path) -> None:
	"""The filename carries the data's reference day, with no time component."""
	path_out = daily_cache_path(tmp_path, "cvm-register", date(2026, 8, 17), ".csv")
	assert path_out.name == "cvm-register_20260817.csv"


def test_download_daily_fetches_on_a_miss(tmp_path: Path) -> None:
	"""A first call with no cached file downloads and writes it."""
	fn_download, list_calls = _fake_download()
	path_out = download_daily(
		"https://example.com/a.csv",
		tmp_path / "cache",
		"src",
		date(2026, 8, 17),
		".csv",
		fn_download=fn_download,
	)
	assert list_calls == ["https://example.com/a.csv"]
	assert path_out.read_bytes() == b"payload"


def test_download_daily_reuses_the_file_on_a_second_call(tmp_path: Path) -> None:
	"""The second call for the same reference day does not hit the network."""
	fn_download, list_calls = _fake_download()
	_call_download(tmp_path, fn_download)  # miss — downloads
	_call_download(tmp_path, fn_download)  # same reference day — must NOT download again
	assert len(list_calls) == 1


def test_download_daily_refetches_for_a_different_reference_date(tmp_path: Path) -> None:
	"""A new reference day is a different file, so it downloads again."""
	fn_download, list_calls = _fake_download()
	_call_download(tmp_path, fn_download, date(2026, 8, 17))
	_call_download(tmp_path, fn_download, date(2026, 8, 18))
	assert len(list_calls) == 2


def test_download_daily_bypasses_the_read_when_caching_is_off(tmp_path: Path) -> None:
	"""``bool_use_cache=False`` fetches even though a cached file exists.

	This is the drift job's posture: a cached read cannot detect drift, so the switch must be
	the caller's to set, not an ambient default the client decides.
	"""
	fn_download, list_calls = _fake_download()
	download_daily(
		"https://example.com/a.csv",
		tmp_path,
		"src",
		date(2026, 8, 17),
		".csv",
		fn_download=fn_download,
	)
	download_daily(
		"https://example.com/a.csv",
		tmp_path,
		"src",
		date(2026, 8, 17),
		".csv",
		bool_use_cache=False,
		fn_download=fn_download,
	)
	assert len(list_calls) == 2


def test_download_daily_treats_a_zero_byte_file_as_a_miss(tmp_path: Path) -> None:
	"""An empty cached file is refetched, not served."""
	# `write_bytes` is not atomic, so an interrupted run can leave an empty file. Serving it
	# hands the caller a valid-looking path to nothing, which fails much later and far away.
	path_cached = daily_cache_path(tmp_path, "src", date(2026, 8, 17), ".csv")
	path_cached.parent.mkdir(parents=True, exist_ok=True)
	path_cached.write_bytes(b"")
	fn_download, list_calls = _fake_download()
	download_daily(
		"https://example.com/a.csv",
		tmp_path,
		"src",
		date(2026, 8, 17),
		".csv",
		fn_download=fn_download,
	)
	assert len(list_calls) == 1


def test_a_failed_download_never_publishes_a_partial_file(tmp_path: Path) -> None:
	"""A download that dies mid-write leaves NO cache file behind.

	The zero-byte guard only catches the empty case. A *truncated non-empty* artifact would be
	served as a hit and reach the parser, so the file must become visible under its final name
	only after the download completed — and the staging file must not linger either, or the
	cache directory fills with debris nobody ever reads.
	"""
	path_cached = daily_cache_path(tmp_path, "src", date(2026, 8, 17), ".csv")
	with pytest.raises(OSError, match="connection dropped"):
		_call_download(tmp_path, _download_that_dies_midway)
	assert not path_cached.exists()
	assert list(tmp_path.glob("*.part")) == []


def test_an_empty_download_does_not_replace_a_good_cache_entry(tmp_path: Path) -> None:
	"""A zero-byte download raises instead of publishing over a valid file.

	Publishing it would contradict the module's own zero-byte-as-miss contract: the next call
	would treat the empty file as a miss and refetch, but this call already returned its path
	to a caller who is about to parse nothing.
	"""
	path_cached = daily_cache_path(tmp_path, "src", date(2026, 8, 17), ".csv")
	path_cached.parent.mkdir(parents=True, exist_ok=True)
	path_cached.write_bytes(b"good bytes")

	with pytest.raises(OSError, match="empty artifact"):
		download_daily(
			"https://example.com/a.csv",
			tmp_path,
			"src",
			date(2026, 8, 17),
			".csv",
			bool_use_cache=False,
			fn_download=_download_that_writes_nothing,
		)
	assert path_cached.read_bytes() == b"good bytes"


def test_download_daily_creates_the_cache_directory(tmp_path: Path) -> None:
	"""The parent tree is created rather than assumed."""
	fn_download, _ = _fake_download()
	path_dir = tmp_path / "a" / "b"
	download_daily(
		"https://example.com/a.csv",
		path_dir,
		"src",
		date(2026, 8, 17),
		".csv",
		fn_download=fn_download,
	)
	assert path_dir.is_dir()


def test_download_daily_logs_which_branch_ran(tmp_path: Path) -> None:
	"""Hit and miss are distinguishable in the log."""
	# A cache silent about hit-vs-network cannot be told from one that never engaged, and
	# "why is this data stale?" becomes unanswerable from the log alone.
	cls_emitter = _RecordingEmitter()
	fn_download, list_calls = _fake_download()

	_call_download(tmp_path, fn_download, cls_logger=cls_emitter)  # miss
	_call_download(tmp_path, fn_download, cls_logger=cls_emitter)  # hit
	assert list_calls == ["https://example.com/a.csv"]
	assert "miss" in cls_emitter.list_messages[0]
	assert "HIT" in cls_emitter.list_messages[1]


_PATH_DRIFT_DRIVER = Path(__file__).resolve().parents[2] / "bin" / "check_contract_drift.py"


# ⚠️ A decorator, not `if not …: pytest.skip(...)` inside the body. The condition is fixed at
# import time (does this tier ship the driver?), so it is not a path THROUGH the test — but an
# `if` in the body makes it one, both to a reader and to mccabe, and tests/ is capped at 1.
@pytest.mark.skipif(
	not _PATH_DRIFT_DRIVER.is_file(), reason="drift driver ships to service tiers only"
)
def test_drift_driver_does_not_use_the_daily_cache() -> None:
	"""The drift job must never read through this cache.

	A cached read cannot detect drift, and a partially-populated cache is reported *as* drift.
	The driver downloads into a temp dir instead — this asserts that stays true, because it is
	currently correct **by accident** (nobody wired the cache in) and an accident is one
	convenient import away from reversing.
	"""
	str_source = _PATH_DRIFT_DRIVER.read_text(encoding="utf-8")
	assert "daily_cache" not in str_source
	assert "download_daily" not in str_source


def test_download_daily_rejects_a_datetime_as_the_reference_date(tmp_path: Path) -> None:
	"""A wall-clock ``datetime`` is refused even though it IS a ``date``.

	``datetime`` subclasses ``date``, so the annotation alone accepts ``datetime.now()`` and it
	even formats into a plausible filename — the exact wall-clock key the module exists to
	prevent, with nothing downstream to complain. Only an explicit guard catches it, so only an
	explicit test proves the guard is there.
	"""
	fn_download, _ = _fake_download()
	with pytest.raises(TypeError):
		download_daily(
			"https://example.com/a.csv",
			tmp_path,
			"src",
			datetime(2026, 8, 17),  # type: ignore[arg-type]
			".csv",
			fn_download=fn_download,
		)


def test_download_daily_rejects_a_string_reference_date(tmp_path: Path) -> None:
	"""A string is refused at the seam by the runtime checker."""
	fn_download, _ = _fake_download()
	with pytest.raises(TypeError):
		download_daily(
			"https://example.com/a.csv",
			tmp_path,
			"src",
			"2026-08-17",  # type: ignore[arg-type]
			".csv",
			fn_download=fn_download,
		)
