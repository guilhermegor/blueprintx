"""Service entrypoint demonstrating core and module wiring with SQLAlchemy ORM."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from core.application import build_database_session
from core.infrastructure.database import SQLAlchemyRecordRepository
from modules.example_feature.application.use_cases import CreateNote, ListNotes
from modules.example_feature.infrastructure.repositories import InMemoryNoteRepository


def main() -> None:
    """Run the service entrypoint.

    Demonstrates:
    - SQLAlchemy database session from ``build_database_session``
    - Feature module wiring with use-cases and repositories
    """
    load_dotenv()

    # Core: SQLAlchemy database session from environment config
    db = build_database_session(echo=os.getenv("SQL_ECHO", "false").lower() == "true")
    db.create_tables()
    print(f"Database URL: {db.engine.url}")

    # Example: Using the generic SQLAlchemy repository
    with db.session() as session:
        repo = SQLAlchemyRecordRepository(session)
        # Demo: add a record
        if os.getenv("RUN_DEMO", "false").lower() == "true":
            record_id = repo.add({"title": "Hello from SQLAlchemy!", "content": "ORM-based storage"})
            session.commit()
            print(f"Created record: {record_id}")
            print(f"All records: {repo.list_all()}")

    # Module: example_feature wiring (domain-specific, uses in-memory by default)
    note_repo = InMemoryNoteRepository()
    create_note = CreateNote(note_repo)
    list_notes = ListNotes(note_repo)

    # Demo usage for feature module
    if os.getenv("RUN_DEMO", "false").lower() == "true":
        note = create_note.execute("Hello from DDD service with SQLAlchemy!")
        print(f"Created note: {note}")
        all_notes = list_notes.execute()
        print(f"All notes: {list(all_notes)}")


if __name__ == "__main__":
    main()
