import logging

import pytest

from src.ingestion.Extract_OCR import OcrResult, ocr_pages
from src.ingestion.errors import LowConfidenceError
from src.ingestion.pipeline import ingest_pdf


def test_ocr_start_and_finish_are_logged(
    caplog: pytest.LogCaptureFixture, make_scanned_pdf, db_path, fake_engine
) -> None:
    fake_engine.default = OcrResult("alpha beta", 92)
    caplog.set_level(logging.INFO)

    ingest_pdf(
        make_scanned_pdf(["alpha beta", "gamma delta"]),
        db_path=db_path,
        ocr_engine=fake_engine,
    )

    assert "ocr started" in caplog.text
    assert "pages_needing_ocr=2" in caplog.text
    assert "ocr finished" in caplog.text
    assert "mean_confidence=0.92" in caplog.text


def test_empty_ocr_page_logs_warning(
    caplog: pytest.LogCaptureFixture, make_scanned_pdf, fake_engine
) -> None:
    caplog.set_level(logging.WARNING)

    ocr_pages(make_scanned_pdf([""]), [1], engine=fake_engine)

    assert "ocr page empty" in caplog.text
    assert "page_number=1" in caplog.text


def test_low_confidence_logs_one_error_with_details(
    caplog: pytest.LogCaptureFixture, make_scanned_pdf, db_path, fake_engine
) -> None:
    fake_engine.default = OcrResult("unclear", 60)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(LowConfidenceError):
        ingest_pdf(
            make_scanned_pdf(["unclear"]),
            db_path=db_path,
            ocr_engine=fake_engine,
        )

    errors = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].exc_info is not None
    assert "page_number=1" in caplog.text
    assert "confidence=60" in caplog.text
    assert "threshold=80.0" in caplog.text


def test_logs_never_contain_ocr_text(
    caplog: pytest.LogCaptureFixture, make_scanned_pdf, db_path, fake_engine
) -> None:
    sentence = "SECRET_OCR_TEXT_987"
    fake_engine.default = OcrResult(sentence, 92)
    caplog.set_level(logging.DEBUG)

    ingest_pdf(
        make_scanned_pdf(["alpha beta"]),
        db_path=db_path,
        ocr_engine=fake_engine,
    )

    assert sentence not in caplog.text


def test_per_page_confidence_is_logged_at_debug(
    caplog: pytest.LogCaptureFixture, make_scanned_pdf, fake_engine
) -> None:
    fake_engine.default = OcrResult("alpha beta", 92.5)
    caplog.set_level(logging.DEBUG)

    ocr_pages(make_scanned_pdf(["alpha beta"]), [1], engine=fake_engine)

    assert (
        "ocr page completed page_number=1 confidence=92.5 characters=10"
        in caplog.text
    )
