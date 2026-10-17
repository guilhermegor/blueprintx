"""Service entrypoint: bootstrap → wire → run → teardown."""

from __future__ import annotations

from app.bootstrap import cls_create_log, init, teardown
from app.container import build
from capabilities.example_feature.domain.dto import NoteCreateDTO
from config.startup import LOGGER


float_start_time = init()

cls_container = build()

cls_note = cls_container.create_note(NoteCreateDTO(title="Hello from DDD service!"))
cls_create_log.log_message(logger=LOGGER, message=f"Created: {cls_note}", log_level="info")

list_all_notes = cls_container.list_notes()
cls_create_log.log_message(logger=LOGGER, message=f"All notes: {list_all_notes}", log_level="info")

teardown(float_start_time)
