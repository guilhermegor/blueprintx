"""Startup: logger and runtime constants.

All module-level names are initialised once at import time. Import this module
early (before any feature code) so every consumer shares the same instances.
"""

from datetime import datetime
from getpass import getuser
import os
from pathlib import Path
from socket import gethostname
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

# Prefer a single plain inputs.yaml/outputs.yaml (default); a project opts into env-wise
# config by deleting the plain file and shipping inputs_dev.yaml/inputs_prd.yaml (etc.),
# after which ENV selects the file and an unknown ENV fails loud (see env_config).
YAML_OUTPUTS: dict = yaml.safe_load(
	resolve_config_path(ENVIRONMENT, "outputs", _CONFIG_DIR).read_text(encoding="utf-8")
)
YAML_INPUTS: dict = yaml.safe_load(
	resolve_config_path(ENVIRONMENT, "inputs", _CONFIG_DIR).read_text(encoding="utf-8")
)

_dt_now = datetime.now()
_str_date = _dt_now.strftime("%Y%m%d")
_str_date_folder = _dt_now.strftime("%Y-%m-%d")
_str_time = _dt_now.strftime("%H%M%S")


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

	if is_windows_path(str_base) and os.name != "nt":
		path_root = path_temp_root
	else:
		path_root = Path(str_base).expanduser()

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
