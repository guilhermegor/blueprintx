"""Service entrypoint: bootstrap → wire → run → teardown."""

from __future__ import annotations

from app.bootstrap import cls_create_log, init, teardown
from app.container import build
from capabilities.example_feature.domain.dto import NoteCreateDTO
from src.config.startup import CLS_MS_TEAMS, ENVIRONMENT, LOGGER, MSG_MS_TEAMS, YAML_WEBHOOKS


float_start_time = init()
cls_container = build()

cls_note = cls_container.create_note(NoteCreateDTO(title="Hello from DDD service!"))
cls_create_log.log_message(logger=LOGGER, message=f"Created: {cls_note}", log_level="info")

list_all_notes = cls_container.list_notes()
cls_create_log.log_message(logger=LOGGER, message=f"All notes: {list_all_notes}", log_level="info")

if ENVIRONMENT == "production":
	CLS_MS_TEAMS.send_message(str_msg=MSG_MS_TEAMS, str_title=YAML_WEBHOOKS["ms_teams"]["title"])

teardown(float_start_time)
