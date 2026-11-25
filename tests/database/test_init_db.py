from pathlib import Path

import pytest

from src.database.repository import (
    BookRecord,
    PageData,
    create_book,
    get_book,
    insert_pages,
)
from src.database.init_db import init_db


def test_init_db_can_run_repeatedly_without_data_loss(
    db_path: Path, book: BookRecord
) -> None:
    init_db(db_path)
    init_db(db_path)

    assert get_book(book.id, db_path=db_path) == book


def test_foreign_keys_are_enforced(db_path: Path) -> None:
    with pytest.raises(Exception):
        insert_pages(
            999,
            [PageData(page_number=1, content="orphan", method="text")],
            db_path=db_path,
        )


def test_status_and_method_checks_are_enforced(db_path: Path) -> None:
    with pytest.raises(Exception):
        create_book(
            title="Bad Status",
            file_path="bad.pdf",
            file_hash="bad-status",
            total_pages=1,
            status="unknown",
            db_path=db_path,
        )

    book = create_book(
        title="Good Book",
        file_path="good.pdf",
        file_hash="good-hash",
        total_pages=1,
        db_path=db_path,
    )
    with pytest.raises(Exception):
        insert_pages(
            book.id,
            [PageData(page_number=1, content="x", method="scan")],
            db_path=db_path,
        )


def test_invalid_confidence_is_rejected(db_path: Path, book: BookRecord) -> None:
    for page_number, confidence in ((1, -0.01), (2, 1.01)):
        with pytest.raises(Exception):
            insert_pages(
                book.id,
                [
                    PageData(
                        page_number=page_number,
                        content="x",
                        method="ocr",
                        confidence=confidence,
                    )
                ],
                db_path=db_path,
            )

    pages = insert_pages(
        book.id,
        [
            PageData(page_number=3, content="low", method="ocr", confidence=0.0),
            PageData(page_number=4, content="high", method="ocr", confidence=1.0),
        ],
        db_path=db_path,
    )
    assert [page.confidence for page in pages] == [0.0, 1.0]
