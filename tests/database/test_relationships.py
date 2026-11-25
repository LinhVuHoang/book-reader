from pathlib import Path

from src.database.repository import (
    BookRecord,
    ChunkData,
    PageChunkData,
    PageData,
    get_chunks_for_page,
    get_pages_for_chunk,
    insert_chunks,
    insert_page_chunks,
    insert_pages,
)


def test_chunk_can_be_associated_with_multiple_pages(
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
    chunk = insert_chunks(
        book.id, [ChunkData(chunk_index=0, content="abcdef")], db_path=db_path
    )[0]
    insert_page_chunks(
        [
            PageChunkData(page_id=pages[0].id, chunk_id=chunk.id, start_offset=0, end_offset=3),
            PageChunkData(page_id=pages[1].id, chunk_id=chunk.id, start_offset=0, end_offset=3),
        ],
        db_path=db_path,
    )

    result = get_pages_for_chunk(chunk.id, db_path=db_path)

    assert [(item.page.id, item.start_offset, item.end_offset) for item in result] == [
        (pages[0].id, 0, 3),
        (pages[1].id, 0, 3),
    ]


def test_page_can_be_associated_with_multiple_chunks(
    db_path: Path, book: BookRecord
) -> None:
    page = insert_pages(
        book.id,
        [PageData(page_number=1, content="abcdef", method="text")],
        db_path=db_path,
    )[0]
    chunks = insert_chunks(
        book.id,
        [
            ChunkData(chunk_index=0, content="abc"),
            ChunkData(chunk_index=1, content="def"),
        ],
        db_path=db_path,
    )
    insert_page_chunks(
        [
            PageChunkData(
                page_id=page.id, chunk_id=chunks[0].id, start_offset=0, end_offset=3
            ),
            PageChunkData(
                page_id=page.id, chunk_id=chunks[1].id, start_offset=3, end_offset=6
            ),
        ],
        db_path=db_path,
    )

    result = get_chunks_for_page(page.id, db_path=db_path)

    assert [(item.chunk.id, item.start_offset, item.end_offset) for item in result] == [
        (chunks[0].id, 0, 3),
        (chunks[1].id, 3, 6),
    ]


def test_offsets_are_stored_independently_per_relationship(
    db_path: Path, book: BookRecord
) -> None:
    pages = insert_pages(
        book.id,
        [
            PageData(page_number=1, content="0123456789", method="text"),
            PageData(page_number=2, content="abcdefghij", method="text"),
        ],
        db_path=db_path,
    )
    chunks = insert_chunks(
        book.id,
        [
            ChunkData(chunk_index=0, content="0123abc"),
            ChunkData(chunk_index=1, content="4567def"),
        ],
        db_path=db_path,
    )
    insert_page_chunks(
        [
            PageChunkData(
                page_id=pages[0].id, chunk_id=chunks[0].id, start_offset=0, end_offset=4
            ),
            PageChunkData(
                page_id=pages[0].id, chunk_id=chunks[1].id, start_offset=4, end_offset=8
            ),
            PageChunkData(
                page_id=pages[1].id, chunk_id=chunks[0].id, start_offset=0, end_offset=3
            ),
            PageChunkData(
                page_id=pages[1].id, chunk_id=chunks[1].id, start_offset=3, end_offset=6
            ),
        ],
        db_path=db_path,
    )

    first = get_pages_for_chunk(chunks[0].id, db_path=db_path)
    second = get_pages_for_chunk(chunks[1].id, db_path=db_path)

    assert [(item.page.id, item.start_offset, item.end_offset) for item in first] == [
        (pages[0].id, 0, 4),
        (pages[1].id, 0, 3),
    ]
    assert [(item.page.id, item.start_offset, item.end_offset) for item in second] == [
        (pages[0].id, 4, 8),
        (pages[1].id, 3, 6),
    ]


def test_offsets_use_python_unicode_indexing(
    db_path: Path, book: BookRecord
) -> None:
    content = "Tiếng Việt"
    page = insert_pages(
        book.id,
        [PageData(page_number=1, content=content, method="text")],
        db_path=db_path,
    )[0]
    chunk = insert_chunks(
        book.id, [ChunkData(chunk_index=0, content="Việt")], db_path=db_path
    )[0]
    start = content.index("Việt")
    end = start + len("Việt")
    insert_page_chunks(
        [
            PageChunkData(
                page_id=page.id,
                chunk_id=chunk.id,
                start_offset=start,
                end_offset=end,
            )
        ],
        db_path=db_path,
    )

    result = get_pages_for_chunk(chunk.id, db_path=db_path)

    assert (
        result[0].page.content[result[0].start_offset : result[0].end_offset] == "Việt"
    )
