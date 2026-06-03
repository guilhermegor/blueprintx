"""Controller entry-point — orchestrates the MVC pipeline (SQLAlchemy ORM).

Script-style on purpose: read top to bottom to follow the flow. The controller
wires config → model → view, bracketing each phase with start/finish log lines
so a run is easy to trace. Run it with ``make run`` or
``python src/controller/main.py``.
"""

import os
import sys
from time import time
import warnings


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from stpstone.utils.loggs.create_logs import CreateLog  # noqa: E402
from stpstone.utils.parsers.json import JsonFiles  # noqa: E402

from config.connection_db import build_engine  # noqa: E402
from config.startup import (  # noqa: E402
	APP_NAME,
	ENVIRONMENT,
	HOSTNAME,
	LOGGER,
	PATH_JSON,
	PATH_LOG,
	USER,
	YAML_INPUTS,
	output_path,
)
from model.example_entity import ExampleEntity  # noqa: E402
from view.report_renderer import RenderToExcel  # noqa: E402


float_start_time = time()

warnings.simplefilter(action="ignore", category=FutureWarning)

cls_create_log = CreateLog()

dict_xpt: dict = {}

path_report = output_path("xlsx_name")

# --- variable definition: record run context so every log file is self-describing ---
cls_create_log.log_message(LOGGER, "Starting variable-definition process", "info")
cls_create_log.log_message(LOGGER, f"App: {APP_NAME}", "info")
cls_create_log.log_message(LOGGER, f"Operator: {USER}", "info")
cls_create_log.log_message(LOGGER, f"Hostname: {HOSTNAME}", "info")
cls_create_log.log_message(LOGGER, f"Environment: {ENVIRONMENT}", "info")
cls_create_log.log_message(LOGGER, f"Inputs config in memory: {YAML_INPUTS}", "info")
cls_create_log.log_message(LOGGER, f"Log path: {PATH_LOG}", "info")
cls_create_log.log_message(LOGGER, f"JSON export path: {PATH_JSON}", "info")
cls_create_log.log_message(LOGGER, f"Report export path: {path_report}", "info")
cls_create_log.log_message(LOGGER, "Finishing variable-definition process", "info")

# --- model: read source data into a DataFrame ---
# Session lifecycle: build the engine, use it, and guarantee dispose() via finally.
cls_create_log.log_message(LOGGER, "Starting data-read process", "info")
cls_engine = build_engine()
try:
	cls_example = ExampleEntity(cls_engine)
	cls_example.ensure_table()
	cls_example.insert("Hello from MVC ORM service!")
	df_report = cls_example.fetch_all()
finally:
	cls_engine.dispose()
dict_xpt["rows_read"] = len(df_report)
cls_create_log.log_message(LOGGER, f"Finishing data-read process ({len(df_report)} rows)", "info")

# --- view: render outputs (report + run summary) ---
cls_create_log.log_message(LOGGER, "Starting report-export process", "info")
RenderToExcel(path_report).render(df_report)
dict_xpt["report_path"] = str(path_report)
cls_create_log.log_message(LOGGER, f"Finishing report-export process ({path_report})", "info")

cls_create_log.log_message(LOGGER, "Starting summary-export process", "info")
bool_json_dump = JsonFiles().dump_message(dict_xpt, str(PATH_JSON))
cls_create_log.log_message(LOGGER, f"Summary export ok={bool_json_dump}: {PATH_JSON}", "info")

float_elapsed_time = time() - float_start_time
float_hours, float_remainder = divmod(float_elapsed_time, 3600)
float_minutes, float_seconds = divmod(float_remainder, 60)
cls_create_log.log_message(
	LOGGER,
	f"Run finished (HH:MM:SS): {int(float_hours)}:{int(float_minutes)}:{float_seconds:.2f}",
	"info",
)
