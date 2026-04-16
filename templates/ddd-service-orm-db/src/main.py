"""Service entrypoint demonstrating core and module wiring."""

from __future__ import annotations

import os
import warnings
from time import time

from dotenv import load_dotenv
from stpstone.utils.calendars.calendar_br import DatesBRAnbima
from stpstone.utils.loggs.create_logs import CreateLog
from stpstone.utils.loggs.init_setup import initiate_logging

from src.config.global_slots import (
	CLS_MS_TEAMS,
	DIR_PARENT,
	ENVIRONMENT,
	HOSTNAME,
	LOGGER,
	MSG_MS_TEAMS,
	USER,
	YAML_OUTPUTS,
	YAML_WEBHOOKS,
)
from core.application import build_database_handler
from modules.example_feature.application.use_cases import CreateNote, ListNotes
from modules.example_feature.infrastructure.repositories import InMemoryNoteRepository


# --- initialisation ---
load_dotenv()
cls_create_log = CreateLog()
cls_dates_br_anbima = DatesBRAnbima()
float_start_time = time()
warnings.simplefilter(action="ignore", category=FutureWarning)
initiate_logging(LOGGER, DIR_PARENT)

# --- database handler ---
cls_create_log.log_message(logger=LOGGER, message="Building database handler", log_level="info")
db_handler = build_database_handler()
cls_create_log.log_message(
	logger=LOGGER,
	message=f"Database backend: {db_handler.__class__.__name__}",
	log_level="info",
)

# --- module wiring ---
cls_create_log.log_message(logger=LOGGER, message="Wiring example_feature module", log_level="info")
note_repo = InMemoryNoteRepository()
create_note = CreateNote(note_repo)
list_notes = ListNotes(note_repo)

# --- demo execution ---
if os.getenv("RUN_DEMO", "false").lower() == "true":
	note = create_note.execute("Hello from DDD service!")
	cls_create_log.log_message(logger=LOGGER, message=f"Created note: {note}", log_level="info")
	all_notes = list_notes.execute()
	cls_create_log.log_message(
		logger=LOGGER, message=f"All notes: {list(all_notes)}", log_level="info"
	)

# --- notifications ---
if ENVIRONMENT == "production":
	CLS_MS_TEAMS.send_message(str_msg=MSG_MS_TEAMS, str_title=YAML_WEBHOOKS["ms_teams"]["title"])

# --- teardown ---
float_elapsed_time = time() - float_start_time
hours, remainder = divmod(float_elapsed_time, 3600)
minutes, seconds = divmod(remainder, 60)
cls_create_log.log_message(
	logger=LOGGER,
	message=f"Time elapsed(HH:MM:SS): {int(hours)}:{int(minutes)}:{seconds:.2f}",
	log_level="info",
)
cls_create_log.log_message(
	logger=LOGGER,
	message="Routine ended in {}".format(str(cls_dates_br_anbima.curr_datetime())),
	log_level="info",
)
