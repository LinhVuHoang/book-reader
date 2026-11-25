from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from src.database.connection import database


class DuplicateBookHashError(ValueError):
    pass


@dataclass(frozen=True)
class PageData:
    page_number: int
    content: str
    method: str
    confidence: float | None = None


@dataclass(frozen=True)
class ChunkData:
    chunk_index: int
    content: str


@dataclass(frozen=True)
class PageChunkData:
    page_id: int
    chunk_id: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class BookRecord:
    id: int
    title: str
    file_path: str
    file_hash: str
    total_pages: int
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class PageRecord:
    id: int
    book_id: int
    page_number: int
    content: str
    method: str
    confidence: float | None
    created_at: str


@dataclass(frozen=True)
class ChunkRecord:
    id: int
    book_id: int
    chunk_index: int
    content: str
    created_at: str


@dataclass(frozen=True)
class PageChunkRecord:
    page_id: int
    chunk_id: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class PageWithOffset:
    page: PageRecord
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class ChunkWithOffset:
    chunk: ChunkRecord
    start_offset: int
    end_offset: int


def _book_from_row(row: sqlite3.Row | None) -> BookRecord:
    assert row is not None
    return BookRecord(
        id=row["id"],
        title=row["title"],
        file_path=row["file_path"],
        file_hash=row["file_hash"],
        total_pages=row["total_pages"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _page_from_row(row: sqlite3.Row | None) -> PageRecord:
    assert row is not None
    return PageRecord(
        id=row["id"],
        book_id=row["book_id"],
        page_number=row["page_number"],
        content=row["content"],
        method=row["method"],
        confidence=row["confidence"],
        created_at=row["created_at"],
    )


def _chunk_from_row(row: sqlite3.Row | None) -> ChunkRecord:
    assert row is not None
    return ChunkRecord(
        id=row["id"],
        book_id=row["book_id"],
        chunk_index=row["chunk_index"],
        content=row["content"],
        created_at=row["created_at"],
    )


def create_book(
    title: str,
    file_path: str,
    file_hash: str,
    total_pages: int,
    status: str = "pending",
    db_path: Path | None = None,
) -> BookRecord:
    with database(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM books WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        if existing is not None:
            raise DuplicateBookHashError(
                f"Book with file_hash {file_hash!r} already exists "
                f"(id={existing['id']})"
            )

        try:
            cursor = connection.execute(
                """
                INSERT INTO books (title, file_path, file_hash, total_pages, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, file_path, file_hash, total_pages, status),
            )
        except sqlite3.IntegrityError as exc:
            if "books.file_hash" in str(exc):
                raise DuplicateBookHashError(
                    f"Book with file_hash {file_hash!r} already exists"
                ) from exc
            raise

        assert cursor.lastrowid is not None
        row = connection.execute(
            "SELECT * FROM books WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return _book_from_row(row)


def get_book(book_id: int, db_path: Path | None = None) -> BookRecord | None:
    with database(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM books WHERE id = ?", (book_id,)
        ).fetchone()
    return None if row is None else _book_from_row(row)


def list_books(
    include_deleted: bool = False, db_path: Path | None = None
) -> list[BookRecord]:
    with database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM books
            WHERE (? = 1 OR status <> ?)
            ORDER BY id
            """,
            (int(include_deleted), "deleted"),
        ).fetchall()
    return [_book_from_row(row) for row in rows]


def update_book_status(
    book_id: int, status: str, db_path: Path | None = None
) -> BookRecord | None:
    with database(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE books
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, book_id),
        )
        if cursor.rowcount == 0:
            return None
        row = connection.execute(
            "SELECT * FROM books WHERE id = ?", (book_id,)
        ).fetchone()
        return _book_from_row(row)


def soft_delete_book(book_id: int, db_path: Path | None = None) -> BookRecord | None:
    return update_book_status(book_id, "deleted", db_path)


def insert_pages(
    book_id: int, pages: Sequence[PageData], db_path: Path | None = None
) -> list[PageRecord]:
    with database(db_path) as connection:
        page_ids: list[int] = []
        for page in pages:
            cursor = connection.execute(
                """
                INSERT INTO pages (book_id, page_number, content, method, confidence)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    page.page_number,
                    page.content,
                    page.method,
                    page.confidence,
                ),
            )
            assert cursor.lastrowid is not None
            page_ids.append(cursor.lastrowid)

        return [
            _page_from_row(
                connection.execute(
                    "SELECT * FROM pages WHERE id = ?", (page_id,)
                ).fetchone()
            )
            for page_id in page_ids
        ]


def get_pages(
    book_id: int,
    start_page: int | None = None,
    end_page: int | None = None,
    db_path: Path | None = None,
) -> list[PageRecord]:
    sql = "SELECT * FROM pages WHERE book_id = ?"
    params: list[int] = [book_id]
    if start_page is not None:
        sql += " AND page_number >= ?"
        params.append(start_page)
    if end_page is not None:
        sql += " AND page_number <= ?"
        params.append(end_page)
    sql += " ORDER BY page_number"

    with database(db_path) as connection:
        rows = connection.execute(sql, params).fetchall()
    return [_page_from_row(row) for row in rows]


def insert_chunks(
    book_id: int, chunks: Sequence[ChunkData], db_path: Path | None = None
) -> list[ChunkRecord]:
    with database(db_path) as connection:
        chunk_ids: list[int] = []
        for chunk in chunks:
            cursor = connection.execute(
                """
                INSERT INTO chunks (book_id, chunk_index, content)
                VALUES (?, ?, ?)
                """,
                (book_id, chunk.chunk_index, chunk.content),
            )
            assert cursor.lastrowid is not None
            chunk_ids.append(cursor.lastrowid)

        return [
            _chunk_from_row(
                connection.execute(
                    "SELECT * FROM chunks WHERE id = ?", (chunk_id,)
                ).fetchone()
            )
            for chunk_id in chunk_ids
        ]


def get_chunks(book_id: int, db_path: Path | None = None) -> list[ChunkRecord]:
    with database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM chunks
            WHERE book_id = ?
            ORDER BY chunk_index
            """,
            (book_id,),
        ).fetchall()
    return [_chunk_from_row(row) for row in rows]


def insert_page_chunks(
    links: Sequence[PageChunkData], db_path: Path | None = None
) -> list[PageChunkRecord]:
    with database(db_path) as connection:
        for link in links:
            connection.execute(
                """
                INSERT INTO page_chunk (page_id, chunk_id, start_offset, end_offset)
                VALUES (?, ?, ?, ?)
                """,
                (link.page_id, link.chunk_id, link.start_offset, link.end_offset),
            )
    return [
        PageChunkRecord(
            page_id=link.page_id,
            chunk_id=link.chunk_id,
            start_offset=link.start_offset,
            end_offset=link.end_offset,
        )
        for link in links
    ]


def get_chunks_for_page(
    page_id: int, db_path: Path | None = None
) -> list[ChunkWithOffset]:
    with database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT c.*, pc.start_offset, pc.end_offset
            FROM page_chunk AS pc
            JOIN chunks AS c ON c.id = pc.chunk_id
            WHERE pc.page_id = ?
            ORDER BY c.chunk_index, pc.start_offset
            """,
            (page_id,),
        ).fetchall()
    return [
        ChunkWithOffset(
            chunk=_chunk_from_row(row),
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
        )
        for row in rows
    ]


def get_pages_for_chunk(
    chunk_id: int, db_path: Path | None = None
) -> list[PageWithOffset]:
    with database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT p.*, pc.start_offset, pc.end_offset
            FROM page_chunk AS pc
            JOIN pages AS p ON p.id = pc.page_id
            WHERE pc.chunk_id = ?
            ORDER BY p.page_number, pc.start_offset
            """,
            (chunk_id,),
        ).fetchall()
    return [
        PageWithOffset(
            page=_page_from_row(row),
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
        )
        for row in rows
    ]


def delete_book_physically(book_id: int, db_path: Path | None = None) -> None:
    with database(db_path) as connection:
        connection.execute("DELETE FROM books WHERE id = ?", (book_id,))
