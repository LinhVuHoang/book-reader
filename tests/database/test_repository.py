import sqlite3
from pathlib import Path

import pytest

from src.database.repository import (
    BookRecord,
    ChunkData,
    DuplicateBookHashError,
    PageChunkData,
    PageData,
    create_book,
    delete_book_physically,
    get_book,
    get_chunks,
    get_chunks_for_page,
    get_pages,
    get_pages_for_chunk,
    insert_chunks,
    insert_page_chunks,
    insert_pages,
    list_books,
    soft_delete_book,
    update_book_status,
)


def test_duplicate_page_number_is_rejected(
    db_path: Path, book: BookRecord
) -> None:
    insert_pages(
        book.id,
        [PageData(page_number=1, content="first", method="text")],
        db_path=db_path,
    )
    with pytest.raises(sqlite3.IntegrityError):
        insert_pages(
            book.id,
            [PageData(page_number=1, content="second", method="text")],
            db_path=db_path,
        )

    assert [page.content for page in get_pages(book.id, db_path=db_path)] == ["first"]


def test_duplicate_chunk_index_is_rejected(
    db_path: Path, book: BookRecord
) -> None:
    insert_chunks(book.id, [ChunkData(chunk_index=0, content="first")], db_path=db_path)
    with pytest.raises(sqlite3.IntegrityError):
        insert_chunks(
            book.id, [ChunkData(chunk_index=0, content="second")], db_path=db_path
        )

    assert [chunk.content for chunk in get_chunks(book.id, db_path=db_path)] == ["first"]


def test_duplicate_file_hash_raises_clear_exception(
    db_path: Path, book: BookRecord
) -> None:
    with pytest.raises(DuplicateBookHashError, match="test-hash"):
        create_book(
            title="Other Book",
            file_path="other.pdf",
            file_hash=book.file_hash,
            total_pages=1,
            db_path=db_path,
        )


def test_update_book_status_updates_status(
    db_path: Path, book: BookRecord
) -> None:
    updated = update_book_status(book.id, "completed", db_path=db_path)

    assert updated is not None
    assert updated.status == "completed"


def test_soft_deleted_books_are_excluded_from_normal_listing(
    db_path: Path, book: BookRecord
) -> None:
    soft_delete_book(book.id, db_path=db_path)

    assert all(item.id != book.id for item in list_books(db_path=db_path))
    assert any(
        item.id == book.id for item in list_books(include_deleted=True, db_path=db_path)
    )


def test_get_pages_filters_by_page_range(
    db_path: Path, book: BookRecord
) -> None:
    insert_pages(
        book.id,
        [
            PageData(page_number=number, content=f"page {number}", method="text")
            for number in range(1, 6)
        ],
        db_path=db_path,
    )

    pages = get_pages(book.id, start_page=2, end_page=4, db_path=db_path)

    assert [page.page_number for page in pages] == [2, 3, 4]


def test_physical_delete_cascades_to_related_records(
    db_path: Path, book: BookRecord
) -> None:
    pages = insert_pages(
        book.id,
        [
            PageData(page_number=1, content="abc", method="text"),
            PageData(page_number=2, content="def", method="text"),
        ],
        db_path=db_path,
    )
    chunks = insert_chunks(
        book.id,
        [ChunkData(chunk_index=0, content="abcdef")],
        db_path=db_path,
    )
    insert_page_chunks(
        [
            PageChunkData(pages[0].id, chunks[0].id, 0, 3),
            PageChunkData(pages[1].id, chunks[0].id, 0, 3),
        ],
        db_path=db_path,
    )

    delete_book_physically(book.id, db_path=db_path)

    assert get_book(book.id, db_path=db_path) is None
    assert get_pages(book.id, db_path=db_path) == []
    assert get_chunks(book.id, db_path=db_path) == []
    assert get_chunks_for_page(pages[0].id, db_path=db_path) == []
    assert get_pages_for_chunk(chunks[0].id, db_path=db_path) == []
