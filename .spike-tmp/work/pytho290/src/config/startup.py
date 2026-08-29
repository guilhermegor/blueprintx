"""Startup: logger and runtime constants.

All module-level names are initialised once at import time. Import this module
early (before any feature code) so every consumer shares the same instances.
"""

from datetime import datetime
from getpass import getuser
import os
from pathlib import Path
from socket import gethostname
import sys
import tempfile
from typing import TYPE_CHECKING

from dotenv import load_dotenv
import yaml

from config.env_config import resolve_config_path
from utils.logs import CreateLog
from utils.paths import is_windows_path


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


load_dotenv(override=True)

cls_create_log = CreateLog()

_CONFIG_DIR = Path(__file__).parent

USER: str = getuser()
HOSTNAME: str = gethostname()
ENVIRONMENT: str = os.getenv("ENV", "development").lower()
APP_NAME: str = os.getenv("APP_NAME", "app")

_dt_now = datetime.now()
_str_date = _dt_now.strftime("%Y%m%d")
_str_date_folder = _dt_now.strftime("%Y-%m-%d")
_str_time = _dt_now.strftime("%H%M%S")

# ─────────────────────────────────────────────────────────────────────────────
# FRAGILITY GRADIENT — everything ABOVE this line must not be able to fail;
# everything BELOW it may. An import-time singleton module has to build its
# OBSERVABILITY before the first thing that can break, or a failure has nowhere
# to be written: the process dies with no log file, no traceback and no run
# folder, and the operator has nothing at all to read.
# ─────────────────────────────────────────────────────────────────────────────

# Filename templates used only when outputs.yaml could not be read — enough to give the
# failure a place to be recorded. They are never the normal path.
_DICT_FALLBACK_OUTPUTS: dict[str, str] = {
	"log_name": "{app_name}_{environment}_{date}_{time}.log",
	"json_name": "{app_name}_{environment}_{date}_{time}.json",
	"txt_name": "{app_name}_{environment}_{date}_{time}.txt",
}

# Prefer a single plain inputs.yaml/outputs.yaml (default); a project opts into env-wise
# config by deleting the plain file and shipping inputs_dev.yaml/inputs_prd.yaml (etc.),
# after which ENV selects the file and an unknown ENV fails loud (see env_config).
#
# The read is FAILABLE (missing file, unreadable file, unknown ENV), so its failure is
# captured rather than raised: the logger below is built either way, and the error is
# reported through it at the end of this module.
_str_config_error: str | None = None
YAML_OUTPUTS: dict = {}
YAML_INPUTS: dict = {}

try:
	YAML_OUTPUTS = yaml.safe_load(
		resolve_config_path(ENVIRONMENT, "outputs", _CONFIG_DIR).read_text(encoding="utf-8")
	)
	YAML_INPUTS = yaml.safe_load(
		resolve_config_path(ENVIRONMENT, "inputs", _CONFIG_DIR).read_text(encoding="utf-8")
	)
	# Validate the SHAPE here, inside the guard. An empty YAML file loads as nothing at all,
	# and a non-mapping root loads as a scalar or as a sequence. Each of those reaches the
	# output directory resolver further down and raises there — that is, BELOW this block and
	# before the logger exists, which is exactly the failure the fragility gradient was
	# introduced to remove. Checking the type here routes a malformed config to the same
	# reported, exit-2 path as a missing one.
	for str_label, dict_loaded in (("outputs", YAML_OUTPUTS), ("inputs", YAML_INPUTS)):
		if not isinstance(dict_loaded, dict):
			raise TypeError(
				f"{str_label} config must be a YAML mapping, got {type(dict_loaded).__name__}"
			)
	# The three filename templates are read unconditionally below; a non-string here would
	# fail while being formatted, for the same reason, one line later.
	for str_key in ("log_name", "json_name", "txt_name"):
		if not isinstance(YAML_OUTPUTS.get(str_key), str):
			raise TypeError(f"outputs config must define {str_key!r} as a string")
# Exception, never BaseException: the config helpers raise SystemExit(2) for an unknown ENV
# and that must pass straight through rather than being reported as a config read failure.
except Exception as cls_exc:  # noqa: BLE001
	_str_config_error = f"{type(cls_exc).__name__}: {cls_exc}"
	YAML_OUTPUTS = dict(_DICT_FALLBACK_OUTPUTS)
	YAML_INPUTS = {}


# Single output root (inputs.yaml); optionally partitioned into <root>/<YYYY-MM-DD>/.
# The partition uses the human-readable _str_date_folder; filenames keep the compact
# _str_date (see output_path).
@type_checker
def _resolve_out_dir() -> Path:
	r"""Resolve the run's output directory with a temp-dir fallback.

	Two safety nets keep import-time singletons from exploding off the production
	host: (1) a configured Windows network path (``A:\\...``) on a POSIX box
	(dev/CI) is unreachable, so write under the temp dir instead; (2) any
	``mkdir`` failure (permissions, missing mount) also falls back to the temp dir.

	Returns
	-------
	Path
		An existing directory the process can write to.
	"""
	str_base = str(YAML_INPUTS.get("daily_infos_base_path", "logs"))
	bool_dated = bool(YAML_INPUTS.get("daily_infos_dated", False))
	path_temp_root = Path(tempfile.gettempdir()) / (APP_NAME or "app")

	# The root is a value CHOICE, so it reads as one. A Windows-shaped path is unreachable
	# off Windows, and the temp root stands in for it. What follows below stays a real
	# handler, because that one is error handling rather than a choice.
	bool_unreachable = is_windows_path(str_base) and os.name != "nt"
	path_root = path_temp_root if bool_unreachable else Path(str_base).expanduser()

	path_dir = path_root / _str_date_folder if bool_dated else path_root
	try:
		path_dir.mkdir(parents=True, exist_ok=True)
	except OSError:
		path_dir = path_temp_root / _str_date_folder if bool_dated else path_temp_root
		path_dir.mkdir(parents=True, exist_ok=True)
	return path_dir


_out_dir = _resolve_out_dir()


@type_checker
def output_path(str_name_key: str) -> Path:
	"""Build an output file path from an ``outputs.yaml`` filename template.

	Parameters
	----------
	str_name_key : str
		Key in ``outputs.yaml`` (e.g. ``"log_name"``, ``"json_name"``, ``"xlsx_name"``).

	Returns
	-------
	Path
		Fully-qualified path under the run's output directory, timestamped to import time.
	"""
	return _out_dir / YAML_OUTPUTS[str_name_key].format(
		environment=ENVIRONMENT, app_name=APP_NAME, user=USER, date=_str_date, time=_str_time
	)


PATH_LOG: Path = output_path("log_name")
PATH_JSON: Path = output_path("json_name")
PATH_TXT: Path = output_path("txt_name")

DIR_PARENT: str = str(_out_dir)
LOGGER = cls_create_log.basic_conf(complete_path=str(PATH_LOG), basic_level="info")

# The logger now exists, so a failure from the block above finally has somewhere to go.
# Report it to BOTH the log file and stderr, name the log's path (the operator has to be
# told where to look), and exit 2 — continuing on fallback config would run the job against
# values nobody configured.
if _str_config_error is not None:
	LOGGER.critical("Configuration could not be read: %s", _str_config_error)
	LOGGER.critical("Falling back to default output names; the run is aborted.")
	print(f"FATAL: configuration could not be read: {_str_config_error}", file=sys.stderr)
	print(f"Details were written to: {PATH_LOG}", file=sys.stderr)
	raise SystemExit(2)
