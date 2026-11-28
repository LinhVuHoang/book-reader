import logging
import sqlite3
from pathlib import Path

import pymupdf as fitz
import pytest

from src.database.repository import (
    get_book,
    get_chunks,
    get_chunks_for_page,
    get_pages,
    get_pages_for_chunk,
    list_books,
)
from src.ingestion.Extract_OCR import OcrResult
from src.ingestion.chunker import chunk_pages
from src.ingestion.errors import (
    DuplicateBookError,
    EmptyInputError,
    InvalidFormatError,
    LowConfidenceError,
    NoTextError,
)
from src.ingestion.image_to_pdf import images_to_pdf
from src.ingestion.models import PageText
from src.ingestion.pipeline import ingest_pdf


def _assert_no_rows(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        for table in ("books", "pages", "chunks", "page_chunk"):
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            assert count == 0


def _make_mixed_pdf(tmp_path: Path, native_pdf: Path, scanned_pdf: Path) -> Path:
    path = tmp_path / "mixed.pdf"
    with (
        fitz.open(native_pdf) as native,
        fitz.open(scanned_pdf) as scanned,
        fitz.open() as document,
    ):
        document.insert_pdf(native)
        document.insert_pdf(scanned)
        document.save(path)
    return path


def _expected_chunks(book_id: int, db_path, chunk_size: int, overlap_size: int):
    pages = get_pages(book_id, db_path=db_path)
    return chunk_pages(
        [PageText(page_number=page.page_number, content=page.content) for page in pages],
        chunk_size,
        overlap_size,
    )


def test_ingest_pdf_stores_rows_and_completes(
    make_pdf, db_path, fake_engine
) -> None:
    path = make_pdf(["alpha beta", "gamma delta"], name="book.pdf")

    book_id = ingest_pdf(
        path,
        db_path=db_path,
        chunk_size=8,
        overlap_size=2,
        ocr_engine=fake_engine,
    )
    assert fake_engine.calls == []

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


def test_empty_pages_are_stored_without_links(
    make_pdf, db_path, fake_engine
) -> None:
    book_id = ingest_pdf(
        make_pdf(["alpha", "", "gamma"]),
        db_path=db_path,
        ocr_engine=fake_engine,
    )

    pages = get_pages(book_id, db_path=db_path)
    assert len(pages) == 3
    assert pages[1].content == ""
    assert pages[1].method == "ocr"
    assert pages[1].confidence is None
    assert get_chunks_for_page(pages[1].id, db_path=db_path) == []


def test_duplicate_ingest_raises_and_creates_no_extra_rows(make_pdf, db_path) -> None:
    path = make_pdf(["alpha"])

    ingest_pdf(path, db_path=db_path)

    with pytest.raises(DuplicateBookError):
        ingest_pdf(path, db_path=db_path)

    assert len(list_books(include_deleted=True, db_path=db_path)) == 1


def test_no_text_pdf_raises_and_saves_nothing(
    make_pdf, db_path, fake_engine
) -> None:
    with pytest.raises(NoTextError):
        ingest_pdf(make_pdf(["", ""]), db_path=db_path, ocr_engine=fake_engine)

    _assert_no_rows(db_path)


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
    caplog: pytest.LogCaptureFixture, make_pdf, db_path, fake_engine
) -> None:
    caplog.set_level(logging.WARNING)

    ingest_pdf(
        make_pdf(["alpha", "", "gamma"]),
        db_path=db_path,
        ocr_engine=fake_engine,
    )

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


def test_scanned_pdf_is_ocrd_and_stored(
    make_scanned_pdf, db_path, fake_engine
) -> None:
    fake_engine.results = [OcrResult("alpha beta", 92.5)]

    book_id = ingest_pdf(
        make_scanned_pdf(["alpha beta"]),
        db_path=db_path,
        chunk_size=8,
        overlap_size=2,
        ocr_engine=fake_engine,
    )

    book = get_book(book_id, db_path=db_path)
    assert book is not None
    assert book.status == "completed"
    pages = get_pages(book_id, db_path=db_path)
    assert len(pages) == 1
    assert pages[0].method == "ocr"
    assert pages[0].confidence == pytest.approx(0.925)
    for chunk in get_chunks(book_id, db_path=db_path):
        links = get_pages_for_chunk(chunk.id, db_path=db_path)
        assert (
            "".join(
                link.page.content[link.start_offset : link.end_offset]
                for link in links
            )
            == chunk.content
        )


def test_mixed_pdf_keeps_page_methods(
    tmp_path: Path, make_pdf, make_scanned_pdf, db_path, fake_engine
) -> None:
    fake_engine.results = [OcrResult("scanned words", 90)]
    path = _make_mixed_pdf(
        tmp_path, make_pdf(["native words"]), make_scanned_pdf(["scanned words"])
    )

    book_id = ingest_pdf(path, db_path=db_path, ocr_engine=fake_engine)

    pages = get_pages(book_id, db_path=db_path)
    assert [page.method for page in pages] == ["text", "ocr"]
    assert pages[0].confidence is None
    assert pages[1].confidence == pytest.approx(0.9)
    for chunk in get_chunks(book_id, db_path=db_path):
        links = get_pages_for_chunk(chunk.id, db_path=db_path)
        assert (
            "".join(
                link.page.content[link.start_offset : link.end_offset]
                for link in links
            )
            == chunk.content
        )


def test_low_confidence_saves_nothing(
    make_scanned_pdf, db_path, fake_engine
) -> None:
    fake_engine.results = [OcrResult("unclear", 60)]

    with pytest.raises(LowConfidenceError) as exc_info:
        ingest_pdf(
            make_scanned_pdf(["unclear"]), db_path=db_path, ocr_engine=fake_engine
        )

    assert exc_info.value.page_number == 1
    assert exc_info.value.confidence == 60
    _assert_no_rows(db_path)


def test_scanned_pdf_without_any_text_saves_nothing(
    make_scanned_pdf, db_path, fake_engine
) -> None:
    with pytest.raises(NoTextError):
        ingest_pdf(
            make_scanned_pdf(["", ""]), db_path=db_path, ocr_engine=fake_engine
        )

    _assert_no_rows(db_path)


def test_blank_ocr_page_is_stored_without_links(
    make_scanned_pdf, db_path, fake_engine
) -> None:
    fake_engine.results = [
        OcrResult("alpha beta", 90),
        OcrResult("", None),
        OcrResult("gamma delta", 95),
    ]

    book_id = ingest_pdf(
        make_scanned_pdf(["alpha beta", "", "gamma delta"]),
        db_path=db_path,
        ocr_engine=fake_engine,
    )

    pages = get_pages(book_id, db_path=db_path)
    assert pages[1].content == ""
    assert pages[1].method == "ocr"
    assert pages[1].confidence is None
    assert get_chunks_for_page(pages[1].id, db_path=db_path) == []


def test_zero_byte_file_saves_nothing(tmp_path: Path, db_path) -> None:
    path = tmp_path / "empty.pdf"
    path.write_bytes(b"")

    with pytest.raises(EmptyInputError):
        ingest_pdf(path, db_path=db_path)

    _assert_no_rows(db_path)


def test_wrong_extension_saves_nothing(
    make_text_image, db_path
) -> None:
    path = make_text_image("alpha")

    with pytest.raises(InvalidFormatError):
        ingest_pdf(path, db_path=db_path)

    _assert_no_rows(db_path)


def test_fake_pdf_saves_nothing(
    tmp_path: Path, make_text_image, db_path
) -> None:
    path = tmp_path / "fake.pdf"
    path.write_bytes(make_text_image("alpha").read_bytes())

    with pytest.raises(InvalidFormatError):
        ingest_pdf(path, db_path=db_path)

    _assert_no_rows(db_path)


def test_zero_page_pdf_saves_nothing(make_zero_page_pdf, db_path) -> None:
    with pytest.raises(EmptyInputError):
        ingest_pdf(make_zero_page_pdf(), db_path=db_path)

    _assert_no_rows(db_path)


def test_duplicate_scan_does_not_run_ocr(
    make_scanned_pdf, db_path, fake_engine
) -> None:
    fake_engine.default = OcrResult("alpha", 90)
    path = make_scanned_pdf(["alpha"])
    ingest_pdf(path, db_path=db_path, ocr_engine=fake_engine)
    fake_engine.calls.clear()

    with pytest.raises(DuplicateBookError):
        ingest_pdf(path, db_path=db_path, ocr_engine=fake_engine)

    assert fake_engine.calls == []
    assert len(list_books(include_deleted=True, db_path=db_path)) == 1


def test_image_converted_to_pdf_can_be_ingested(
    tmp_path: Path, make_text_image, db_path, fake_engine
) -> None:
    fake_engine.results = [OcrResult("alpha beta", 92)]
    image = make_text_image("alpha beta")
    pdf = images_to_pdf([image], tmp_path / "from_image.pdf")

    book_id = ingest_pdf(pdf, db_path=db_path, ocr_engine=fake_engine)

    assert get_pages(book_id, db_path=db_path)[0].method == "ocr"
    with pytest.raises(InvalidFormatError):
        ingest_pdf(image, db_path=db_path, ocr_engine=fake_engine)
