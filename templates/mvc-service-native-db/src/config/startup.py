"""Startup: logger, MS Teams webhook, and runtime constants.

All module-level names are initialised once at import time. Import this module
early (before any feature code) so every consumer shares the same instances.
"""

import os
from getpass import getuser
from pathlib import Path
from socket import gethostname

from dotenv import load_dotenv
from stpstone.utils.calendars.calendar_br import DatesBRAnbima
from stpstone.utils.loggs.create_logs import CreateLog
from stpstone.utils.parsers.folders import DirFilesManagement
from stpstone.utils.parsers.yaml import reading_yaml
from stpstone.utils.webhooks.teams import WebhookTeams


load_dotenv()

cls_dates_br = DatesBRAnbima()
cls_create_log = CreateLog()
cls_dir_files_management = DirFilesManagement()

_CONFIG_DIR = Path(__file__).parent

USER: str = getuser()
HOSTNAME: str = gethostname()
ENVIRONMENT: str = os.getenv("ENV", "development").lower()
APP_NAME: str = os.getenv("APP_NAME", "app")

YAML_OUTPUTS: dict = reading_yaml(str(_CONFIG_DIR / "outputs.yaml"))
YAML_WEBHOOKS: dict = reading_yaml(str(_CONFIG_DIR / "webhooks.yaml"))
YAML_INPUTS: dict = reading_yaml(str(_CONFIG_DIR / "inputs.yaml"))
CLS_MS_TEAMS = WebhookTeams(YAML_WEBHOOKS["ms_teams"]["url"])

_dt_run = cls_dates_br.curr_date()
_dt_run_time = cls_dates_br.curr_time()
_str_date = _dt_run.strftime("%Y%m%d")
_str_time = _dt_run_time.strftime("%H%M%S")

# Base output dir comes from outputs.yaml (relative, absolute POSIX, or Windows UNC);
# pathlib handles separators so the same code runs on macOS, Linux, and Windows. Outputs
# are partitioned into a daily subfolder: <output_dir>/<daily_subfolder>/<YYYY-MM-DD>/.
_path_output_dir = Path(YAML_OUTPUTS["output_dir"])
_path_daily = _path_output_dir / YAML_OUTPUTS["daily_subfolder"] / _dt_run.strftime("%Y-%m-%d")

PATH_LOG: Path = _path_daily / YAML_OUTPUTS["path_log"].format(
	APP_NAME, USER, _str_date, _str_time
)
PATH_JSON: Path = _path_daily / YAML_OUTPUTS["path_json"].format(
	APP_NAME, USER, _str_date, _str_time
)
PATH_REPORT: Path = _path_daily / YAML_OUTPUTS["path_report"].format(
	APP_NAME, USER, _str_date, _str_time
)

DIR_PARENT = str(_path_daily)
cls_dir_files_management.mk_new_directory(DIR_PARENT)
LOGGER = cls_create_log.basic_conf(complete_path=str(PATH_LOG), basic_level="info")

MSG_MS_TEAMS: str = YAML_WEBHOOKS["ms_teams"]["message"].format(
	YAML_WEBHOOKS["ms_teams"]["title"],
	cls_dates_br.curr_date(),
	HOSTNAME,
	USER,
	str(PATH_JSON),
	str(PATH_LOG),
)
