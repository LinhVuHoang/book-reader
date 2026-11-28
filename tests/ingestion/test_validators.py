from pathlib import Path

import pytest

from src.ingestion.errors import (
    EmptyInputError,
    InvalidFormatError,
    PdfReadError,
)
from src.ingestion.pdf_extractor import extract_pages
from src.ingestion.validators import validate_pdf_file


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        validate_pdf_file(tmp_path / "missing.pdf")


def test_directory_raises_invalid_format(tmp_path: Path) -> None:
    with pytest.raises(InvalidFormatError):
        validate_pdf_file(tmp_path)


def test_empty_pdf_raises_empty_input(tmp_path: Path) -> None:
    path = tmp_path / "empty.pdf"
    path.write_bytes(b"")

    with pytest.raises(EmptyInputError):
        validate_pdf_file(path)


@pytest.mark.parametrize("suffix", [".txt", ".docx"])
def test_non_pdf_suffix_raises_invalid_format(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"book{suffix}"
    path.write_text("content")

    with pytest.raises(InvalidFormatError):
        validate_pdf_file(path)


@pytest.mark.parametrize("suffix", [".png", ".jpg"])
def test_image_suffix_mentions_conversion(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"page{suffix}"
    path.write_bytes(b"content")

    with pytest.raises(InvalidFormatError, match="images_to_pdf"):
        validate_pdf_file(path)


def test_png_renamed_to_pdf_raises_invalid_format(tmp_path: Path) -> None:
    path = tmp_path / "fake.pdf"
    path.write_bytes(b"\x89PNG\r\n\x1a\ncontent")

    with pytest.raises(InvalidFormatError):
        validate_pdf_file(path)


def test_valid_header_but_corrupt_pdf_raises_pdf_read_error(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.4\nbroken")

    assert validate_pdf_file(path) == path
    with pytest.raises(PdfReadError):
        extract_pages(path)


def test_zero_page_pdf_raises_empty_input(make_zero_page_pdf) -> None:
    path = make_zero_page_pdf()

    assert validate_pdf_file(path) == path
    with pytest.raises(EmptyInputError):
        extract_pages(path)


def test_uppercase_pdf_suffix_is_accepted(make_pdf) -> None:
    path = make_pdf(["alpha"], name="BOOK.PDF")

    assert validate_pdf_file(path) == path
