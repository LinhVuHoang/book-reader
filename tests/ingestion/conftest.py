from collections.abc import Callable
from pathlib import Path

import pymupdf as fitz
import pytest

from src.database.init_db import init_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "book_reader.db"
    init_db(path)
    return path


@pytest.fixture
def make_pdf(tmp_path: Path) -> Callable[[list[str], str], Path]:
    def _make(texts: list[str], name: str = "sample.pdf") -> Path:
        path = tmp_path / name
        document = fitz.open()
        for text in texts:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        document.save(path)
        document.close()
        return path

    return _make
