"""Controller entry-point — builds the pipeline orchestrator and runs it (native DB).

Script-style and intentionally thin: it wires the ``config.startup`` singletons + config
into :class:`controller._pipeline.PipelineOrchestrator` and calls ``run``. It defines no
functions — business logic lives in the model and all phase sequencing in the orchestrator.
Run it with ``make run`` or ``python src/controller/main.py``.
"""

import os
import sys
import warnings


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.connection_db import build_connection  # noqa: E402
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


warnings.simplefilter(action="ignore", category=FutureWarning)

# E-mail handler (opt-in seam): the assignment below is replaced at scaffold time when the
# e-mail opt-in is chosen, to build an EmailHandler (Outlook backend by default). By default
# no handler is wired and the orchestrator runs without sending.
CLS_EMAIL_HANDLER = None

PipelineOrchestrator(
	logger=LOGGER,
	fn_build_connection=build_connection,
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
	cls_email_handler=CLS_EMAIL_HANDLER,
).run()
