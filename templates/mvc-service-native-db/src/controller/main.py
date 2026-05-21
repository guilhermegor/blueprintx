"""Controller entry-point — orchestrates the MVC pipeline (native DB).

Script-style on purpose: read top to bottom to follow the flow. The controller
wires config → model → view, bracketing each phase with start/finish log lines
so a run is easy to trace. Run it with ``make start`` or
``python src/controller/main.py``.
"""

import os
import sys
import warnings
from time import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.startup import (  # noqa: E402
	APP_NAME,
	CLS_MS_TEAMS,
	ENVIRONMENT,
	HOSTNAME,
	LOGGER,
	MSG_MS_TEAMS,
	PATH_JSON,
	PATH_LOG,
	PATH_REPORT,
	USER,
	YAML_INPUTS,
	YAML_WEBHOOKS,
)
from model.conexao_db import build_connection  # noqa: E402
from model.example_entity import ExampleEntity  # noqa: E402
from stpstone.utils.loggs.create_logs import CreateLog  # noqa: E402
from view.report_renderer import RenderToExcel  # noqa: E402


# start the run timer
float_start_time = time()

# silence pandas/openpyxl forward-incompatibility noise that clutters run logs
warnings.simplefilter(action="ignore", category=FutureWarning)

cls_create_log = CreateLog()

# accumulates the artifacts produced by the run (paths, counts) for a final summary
dict_xpt: dict = {}

# --- variable definition: record run context so every log file is self-describing ---
cls_create_log.infos(LOGGER, "Starting variable-definition process")
cls_create_log.infos(LOGGER, f"App: {APP_NAME}")
cls_create_log.infos(LOGGER, f"Operator: {USER}")
cls_create_log.infos(LOGGER, f"Hostname: {HOSTNAME}")
cls_create_log.infos(LOGGER, f"Environment: {ENVIRONMENT}")
cls_create_log.infos(LOGGER, f"Inputs config in memory: {YAML_INPUTS}")
cls_create_log.infos(LOGGER, f"Log path: {PATH_LOG}")
cls_create_log.infos(LOGGER, f"JSON export path: {PATH_JSON}")
cls_create_log.infos(LOGGER, f"Report export path: {PATH_REPORT}")
cls_create_log.infos(LOGGER, "Finishing variable-definition process")

cls_create_log.infos(LOGGER, "Starting data-read process")
cls_connection = build_connection()
cls_example = ExampleEntity(cls_connection)
cls_example.ensure_table()
cls_example.insert("Hello from MVC native-db service!")
df_report = cls_example.fetch_all()
cls_connection.close()
dict_xpt["rows_read"] = len(df_report)
cls_create_log.infos(LOGGER, f"Finishing data-read process ({len(df_report)} rows)")

cls_create_log.infos(LOGGER, "Starting report-export process")
RenderToExcel(PATH_REPORT).render(df_report)
dict_xpt["report_path"] = str(PATH_REPORT)
cls_create_log.infos(LOGGER, f"Finishing report-export process ({PATH_REPORT})")

if ENVIRONMENT == "production":
	CLS_MS_TEAMS.send_message(str_msg=MSG_MS_TEAMS, str_title=YAML_WEBHOOKS["ms_teams"]["title"])

# report total run duration in HH:MM:SS
float_elapsed_time = time() - float_start_time
float_hours, float_remainder = divmod(float_elapsed_time, 3600)
float_minutes, float_seconds = divmod(float_remainder, 60)
cls_create_log.infos(
	LOGGER,
	f"Run finished (HH:MM:SS): {int(float_hours)}:{int(float_minutes)}:{float_seconds:.2f}",
)
