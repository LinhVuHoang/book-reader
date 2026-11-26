import logging

import pytest

from src.database.repository import (
    get_book,
    get_chunks,
    get_chunks_for_page,
    get_pages,
    get_pages_for_chunk,
    list_books,
)
from src.ingestion.chunker import chunk_pages
from src.ingestion.errors import DuplicateBookError, NoTextError
from src.ingestion.pdf_extractor import PageText
from src.ingestion.pipeline import ingest_pdf


def _expected_chunks(book_id: int, db_path, chunk_size: int, overlap_size: int):
    pages = get_pages(book_id, db_path=db_path)
    return chunk_pages(
        [PageText(page_number=page.page_number, content=page.content) for page in pages],
        chunk_size,
        overlap_size,
    )


def test_ingest_pdf_stores_rows_and_completes(make_pdf, db_path) -> None:
    path = make_pdf(["alpha beta", "gamma delta"], name="book.pdf")

    book_id = ingest_pdf(
        path, db_path=db_path, chunk_size=8, overlap_size=2
    )

    book = get_book(book_id, db_path=db_path)
    assert book is not None
    assert book.status == "completed"
    assert book.total_pages == 2
    assert len(book.file_hash) == 64
    assert book.title

    pages = get_pages(book_id, db_path=db_path)
    assert len(pages) == 2
    assert all(page.method == "text" for page in pages)
    assert all(page.confidence is None for page in pages)

    expected = _expected_chunks(book_id, db_path, 8, 2)
    stored_chunks = get_chunks(book_id, db_path=db_path)
    assert [chunk.content for chunk in stored_chunks] == [
        chunk.content for chunk in expected
    ]

    for stored, spec in zip(stored_chunks, expected):
        links = get_pages_for_chunk(stored.id, db_path=db_path)
        assert [
            (link.page.page_number, link.start_offset, link.end_offset)
            for link in links
        ] == [
            (span.page_number, span.start_offset, span.end_offset)
            for span in spec.spans
        ]
        assert (
            "".join(
                link.page.content[link.start_offset : link.end_offset]
                for link in links
            )
            == stored.content
        )


def test_empty_pages_are_stored_without_links(make_pdf, db_path) -> None:
    book_id = ingest_pdf(make_pdf(["alpha", "", "gamma"]), db_path=db_path)

    pages = get_pages(book_id, db_path=db_path)
    assert len(pages) == 3
    assert pages[1].content == ""
    assert get_chunks_for_page(pages[1].id, db_path=db_path) == []


def test_duplicate_ingest_raises_and_creates_no_extra_rows(make_pdf, db_path) -> None:
    path = make_pdf(["alpha"])

    ingest_pdf(path, db_path=db_path)

    with pytest.raises(DuplicateBookError):
        ingest_pdf(path, db_path=db_path)

    assert len(list_books(include_deleted=True, db_path=db_path)) == 1


def test_no_text_pdf_raises_and_marks_book_failed(make_pdf, db_path) -> None:
    with pytest.raises(NoTextError):
        ingest_pdf(make_pdf(["", ""]), db_path=db_path)

    books = list_books(include_deleted=True, db_path=db_path)
    assert len(books) == 1
    assert books[0].status == "failed"
    assert len(get_pages(books[0].id, db_path=db_path)) == 2


def test_custom_chunk_parameters_are_respected(make_pdf, db_path) -> None:
    path = make_pdf(["abcdefghij" * 5])

    book_id = ingest_pdf(path, db_path=db_path, chunk_size=12, overlap_size=3)

    expected = _expected_chunks(book_id, db_path, 12, 3)
    stored = get_chunks(book_id, db_path=db_path)
    assert len(stored) > 1
    assert [chunk.content for chunk in stored] == [
        chunk.content for chunk in expected
    ]


def test_saving_failure_marks_book_failed(
    monkeypatch: pytest.MonkeyPatch, make_pdf, db_path
) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.ingestion.pipeline.insert_chunks", fail)

    with pytest.raises(RuntimeError):
        ingest_pdf(make_pdf(["alpha"]), db_path=db_path)

    books = list_books(include_deleted=True, db_path=db_path)
    assert len(books) == 1
    assert books[0].status == "failed"


def test_successful_ingest_logs_start_and_completion(
    caplog: pytest.LogCaptureFixture, make_pdf, db_path
) -> None:
    caplog.set_level(logging.INFO)

    book_id = ingest_pdf(make_pdf(["alpha"]), db_path=db_path)

    assert "ingestion started" in caplog.text
    assert "book completed" in caplog.text
    assert f"book_id={book_id}" in caplog.text


def test_empty_page_logs_warning_with_page_number(
    caplog: pytest.LogCaptureFixture, make_pdf, db_path
) -> None:
    caplog.set_level(logging.WARNING)

    ingest_pdf(make_pdf(["alpha", "", "gamma"]), db_path=db_path)

    assert "empty page" in caplog.text
    assert "page_number=2" in caplog.text


def test_duplicate_logs_warning_with_existing_book_id(
    caplog: pytest.LogCaptureFixture, make_pdf, db_path
) -> None:
    path = make_pdf(["alpha"])
    first_id = ingest_pdf(path, db_path=db_path)
    caplog.set_level(logging.WARNING)
    caplog.clear()

    with pytest.raises(DuplicateBookError):
        ingest_pdf(path, db_path=db_path)

    assert "duplicate file hash" in caplog.text
    assert f"book_id={first_id}" in caplog.text


def test_failure_logs_one_error_with_traceback(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    make_pdf,
    db_path,
) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.ingestion.pipeline.insert_chunks", fail)
    caplog.set_level(logging.ERROR)

    with pytest.raises(RuntimeError):
        ingest_pdf(make_pdf(["alpha"]), db_path=db_path)

    errors = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].exc_info is not None
    assert list_books(include_deleted=True, db_path=db_path)[0].status == "failed"


def test_logs_never_contain_book_text(
    caplog: pytest.LogCaptureFixture, make_pdf, db_path
) -> None:
    sentence = "SECRET_SENTENCE_123"
    caplog.set_level(logging.DEBUG)

    ingest_pdf(make_pdf([sentence]), db_path=db_path)

    assert sentence not in caplog.text
