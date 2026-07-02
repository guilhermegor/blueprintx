"""Controller entry-point — resolves PIPELINE_INTENT and runs the chosen pipeline (ORM).

Script-style and intentionally thin (multi-intent mode): it reads ``PIPELINE_INTENT``,
resolves it to a canonical intent, builds the matching orchestrator via
``controller.pipeline_dispatch``, and calls ``run``. It defines no functions — business logic
lives in the model, phase sequencing in each ``controller/pipeline_<intent>.py``, and the shared
phases in ``controller/pipeline_common.py``. Run it with ``make run`` (set ``PIPELINE_INTENT`` in
``.env``) or ``PIPELINE_INTENT=reconcile python src/controller/main.py``.
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
from controller.pipeline_dispatch import build_pipeline, resolve_intent  # noqa: E402


warnings.simplefilter(action="ignore", category=FutureWarning)

# E-mail handler (opt-in seam): the assignment below is replaced at scaffold time when the
# e-mail opt-in is chosen, to build an EmailHandler (Outlook backend by default). By default
# no handler is wired and the chosen pipeline runs without sending.
CLS_EMAIL_HANDLER = None

# PIPELINE_INTENT selects which purpose to run; default "send" preserves single-mode behaviour.
# resolve_intent normalises the spelling and fails loud (SystemExit 2) on an unknown value.
STR_INTENT = resolve_intent(os.getenv("PIPELINE_INTENT", "send"))

build_pipeline(
	STR_INTENT,
	logger=LOGGER,
	fn_build_engine=build_engine,
	fn_output_path=output_path,
	path_json=PATH_JSON,
	dict_context={
		"App": APP_NAME,
		"Operator": USER,
		"Hostname": HOSTNAME,
		"Environment": ENVIRONMENT,
		"Pipeline intent": STR_INTENT,
		"Inputs config in memory": YAML_INPUTS,
		"Log path": PATH_LOG,
		"JSON export path": PATH_JSON,
	},
	cls_email_handler=CLS_EMAIL_HANDLER,
).run()
