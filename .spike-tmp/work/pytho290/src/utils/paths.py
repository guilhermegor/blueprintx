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


# A drive-letter prefix is exactly two characters, such as C-colon. Named so the length test
# reads as "is there room for a drive letter?" rather than as an arbitrary bound.
_INT_DRIVE_PREFIX_LEN = 2


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
	if (
		len(str_stripped) >= _INT_DRIVE_PREFIX_LEN
		and str_stripped[1] == ":"
		and str_stripped[0].isalpha()
	):
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
	if not is_windows_path(str_stripped):
		return Path(str_stripped).expanduser()
	# On Windows the string is already native; elsewhere it is parsed through PureWindowsPath
	# so its parts come out right even though the path is not reachable locally.
	return Path(str_stripped) if os.name == "nt" else Path(PureWindowsPath(str_stripped))


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
	# Two genuinely different resolutions behind one name, so each gets its own function and
	# this one only chooses. The mapping form searches a directory; the string form names a
	# file outright.
	if isinstance(spec, dict):
		return _resolve_mapping_spec(spec, dict_tokens)
	return _resolve_plain_spec(str(spec or ""), dict_tokens)


@type_checker
def _resolve_mapping_spec(dict_spec: dict[str, str], dict_tokens: dict) -> Path | None:
	"""Resolve a ``{dir, filename_pattern}`` spec to the newest matching file.

	Parameters
	----------
	dict_spec : dict of {str: str}
		The mapping form of an input spec.
	dict_tokens : dict
		Date tokens used to fill the templates.

	Returns
	-------
	pathlib.Path or None
		The newest match as an absolute path, or ``None``.
	"""
	str_dir = str(dict_spec.get("dir", "")).format(**dict_tokens)
	str_pattern = str(dict_spec.get("filename_pattern", "*")).format(**dict_tokens)
	path_match = _latest_match(resolve_path(str_dir), str_pattern)
	return to_absolute(path_match) if path_match is not None else None


@type_checker
def _resolve_plain_spec(str_spec: str, dict_tokens: dict) -> Path | None:
	"""Resolve a plain path-string spec to an existing absolute file.

	Parameters
	----------
	str_spec : str
		The string form of an input spec (may be empty).
	dict_tokens : dict
		Date tokens used to fill the template.

	Returns
	-------
	pathlib.Path or None
		The resolved file as an absolute path, or ``None`` when blank or absent.
	"""
	str_path = str_spec.format(**dict_tokens)
	if not str_path.strip():
		return None
	path_resolved = resolve_path(str_path)
	return to_absolute(path_resolved) if path_resolved.exists() else None


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
	str_pattern = str(spec.get("filename_pattern", "*")).format(**dict_tokens)
	list_matches = _matching_files(resolve_path(str_dir), str_pattern)
	return sorted(to_absolute(path) for path in list_matches)


@type_checker
def to_absolute(path_resolved: Path) -> Path:
	r"""Return a path made absolute so a **foreign process** resolves it the way we do.

	Call this at every boundary a path leaves this process — attachment argv, a COM
	``SaveAsFile`` destination, subprocess arguments. It is not an input rule: the recurrences
	were *outputs*, and both mechanisms are invisible to an :meth:`~pathlib.Path.exists` guard
	because that guard runs in **our** process.

	**CWD-relative** — a relative path satisfies Python's CWD-anchored ``exists()`` and then
	breaks any consumer that does not share our working directory.

	**Drive-relative (Windows)** — a POSIX-shaped configured value such as ``/home/x/out``
	renders ``\\home\\x\\out``: rooted but **driveless**, so ``is_absolute()`` is ``False`` and
	it anchors to whichever drive the *reading* process sits on. Resolving here anchors it to
	ours instead, which is the only drive both sides agree on.

	An already-absolute path is returned unchanged.

	Parameters
	----------
	path_resolved : pathlib.Path
		The path to hand off.

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
	# The default keyword carries the empty case, so no second guard is needed for it.
	return max(
		_matching_files(path_dir, str_pattern),
		key=lambda path: path.stat().st_mtime,
		default=None,
	)


@type_checker
def _matching_files(path_dir: Path, str_pattern: str) -> list[Path]:
	"""Return every file in ``path_dir`` whose name matches ``str_pattern``, case-insensitively.

	The one place the case-insensitive scan lives. It was written twice — once to pick the
	newest match and once to return them all — which is two chances for the matching rule to
	drift apart while both callers keep passing their own tests.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory to search; a missing directory yields an empty list rather than raising.
	str_pattern : str
		Glob pattern, matched case-insensitively against file names.

	Returns
	-------
	list of pathlib.Path
		Matching files, in directory order.
	"""
	if not path_dir.exists():
		return []
	str_pattern_low = str_pattern.casefold()
	return [
		path
		for path in path_dir.iterdir()
		if path.is_file() and Path(path.name.casefold()).match(str_pattern_low)
	]
