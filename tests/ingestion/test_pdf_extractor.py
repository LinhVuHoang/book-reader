from pathlib import Path

import pytest

from src.ingestion.errors import PdfReadError
from src.ingestion.pdf_extractor import extract_pages


def test_three_pages_are_returned_in_order(make_pdf) -> None:
    path = make_pdf(["alpha", "beta", "gamma"])

    pages = extract_pages(path)

    assert [page.page_number for page in pages] == [1, 2, 3]
    assert "alpha" in pages[0].content
    assert "beta" in pages[1].content
    assert "gamma" in pages[2].content


def test_empty_page_is_kept(make_pdf) -> None:
    pages = extract_pages(make_pdf(["alpha", "", "gamma"]))

    assert [page.page_number for page in pages] == [1, 2, 3]
    assert pages[1].content == ""


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        extract_pages(tmp_path / "missing.pdf")


def test_corrupt_pdf_raises_pdf_read_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a pdf")

    with pytest.raises(PdfReadError):
        extract_pages(path)
