from pathlib import Path

import pymupdf as fitz
import pytest
from PIL import Image

from src.ingestion.errors import EmptyInputError, InvalidFormatError
from src.ingestion.image_to_pdf import images_to_pdf
from src.ingestion.validators import validate_pdf_file


def _image(tmp_path: Path, name: str, color: str = "white") -> Path:
    path = tmp_path / name
    Image.new("RGB", (80, 120), color).save(path)
    return path


def test_one_image_becomes_one_page(tmp_path: Path) -> None:
    image = _image(tmp_path, "one.png")

    output = images_to_pdf([image], tmp_path / "one.pdf")

    assert output.exists()
    with fitz.open(output) as document:
        assert document.page_count == 1


def test_three_images_keep_order(tmp_path: Path) -> None:
    images = [
        _image(tmp_path, f"{index}.png", color)
        for index, color in enumerate(["red", "green", "blue"])
    ]

    output = images_to_pdf(images, tmp_path / "three.pdf")

    with fitz.open(output) as document:
        assert document.page_count == 3
        pixmaps = [page.get_pixmap(dpi=10) for page in document]
        assert [pixmap.pixel(1, 1)[:3] for pixmap in pixmaps] == [
            (255, 0, 0),
            (0, 128, 0),
            (0, 0, 255),
        ]
    assert validate_pdf_file(output) == output


def test_empty_list_raises_empty_input(tmp_path: Path) -> None:
    with pytest.raises(EmptyInputError):
        images_to_pdf([], tmp_path / "empty.pdf")


def test_zero_byte_image_raises_empty_input(tmp_path: Path) -> None:
    image = tmp_path / "zero.png"
    image.write_bytes(b"")

    with pytest.raises(EmptyInputError):
        images_to_pdf([image], tmp_path / "out.pdf")


def test_unsupported_suffix_raises_invalid_format(tmp_path: Path) -> None:
    image = tmp_path / "page.gif"
    image.write_bytes(b"content")

    with pytest.raises(InvalidFormatError):
        images_to_pdf([image], tmp_path / "out.pdf")


def test_corrupt_image_raises_invalid_format(tmp_path: Path) -> None:
    image = tmp_path / "broken.png"
    image.write_bytes(b"not an image")

    with pytest.raises(InvalidFormatError):
        images_to_pdf([image], tmp_path / "out.pdf")


def test_missing_image_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        images_to_pdf([tmp_path / "missing.png"], tmp_path / "out.pdf")


def test_existing_output_raises_file_exists(tmp_path: Path) -> None:
    image = _image(tmp_path, "one.png")
    output = tmp_path / "out.pdf"
    output.write_bytes(b"%PDF-")

    with pytest.raises(FileExistsError):
        images_to_pdf([image], output)


def test_non_pdf_output_raises_invalid_format(tmp_path: Path) -> None:
    image = _image(tmp_path, "one.png")

    with pytest.raises(InvalidFormatError):
        images_to_pdf([image], tmp_path / "out.txt")
