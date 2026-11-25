from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = BASE_DIR / "data" / "book_reader.db"


def _resolve_database_path() -> Path:
    configured = os.getenv("BOOK_READER_DB_PATH")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
    else:
        path = DEFAULT_DATABASE_PATH
    return path.resolve()


DATABASE_PATH = _resolve_database_path()
