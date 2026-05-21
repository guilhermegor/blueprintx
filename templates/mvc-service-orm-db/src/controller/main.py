"""Controller entry-point — orchestrates the MVC pipeline (SQLAlchemy ORM).

Script-style on purpose: read top to bottom to follow the flow. The controller
wires config → model → view, bracketing each phase with start/finish log lines
so a run is easy to trace. Run it with ``make start`` or
``python src/controller/main.py``.
"""

import os
import sys
import warnings
from pathlib import Path
from time import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.startup import (  # noqa: E402
	CLS_MS_TEAMS,
	ENVIRONMENT,
	LOGGER,
	MSG_MS_TEAMS,
	YAML_WEBHOOKS,
)
from model.conexao_db import build_engine  # noqa: E402
from model.example_entity import ExampleEntity  # noqa: E402
from stpstone.utils.loggs.create_logs import CreateLog  # noqa: E402
from view.report_renderer import RenderToExcel  # noqa: E402


# start the run timer
float_start_time = time()

# silence pandas/openpyxl forward-incompatibility noise that clutters run logs
warnings.simplefilter(action="ignore", category=FutureWarning)

cls_create_log = CreateLog()


def log_info(str_msg: str) -> None:
	"""Log an info-level line to the shared run logger (terse pipeline shim)."""
	cls_create_log.log_message(logger=LOGGER, message=str_msg, log_level="info")


# accumulates the artifacts produced by the run (paths, counts) for a final summary
dict_xpt: dict = {}

log_info("Starting variable-definition process")
path_report = Path("data") / "report.xlsx"
log_info("Finishing variable-definition process")

log_info("Starting data-read process")
cls_engine = build_engine()
cls_example = ExampleEntity(cls_engine)
cls_example.ensure_table()
cls_example.insert("Hello from MVC ORM service!")
df_report = cls_example.fetch_all()
cls_engine.dispose()
dict_xpt["rows_read"] = len(df_report)
log_info(f"Finishing data-read process ({len(df_report)} rows)")

log_info("Starting report-export process")
RenderToExcel(path_report).render(df_report)
dict_xpt["report_path"] = str(path_report)
log_info(f"Finishing report-export process ({path_report})")

if ENVIRONMENT == "production":
	CLS_MS_TEAMS.send_message(str_msg=MSG_MS_TEAMS, str_title=YAML_WEBHOOKS["ms_teams"]["title"])

# report total run duration in HH:MM:SS
float_elapsed_time = time() - float_start_time
float_hours, float_remainder = divmod(float_elapsed_time, 3600)
float_minutes, float_seconds = divmod(float_remainder, 60)
log_info(f"Run finished (HH:MM:SS): {int(float_hours)}:{int(float_minutes)}:{float_seconds:.2f}")
