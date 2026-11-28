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


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


CHUNK_SIZE = _env_int("BOOK_READER_CHUNK_SIZE", 1000)
CHUNK_OVERLAP = _env_int("BOOK_READER_CHUNK_OVERLAP", 200)
LOG_LEVEL = os.getenv("BOOK_READER_LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("BOOK_READER_LOG_FILE", "logs/book_reader.log")

OCR_LANGUAGES = os.getenv("BOOK_READER_OCR_LANGUAGES", "vie+eng")
OCR_DPI = _env_int("BOOK_READER_OCR_DPI", 300)
OCR_MIN_CONFIDENCE = _env_float("BOOK_READER_OCR_MIN_CONFIDENCE", 80.0)
TESSERACT_CMD = os.getenv("TESSERACT_CMD") or None
