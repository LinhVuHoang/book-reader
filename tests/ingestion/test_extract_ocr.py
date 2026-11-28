from pathlib import Path

import pytest
import pytesseract
from PIL import Image

from src.ingestion.Extract_OCR import (
    OcrResult,
    TesseractEngine,
    normalize_ocr_text,
    ocr_pages,
    result_from_data,
)
from src.ingestion.errors import (
    IngestionError,
    LowConfidenceError,
    NoTextError,
    OcrEngineError,
)
from src.ingestion.pipeline import ingest_pdf


class FailingEngine:
    def recognize(self, image: Image.Image) -> OcrResult:
        raise RuntimeError("engine down")


def test_only_requested_pages_are_ocrd(make_pdf, fake_engine) -> None:
    fake_engine.results = [OcrResult("hello", 92.5)]

    pages = ocr_pages(make_pdf(["one", "two", "three"]), [2], engine=fake_engine)

    assert len(fake_engine.calls) == 1
    assert [page.page_number for page in pages] == [2]
    assert pages[0].content == "hello"
    assert pages[0].method == "ocr"
    assert pages[0].confidence == 0.925


def test_empty_ocr_result_is_not_an_error(make_pdf, fake_engine) -> None:
    fake_engine.results = [OcrResult("", None)]

    pages = ocr_pages(make_pdf(["one"]), [1], engine=fake_engine)

    assert pages[0].content == ""
    assert pages[0].confidence is None


def test_ocr_text_is_normalized(make_pdf, fake_engine) -> None:
    fake_engine.results = [
        OcrResult("  first  \r\nsecond   \r\n\n\n\nthird  \n", 90)
    ]

    pages = ocr_pages(make_pdf(["one"]), [1], engine=fake_engine)

    assert pages[0].content == "  first\nsecond\n\nthird"
    assert normalize_ocr_text("a\r\nb\r\n\r\n\r\nc") == "a\nb\n\nc"


def test_engine_failure_is_wrapped(make_pdf) -> None:
    with pytest.raises(OcrEngineError):
        ocr_pages(make_pdf(["one"]), [1], engine=FailingEngine())


def test_missing_tesseract_raises_ocr_engine_error(tmp_path: Path) -> None:
    with pytest.raises(OcrEngineError):
        TesseractEngine(
            languages="eng", tesseract_cmd=str(tmp_path / "not_installed.exe")
        )


def test_missing_language_pack_raises_ocr_engine_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pytesseract, "get_languages", lambda config="": ["eng"])

    with pytest.raises(OcrEngineError):
        TesseractEngine(languages="eng+vie")


def test_result_from_data_ignores_non_words_and_groups_lines() -> None:
    data = {
        "text": ["Hello", "world", "", "Second", "line", "", "Para", "two", ""],
        "conf": ["90", "80", "-1", "95", "85", "-1", "70", "60", "-1"],
        "block_num": [1, 1, 1, 1, 1, 1, 2, 2, 2],
        "par_num": [1, 1, 1, 2, 2, 2, 1, 1, 1],
        "line_num": [1, 1, 1, 1, 1, 1, 1, 1, 1],
    }

    result = result_from_data(data)

    assert result.text == "Hello world\n\nSecond line\n\nPara two"
    assert result.confidence == 80


def test_result_from_data_without_words_has_no_confidence() -> None:
    result = result_from_data(
        {
            "text": ["", ""],
            "conf": ["-1", "-1"],
            "block_num": [1, 1],
            "par_num": [1, 1],
            "line_num": [1, 1],
        }
    )

    assert result == OcrResult("", None)


@pytest.mark.parametrize(
    ("score", "accepted"), [(79.99, False), (80.0, True), (100, True)]
)
def test_confidence_threshold_is_inclusive(
    make_pdf, fake_engine, score: float, accepted: bool
) -> None:
    fake_engine.results = [OcrResult("text", score)]

    if accepted:
        pages = ocr_pages(make_pdf(["one"]), [1], engine=fake_engine)
        assert pages[0].confidence == pytest.approx(score / 100)
    else:
        with pytest.raises(LowConfidenceError):
            ocr_pages(make_pdf(["one"]), [1], engine=fake_engine)


def test_low_confidence_error_carries_page_and_scores(make_pdf, fake_engine) -> None:
    fake_engine.results = [OcrResult("first", 95), OcrResult("second", 60)]

    with pytest.raises(LowConfidenceError) as exc_info:
        ocr_pages(make_pdf(["one", "two"]), [1, 2], engine=fake_engine)

    error = exc_info.value
    assert isinstance(error, IngestionError)
    assert error.page_number == 2
    assert error.confidence == 60
    assert error.threshold == 80.0


def test_custom_threshold_is_respected(make_pdf, fake_engine) -> None:
    fake_engine.results = [OcrResult("text", 85)]

    with pytest.raises(LowConfidenceError):
        ocr_pages(
            make_pdf(["one"]), [1], engine=fake_engine, min_confidence=90
        )

    fake_engine.calls.clear()
    pages = ocr_pages(
        make_pdf(["one"]), [1], engine=fake_engine, min_confidence=80
    )
    assert pages[0].confidence == pytest.approx(0.85)


@pytest.mark.ocr
def test_real_engine_reads_english_text(make_text_image, real_engine) -> None:
    with Image.open(make_text_image("HELLO WORLD")) as image:
        result = real_engine.recognize(image)

    assert "HELLO" in result.text.upper()
    assert result.confidence is not None
    assert result.confidence >= 80


@pytest.mark.ocr
def test_real_engine_scores_clean_scanned_page(
    make_scanned_pdf, real_engine
) -> None:
    pages = ocr_pages(make_scanned_pdf(["HELLO WORLD"]), [1], engine=real_engine)

    assert "HELLO" in pages[0].content.upper()
    assert pages[0].confidence is not None
    assert pages[0].confidence >= 0.8


@pytest.mark.ocr
def test_real_engine_end_to_end(make_scanned_pdf, db_path, real_engine) -> None:
    book_id = ingest_pdf(
        make_scanned_pdf(["HELLO WORLD"]),
        db_path=db_path,
        ocr_engine=real_engine,
    )

    from src.database.repository import get_book, get_pages

    assert get_book(book_id, db_path=db_path).status == "completed"
    pages = get_pages(book_id, db_path=db_path)
    assert all(page.method == "ocr" for page in pages)
    assert all(page.confidence >= 0.8 for page in pages)


@pytest.mark.ocr
def test_real_engine_blank_page_has_no_text(
    make_scanned_pdf, db_path, real_engine
) -> None:
    with pytest.raises(NoTextError):
        ingest_pdf(
            make_scanned_pdf([""]), db_path=db_path, ocr_engine=real_engine
        )
