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

import os
from pathlib import Path, PureWindowsPath


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
