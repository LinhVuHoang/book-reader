from pathlib import Path

import pytest

from src.database.init_db import init_db
from src.database.repository import BookRecord, create_book


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "book_reader.db"
    init_db(path)
    return path


@pytest.fixture
def book(db_path: Path) -> BookRecord:
    return create_book(
        title="Test Book",
        file_path="test.pdf",
        file_hash="test-hash",
        total_pages=10,
        db_path=db_path,
    )
