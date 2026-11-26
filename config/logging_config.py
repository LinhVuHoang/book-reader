from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings

HANDLER_TAG = "_book_reader_handler"
_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def _resolve_log_path(log_file: str | None) -> Path | None:
    configured = settings.LOG_FILE if log_file is None else log_file
    if configured == "":
        return None
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = settings.BASE_DIR / path
    return path.resolve()


def setup_logging(level: str | None = None, log_file: str | None = None) -> None:
    root = logging.getLogger()
    if any(getattr(handler, HANDLER_TAG, False) for handler in root.handlers):
        return

    formatter = logging.Formatter(_FORMAT)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    setattr(console, HANDLER_TAG, True)
    root.addHandler(console)

    path = _resolve_log_path(log_file)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        setattr(file_handler, HANDLER_TAG, True)
        root.addHandler(file_handler)

    root.setLevel(level or settings.LOG_LEVEL)
