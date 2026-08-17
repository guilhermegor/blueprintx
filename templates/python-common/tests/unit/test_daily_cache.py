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
	list_calls: list[str] = []

	def fn_download(str_url: str, path_dest: Path) -> Path:
		list_calls.append(str_url)
		path_dest.write_bytes(bytes_payload)
		return path_dest

	return fn_download, list_calls


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

	def fn_call() -> None:
		download_daily(
			"https://example.com/a.csv",
			tmp_path,
			"src",
			date(2026, 8, 17),
			".csv",
			fn_download=fn_download,
		)

	fn_call()  # miss — downloads
	fn_call()  # same reference day — must NOT download again
	assert len(list_calls) == 1


def test_download_daily_refetches_for_a_different_reference_date(tmp_path: Path) -> None:
	"""A new reference day is a different file, so it downloads again."""
	fn_download, list_calls = _fake_download()
	for dt_day in (date(2026, 8, 17), date(2026, 8, 18)):
		download_daily(
			"https://example.com/a.csv",
			tmp_path,
			"src",
			dt_day,
			".csv",
			fn_download=fn_download,
		)
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

	def fn_download(str_url: str, path_dest: Path) -> Path:
		path_dest.write_bytes(b"half a fi")  # non-empty, and wrong
		raise OSError("connection dropped mid-transfer")

	path_cached = daily_cache_path(tmp_path, "src", date(2026, 8, 17), ".csv")
	with pytest.raises(OSError, match="connection dropped"):
		download_daily(
			"https://example.com/a.csv",
			tmp_path,
			"src",
			date(2026, 8, 17),
			".csv",
			fn_download=fn_download,
		)
	assert not path_cached.exists()
	assert list(tmp_path.glob("*.part")) == []


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

	def fn_call() -> None:
		download_daily(
			"https://example.com/a.csv",
			tmp_path,
			"src",
			date(2026, 8, 17),
			".csv",
			cls_logger=cls_emitter,
			fn_download=fn_download,
		)

	fn_call()  # miss
	fn_call()  # hit
	assert list_calls == ["https://example.com/a.csv"]
	assert "miss" in cls_emitter.list_messages[0]
	assert "HIT" in cls_emitter.list_messages[1]


def test_drift_driver_does_not_use_the_daily_cache() -> None:
	"""The drift job must never read through this cache.

	A cached read cannot detect drift, and a partially-populated cache is reported *as* drift.
	The driver downloads into a temp dir instead — this asserts that stays true, because it is
	currently correct **by accident** (nobody wired the cache in) and an accident is one
	convenient import away from reversing.
	"""
	path_driver = Path(__file__).resolve().parents[2] / "bin" / "check_contract_drift.py"
	if not path_driver.is_file():
		pytest.skip("drift driver ships to service tiers only")
	str_source = path_driver.read_text(encoding="utf-8")
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
