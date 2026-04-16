"""Global application slots: logger, MS Teams webhook, and runtime constants.

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

_CONFIG_DIR = Path(__file__).parent

USER: str = getuser()
HOSTNAME: str = gethostname()
ENVIRONMENT: str = os.getenv("ENV", "development").lower()

YAML_OUTPUTS: dict = reading_yaml(_CONFIG_DIR / "outputs.yaml")
YAML_WEBHOOKS: dict = reading_yaml(_CONFIG_DIR / "webhooks.yaml")

DIR_PARENT = Path(YAML_OUTPUTS["path_log"]).parent
DirFilesManagement().mk_new_directory(DIR_PARENT)
LOGGER = CreateLog().basic_conf(complete_path=YAML_OUTPUTS["path_log"], basic_level="info")

CLS_MS_TEAMS = WebhookTeams(YAML_WEBHOOKS["ms_teams"]["url"])

MSG_MS_TEAMS: str = YAML_WEBHOOKS["ms_teams"]["message"].format(
	YAML_WEBHOOKS["ms_teams"]["title"],
	DatesBRAnbima().curr_date(),
	HOSTNAME,
	USER,
	YAML_OUTPUTS["path_json"],
	YAML_OUTPUTS["path_log"],
)
