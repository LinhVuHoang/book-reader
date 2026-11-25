from __future__ import annotations

from pathlib import Path

from config import settings
from src.database.connection import database

_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_hash TEXT NOT NULL UNIQUE,
        total_pages INTEGER NOT NULL CHECK (total_pages > 0),
        status TEXT NOT NULL CHECK (
            status IN ('pending', 'processing', 'completed', 'failed', 'deleted')
        ),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
        page_number INTEGER NOT NULL CHECK (page_number > 0),
        content TEXT NOT NULL,
        method TEXT NOT NULL CHECK (method IN ('text', 'ocr')),
        confidence REAL CHECK (
            confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
        ),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (book_id, page_number)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (book_id, chunk_index)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS page_chunk (
        page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
        chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
        start_offset INTEGER NOT NULL CHECK (start_offset >= 0),
        end_offset INTEGER NOT NULL CHECK (end_offset >= start_offset),
        PRIMARY KEY (page_id, chunk_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_page_chunk_chunk_id
    ON page_chunk (chunk_id)
    """,
)


def init_db(db_path: Path | str | None = None) -> None:
    with database(db_path) as connection:
        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)


def main() -> None:
    init_db()
    print(f"Database initialized: {settings.DATABASE_PATH}")


if __name__ == "__main__":
    main()
