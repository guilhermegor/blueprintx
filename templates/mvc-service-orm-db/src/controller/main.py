"""Controller entry-point — builds the pipeline orchestrator and runs it (SQLAlchemy ORM).

Script-style and intentionally thin: it wires the ``config.startup`` singletons + config
into :class:`controller._pipeline.PipelineOrchestrator` and calls ``run``. It defines no
functions — business logic lives in the model and all phase sequencing in the orchestrator.
Run it with ``make run`` or ``python src/controller/main.py``.
"""

import os
import sys
import warnings


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
from controller._pipeline import PipelineOrchestrator  # noqa: E402
from utils.outlook_gateway import OutlookGateway  # noqa: E402
from utils.paths import resolve_path  # noqa: E402


warnings.simplefilter(action="ignore", category=FutureWarning)

PipelineOrchestrator(
	logger=LOGGER,
	fn_build_engine=build_engine,
	fn_output_path=output_path,
	path_json=PATH_JSON,
	dict_context={
		"App": APP_NAME,
		"Operator": USER,
		"Hostname": HOSTNAME,
		"Environment": ENVIRONMENT,
		"Inputs config in memory": YAML_INPUTS,
		"Log path": PATH_LOG,
		"JSON export path": PATH_JSON,
	},
	cls_email_gateway=OutlookGateway(
		os.getenv("SENDER_EMAIL", ""),
		path_signatures_dir=resolve_path("src/config/signatures"),
		logger=LOGGER,
	),
).run()
