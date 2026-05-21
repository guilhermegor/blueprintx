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
_folder = Path(YAML_OUTPUTS["folder"])

PATH_LOG: Path = _folder / YAML_OUTPUTS["path_log"].format(
	ENVIRONMENT,
	APP_NAME,
	USER,
	HOSTNAME,
	_dt_run.strftime("%Y%m%d"),
	_dt_run_time.strftime("%H%M%S"),
)
PATH_JSON: Path = _folder / YAML_OUTPUTS["path_json"].format(
	ENVIRONMENT,
	APP_NAME,
	USER,
	HOSTNAME,
	_dt_run.strftime("%Y%m%d"),
	_dt_run_time.strftime("%H%M%S"),
)

DIR_PARENT = str(_folder)
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
