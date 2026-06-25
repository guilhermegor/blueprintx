r"""OS-independent path resolution for configured locations.

A service may read inputs from Windows network drives (``A:\...``, ``E:\...``)
or UNC shares (``\\server\share\...``) declared in configuration. Those strings
carry backslash separators that :class:`pathlib.Path` would misread on POSIX, so
every configured path is funnelled through :func:`resolve_path`, which keeps
native Windows paths intact on Windows and degrades gracefully elsewhere (tests,
CI on Linux) by interpreting them as pure paths.

All filesystem manipulation should go through ``pathlib`` — never raw string
concatenation with ``os.sep``.
"""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path, PureWindowsPath
import shutil
from typing import TYPE_CHECKING


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). mypy reads the single TYPE_CHECKING
# import (no redefinition); at runtime the try/except picks whichever layout shipped.
if TYPE_CHECKING:
	from utils.typing import type_checker
else:
	try:
		from utils.typing import type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from chassis.typing import type_checker


# pt-BR month names (index 1..12), accent-folded to match folder names on disk
# (``abril-2026``). Folders are created without accents, so ``marco`` not ``março``.
_MONTHS_PT: tuple[str, ...] = (
	"",
	"janeiro",
	"fevereiro",
	"marco",
	"abril",
	"maio",
	"junho",
	"julho",
	"agosto",
	"setembro",
	"outubro",
	"novembro",
	"dezembro",
)
_MONTHS_PT_ABBR: tuple[str, ...] = (
	"",
	"Jan",
	"Fev",
	"Mar",
	"Abr",
	"Mai",
	"Jun",
	"Jul",
	"Ago",
	"Set",
	"Out",
	"Nov",
	"Dez",
)


@type_checker
def is_windows_path(str_path: str) -> bool:
	r"""Return whether ``str_path`` looks like a Windows drive or UNC path.

	Parameters
	----------
	str_path : str
		Candidate path string.

	Returns
	-------
	bool
		``True`` for ``X:\...`` drive paths or ``\\server\share`` UNC paths.
	"""
	str_stripped = str_path.strip()
	if len(str_stripped) >= 2 and str_stripped[1] == ":" and str_stripped[0].isalpha():
		return True
	return str_stripped.startswith("\\\\")


@type_checker
def resolve_path(str_path: str) -> Path:
	"""Resolve a configured path string to a :class:`pathlib.Path`.

	On Windows, Windows-style paths resolve to a native ``Path``. On POSIX, a
	Windows-style path is wrapped in :class:`pathlib.PureWindowsPath` first so its
	parts are parsed correctly even though it is not reachable locally; POSIX paths
	expand ``~`` as usual.

	Parameters
	----------
	str_path : str
		Path string from configuration (drive, UNC, POSIX, or ``~``-prefixed).

	Returns
	-------
	pathlib.Path
		A path object suitable for the host OS.
	"""
	str_stripped = str_path.strip()
	if is_windows_path(str_stripped):
		if os.name == "nt":
			return Path(str_stripped)
		return Path(PureWindowsPath(str_stripped))
	return Path(str_stripped).expanduser()


@type_checker
def ensure_dir(path_dir: Path) -> Path:
	"""Create ``path_dir`` (and parents) if absent and return it.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory to ensure exists.

	Returns
	-------
	pathlib.Path
		The same directory path.
	"""
	path_dir.mkdir(parents=True, exist_ok=True)
	return path_dir


@type_checker
def copy_into(path_src: Path, path_dir: Path, str_stamp: str | None = None) -> Path:
	"""Copy ``path_src`` into ``path_dir`` (created if absent), returning the destination.

	Use to archive every input a run reads into its output subfolder, so each run's folder is
	a complete, self-contained record of its inputs. Metadata is preserved (``shutil.copy2``).
	When ``str_stamp`` is given the destination stem is suffixed ``<stem>_<str_stamp><ext>`` so
	re-running never overwrites a prior copy; without a stamp the original name is kept.

	Parameters
	----------
	path_src : pathlib.Path
		The source file to copy.
	path_dir : pathlib.Path
		Destination directory.
	str_stamp : str | None
		Optional stamp suffix appended to the stem.

	Returns
	-------
	pathlib.Path
		The copied file's path.

	Raises
	------
	FileNotFoundError
		If ``path_src`` does not exist.
	"""
	if not path_src.exists():
		raise FileNotFoundError(f"Input not found for copy: {path_src}")
	path_dir.mkdir(parents=True, exist_ok=True)
	str_name = f"{path_src.stem}_{str_stamp}{path_src.suffix}" if str_stamp else path_src.name
	path_dest = path_dir / str_name
	shutil.copy2(path_src, path_dest)
	return path_dest


@type_checker
def date_tokens(dt_ref: date) -> dict[str, str]:
	r"""Build the date-token substitution map for a reference date.

	Input locations often change every period — the folder is named after the reference date
	(``abril-2026``, ``2026-04-30``). Instead of hard-coding a dated path, configuration
	declares templates with these tokens, filled here.

	==================  ==============================
	Token               Example (ref 2026-04-30)
	==================  ==============================
	``{year}``          ``2026``
	``{month}``         ``04``
	``{day}``           ``30``
	``{date}``          ``2026-04-30``
	``{ym}``            ``202604``
	``{ymd}``           ``20260430``
	``{month_pt}``      ``abril``
	``{month_pt_abbr}`` ``Abr``
	==================  ==============================

	Parameters
	----------
	dt_ref : datetime.date
		Reference date.

	Returns
	-------
	dict
		Token name to value.
	"""
	return {
		"year": f"{dt_ref.year:04d}",
		"month": f"{dt_ref.month:02d}",
		"day": f"{dt_ref.day:02d}",
		"date": dt_ref.strftime("%Y-%m-%d"),
		"ym": dt_ref.strftime("%Y%m"),
		"ymd": dt_ref.strftime("%Y%m%d"),
		"month_pt": _MONTHS_PT[dt_ref.month],
		"month_pt_abbr": _MONTHS_PT_ABBR[dt_ref.month],
	}


@type_checker
def resolve_input(spec: str | dict[str, str] | None, dt_ref: date) -> Path | None:
	"""Resolve an input spec to an existing absolute file path for the reference date.

	A configured input is either a plain path string, or a mapping ``{dir, filename_pattern}``
	where ``dir`` is a date-token template (see :func:`date_tokens`) and ``filename_pattern`` a
	glob. For a mapping the newest file (by modification time) matching the glob
	case-insensitively is chosen. The result is always absolute, so a consumer that does not
	share the process working directory (e.g. an external tool) can open it.

	Parameters
	----------
	spec : str or dict of {str: str} or None
		A plain path string, or a ``{dir, filename_pattern}`` mapping.
	dt_ref : datetime.date
		Reference date used to fill the templates.

	Returns
	-------
	pathlib.Path or None
		The resolved file, or ``None`` when nothing matches.
	"""
	dict_tokens = date_tokens(dt_ref)
	if isinstance(spec, dict):
		str_dir = str(spec.get("dir", "")).format(**dict_tokens)
		str_pattern = str(spec.get("filename_pattern", "*")).format(**dict_tokens)
		path_match = _latest_match(resolve_path(str_dir), str_pattern)
		return _to_absolute(path_match) if path_match is not None else None
	str_path = str(spec or "").format(**dict_tokens)
	if not str_path.strip():
		return None
	path_resolved = resolve_path(str_path)
	return _to_absolute(path_resolved) if path_resolved.exists() else None


@type_checker
def resolve_input_glob(spec: dict[str, str] | None, dt_ref: date) -> list[Path]:
	"""Resolve a ``{dir, filename_pattern}`` spec to **all** matching files for the date.

	Like :func:`resolve_input` but returns every case-insensitive match (sorted by name)
	instead of only the newest — for inputs that are one-file-per-entity at the same date.

	Parameters
	----------
	spec : dict of {str: str} or None
		A ``{dir, filename_pattern}`` mapping (date-token templates), or ``None``.
	dt_ref : datetime.date
		Reference date used to fill the templates.

	Returns
	-------
	list of pathlib.Path
		Every matching file (empty when the spec is ``None`` or nothing matches).
	"""
	if not isinstance(spec, dict):
		return []
	dict_tokens = date_tokens(dt_ref)
	str_dir = str(spec.get("dir", "")).format(**dict_tokens)
	str_pattern = str(spec.get("filename_pattern", "*")).format(**dict_tokens).casefold()
	path_dir = resolve_path(str_dir)
	if not path_dir.exists():
		return []
	return sorted(
		_to_absolute(path)
		for path in path_dir.iterdir()
		if path.is_file() and Path(path.name.casefold()).match(str_pattern)
	)


@type_checker
def _to_absolute(path_resolved: Path) -> Path:
	"""Return a resolved input path made absolute so external tools can open it.

	A relative resolved path satisfies Python's CWD-anchored :meth:`~pathlib.Path.exists`, but
	breaks any consumer that does not share the process working directory. Absolute paths
	resolve identically everywhere; an already-absolute path is returned unchanged.

	Parameters
	----------
	path_resolved : pathlib.Path
		The resolved input path.

	Returns
	-------
	pathlib.Path
		The absolute path.
	"""
	return path_resolved if path_resolved.is_absolute() else path_resolved.resolve()


@type_checker
def _latest_match(path_dir: Path, str_pattern: str) -> Path | None:
	"""Return the newest file in ``path_dir`` matching ``str_pattern`` (case-insensitive).

	Parameters
	----------
	path_dir : pathlib.Path
		Directory to search.
	str_pattern : str
		Glob pattern, matched case-insensitively against file names.

	Returns
	-------
	pathlib.Path or None
		The most recently modified matching file, or ``None``.
	"""
	if not path_dir.exists():
		return None
	str_pattern_low = str_pattern.casefold()
	list_matches = [
		path
		for path in path_dir.iterdir()
		if path.is_file() and Path(path.name.casefold()).match(str_pattern_low)
	]
	if not list_matches:
		return None
	return max(list_matches, key=lambda p: p.stat().st_mtime)
