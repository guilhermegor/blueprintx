"""Service entrypoint demonstrating core and module wiring."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from core.application import build_database_handler
from modules.example_feature.application.use_cases import CreateNote, ListNotes
from modules.example_feature.infrastructure.repositories import InMemoryNoteRepository


def main() -> None:
    """Run the service entrypoint.

    Demonstrates:
    - Database handler selection via ``build_database_handler``
    - Feature module wiring with use-cases and repositories
    """
    load_dotenv()

    # Core: database handler from environment config
    db_handler = build_database_handler()
    print(f"Database backend: {db_handler.__class__.__name__}")

    # Module: example_feature wiring
    note_repo = InMemoryNoteRepository()
    create_note = CreateNote(note_repo)
    list_notes = ListNotes(note_repo)

    # Demo usage
    if os.getenv("RUN_DEMO", "false").lower() == "true":
        note = create_note.execute("Hello from DDD service!")
        print(f"Created note: {note}")
        all_notes = list_notes.execute()
        print(f"All notes: {list(all_notes)}")


if __name__ == "__main__":
    main()
