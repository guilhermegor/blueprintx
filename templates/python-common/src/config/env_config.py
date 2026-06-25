"""Env-wise config-file resolution (inputs/outputs selected by ``ENV``).

A pure, side-effect-free selector so the choice + its fail-loud behaviour is unit-testable
without importing ``startup`` (which builds singletons at import). Two modes, decided per
config kind by which files exist:

- **Plain (default):** a single ``<kind>.yaml`` (e.g. ``inputs.yaml``) ships and is always
  used — ``ENV`` does not affect file selection. This is the out-of-the-box behaviour.
- **Env-wise (opt-in):** delete the plain ``<kind>.yaml`` and ship ``<kind>_dev.yaml`` /
  ``<kind>_prd.yaml``. ``ENV`` then picks the suffix; an unknown/typo ``ENV`` or a missing
  file logs to stderr and aborts the process (``SystemExit`` 2) — never a silent default.

Deliberately decoupled from ``utils.typing`` so it stays portable across the
``chassis.typing`` (DDD) and ``utils.typing`` (MVC) layouts.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import TYPE_CHECKING, NoReturn


# The runtime type-checking engine is always injected, but at a layout-dependent path:
# utils.typing (MVC) or chassis.typing (DDD). mypy reads the single TYPE_CHECKING import
# (no redefinition); at runtime the try/except picks whichever layout shipped.
if TYPE_CHECKING:
	from utils.typing import type_checker
else:
	try:
		from utils.typing import type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from chassis.typing import type_checker


# Accepted ENV values -> config-file suffix (English + pt-BR + short forms). Anything else
# in env-wise mode is a typo and fails loud.
ENV_TO_SUFFIX: dict[str, str] = {
	"development": "dev",
	"desenvolvimento": "dev",
	"dev": "dev",
	"production": "prd",
	"producao": "prd",
	"prod": "prd",
	"prd": "prd",
}


@type_checker
def resolve_config_path(str_env: str, str_kind: str, path_dir: Path) -> Path:
	"""Resolve the config file for ``str_kind``, preferring the plain file when present.

	Plain mode (a ``<kind>.yaml`` exists) returns that file regardless of ``str_env``.
	Otherwise env-wise mode resolves ``<kind>_<suffix>.yaml`` for ``str_env`` and aborts
	loudly when ``str_env`` maps to no suffix or the resolved file is absent.

	Parameters
	----------
	str_env : str
		The environment name (``ENV``), already lower-cased.
	str_kind : str
		Config kind (``"inputs"`` / ``"outputs"``).
	path_dir : pathlib.Path
		Directory holding the config files.

	Returns
	-------
	pathlib.Path
		The resolved, existing config-file path.

	Raises
	------
	SystemExit
		In env-wise mode, when ``str_env`` maps to no known suffix or the resolved file is
		absent — after printing a clear error to stderr (exit code 2).
	"""
	path_plain = path_dir / f"{str_kind}.yaml"
	if path_plain.exists():
		return path_plain
	str_suffix = ENV_TO_SUFFIX.get(str_env)
	if str_suffix is None:
		_abort(f"invalid ENV {str_env!r}; expected one of: {sorted(set(ENV_TO_SUFFIX))}")
	path_cfg = path_dir / f"{str_kind}_{str_suffix}.yaml"
	if not path_cfg.exists():
		_abort(f"missing config file: {path_cfg}")
	return path_cfg


@type_checker
def _abort(str_reason: str) -> NoReturn:
	"""Print a startup error to stderr and abort the process (``SystemExit`` code 2).

	Parameters
	----------
	str_reason : str
		The reason shown to the operator.

	Raises
	------
	SystemExit
		Always (exit code 2).
	"""
	print(f"[startup][ERROR] {str_reason}", file=sys.stderr)
	raise SystemExit(2)
