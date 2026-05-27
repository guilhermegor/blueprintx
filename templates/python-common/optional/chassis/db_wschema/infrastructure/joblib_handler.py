"""Joblib-based binary artifact store with three-factor integrity verification."""

from __future__ import annotations

import hashlib
import hmac
import io
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import joblib

from chassis.db.domain.ports import DatabaseHandler, Record


_TS_FMT = "%Y%m%d_%H%M%S"


class JoblibHandler(DatabaseHandler):
	"""Immutable binary artifact store backed by joblib with integrity verification.

	Each artifact is stored as a single file named
	``{name}_{YYYYMMDD_HHMMSS}_{sha256_prefix8}.joblib``.

	**Three-factor integrity check on every load:**

	1. SHA256 prefix in filename — first 8 hex chars of SHA256(bytes) must match the
	   suffix embedded in the filename.
	2. ``_saved_at`` metadata — the ``_saved_at`` field injected at save time must match
	   the timestamp segment of the filename.
	3. HMAC sidecar (optional) — when ``secret_key`` is set, a ``.sig`` sidecar is written
	   and verified on load; protects against an adversary who controls the filesystem.

	``update()`` is intentionally not supported — artifacts are immutable. Save a new
	version by calling ``create()`` again.

	Parameters
	----------
	dir_path : str or Path
		Directory where artifact files are stored.
	compress : tuple of (str, int), optional
		Joblib compression codec and level, by default ``("lz4", 3)``.
	secret_key : bytes or None, optional
		Key for HMAC-SHA256 signing. When ``None`` only SHA256 + metadata checks run.
	"""

	def __init__(
		self,
		dir_path: str | Path,
		compress: tuple[str, int] = ("lz4", 3),
		secret_key: bytes | None = None,
	) -> None:
		self._dir = Path(dir_path)
		self._dir.mkdir(parents=True, exist_ok=True)
		self._compress = compress
		self._key = secret_key

	def create(self, record: Record) -> str:
		"""Persist a new artifact and return its unique identifier.

		The record may contain a ``"_name"`` key (kebab-case, no underscores) to make
		the filename human-readable. A UUID hex is used when ``"_name"`` is absent.

		Parameters
		----------
		record : Record
			Data to persist. ``_saved_at`` is injected automatically.

		Returns
		-------
		str
			Artifact identifier of the form ``{name}_{YYYYMMDD_HHMMSS}_{sha256_prefix8}``.
		"""

		str_name = str(record.get("_name", uuid.uuid4().hex)).replace("_", "-")
		str_ts = datetime.utcnow().strftime(_TS_FMT)
		dict_record = {**record, "_saved_at": str_ts}
		bytes_data = self._to_bytes(dict_record)
		str_sha256 = hashlib.sha256(bytes_data).hexdigest()[:8]
		str_record_id = f"{str_name}_{str_ts}_{str_sha256}"
		(self._dir / f"{str_record_id}.joblib").write_bytes(bytes_data)
		if self._key:
			bytes_sig = hmac.new(self._key, bytes_data, hashlib.sha256).digest()
			(self._dir / f"{str_record_id}.sig").write_bytes(bytes_sig)
		return str_record_id

	def read(self, record_id: str) -> Optional[Record]:
		"""Load and verify an artifact by its identifier.

		Parameters
		----------
		record_id : str
			Identifier returned by ``create()``.

		Returns
		-------
		Record or None
			Loaded artifact when found and all integrity checks pass.

		Raises
		------
		ValueError
			If any integrity factor fails.
		"""

		path_artifact = self._dir / f"{record_id}.joblib"
		if not path_artifact.exists():
			return None
		bytes_data = path_artifact.read_bytes()
		self._verify(record_id, bytes_data)
		buf = io.BytesIO(bytes_data)
		return joblib.load(buf)  # noqa: S301

	def update(self, record_id: str, updates: Record) -> Optional[Record]:
		"""Not supported — artifacts are immutable.

		Raises
		------
		NotImplementedError
			Always. Call ``create()`` to save a new version.
		"""

		raise NotImplementedError(
			"JoblibHandler stores immutable artifacts — call create() to save a new version"
		)

	def delete(self, record_id: str) -> bool:
		"""Remove an artifact and its optional signature sidecar.

		Parameters
		----------
		record_id : str
			Identifier of the artifact to remove.

		Returns
		-------
		bool
			``True`` when the artifact existed and was removed.
		"""

		path_artifact = self._dir / f"{record_id}.joblib"
		if not path_artifact.exists():
			return False
		path_artifact.unlink()
		path_sig = self._dir / f"{record_id}.sig"
		if path_sig.exists():
			path_sig.unlink()
		return True

	def backup(self, target_path: str | Path) -> Path:
		"""Copy the entire artifact directory to a new location.

		Parameters
		----------
		target_path : str or Path
			Destination directory.

		Returns
		-------
		Path
			Path to the created backup directory.
		"""

		path_target = Path(target_path)
		shutil.copytree(str(self._dir), str(path_target), dirs_exist_ok=True)
		return path_target

	def close(self) -> None:
		"""No-op for file-based storage."""

		return None

	def list_all(self) -> list[str]:
		"""Return identifiers for all artifacts in the store.

		Returns
		-------
		list of str
			Artifact identifiers (filenames without the ``.joblib`` extension).
		"""

		return [path_f.stem for path_f in sorted(self._dir.glob("*.joblib"))]

	def _to_bytes(self, record: Record) -> bytes:
		"""Serialize a record to compressed joblib bytes.

		Parameters
		----------
		record : Record
			Data to serialize.

		Returns
		-------
		bytes
			Compressed serialized bytes.
		"""

		buf = io.BytesIO()
		joblib.dump(record, buf, compress=self._compress)
		return buf.getvalue()

	def _verify(self, record_id: str, bytes_data: bytes) -> None:
		"""Run all three integrity checks and raise on the first failure.

		Parameters
		----------
		record_id : str
			Artifact identifier, used to extract expected hash and timestamp.
		bytes_data : bytes
			Raw bytes read from the artifact file.

		Raises
		------
		ValueError
			If record_id format is invalid, SHA256 prefix mismatches,
			``_saved_at`` metadata mismatches, or HMAC verification fails.
		"""

		list_parts = record_id.rsplit("_", 3)
		if len(list_parts) != 4:
			raise ValueError(f"Invalid record_id format: {record_id!r}")
		str_sha256_expected = list_parts[-1]
		str_sha256_actual = hashlib.sha256(bytes_data).hexdigest()[:8]
		if str_sha256_expected != str_sha256_actual:
			raise ValueError(
				f"SHA256 prefix mismatch for {record_id!r} — file may be corrupted or substituted"
			)
		if self._key:
			path_sig = self._dir / f"{record_id}.sig"
			if not path_sig.exists():
				raise ValueError(f"HMAC signature missing for {record_id!r}")
			bytes_sig_stored = path_sig.read_bytes()
			bytes_sig_actual = hmac.new(self._key, bytes_data, hashlib.sha256).digest()
			if not hmac.compare_digest(bytes_sig_stored, bytes_sig_actual):
				raise ValueError(f"HMAC verification failed for {record_id!r} — file may be tampered")
		buf = io.BytesIO(bytes_data)
		dict_record = joblib.load(buf)  # noqa: S301
		str_ts_expected = f"{list_parts[-3]}_{list_parts[-2]}"
		if dict_record.get("_saved_at") != str_ts_expected:
			raise ValueError(
				f"_saved_at metadata mismatch for {record_id!r} — content may be tampered"
			)
