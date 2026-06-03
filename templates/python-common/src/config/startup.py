"""Startup: logger and runtime constants.

All module-level names are initialised once at import time. Import this module
early (before any feature code) so every consumer shares the same instances.
"""

from datetime import datetime
from getpass import getuser
import os
from pathlib import Path
from socket import gethostname

from dotenv import load_dotenv
from stpstone.utils.loggs.create_logs import CreateLog
from stpstone.utils.parsers.yaml import reading_yaml


load_dotenv(override=True)

cls_create_log = CreateLog()

_CONFIG_DIR = Path(__file__).parent

USER: str = getuser()
HOSTNAME: str = gethostname()
ENVIRONMENT: str = os.getenv("ENV", "development").lower()
APP_NAME: str = os.getenv("APP_NAME", "app")

YAML_OUTPUTS: dict = reading_yaml(str(_CONFIG_DIR / "outputs.yaml"))
YAML_INPUTS: dict = reading_yaml(str(_CONFIG_DIR / "inputs.yaml"))

_dt_now = datetime.now()
_str_date = _dt_now.strftime("%Y%m%d")
_str_date_folder = _dt_now.strftime("%Y-%m-%d")
_str_time = _dt_now.strftime("%H%M%S")

# Single output root (inputs.yaml); optionally partitioned into <root>/<YYYY-MM-DD>/.
# The partition uses the human-readable _str_date_folder; filenames keep the compact
# _str_date (see output_path).
_root = Path(YAML_INPUTS.get("daily_infos_base_path", "logs")).expanduser()
_out_dir = _root / _str_date_folder if YAML_INPUTS.get("daily_infos_dated", False) else _root
_out_dir.mkdir(parents=True, exist_ok=True)


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
