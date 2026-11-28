from __future__ import annotations

from pathlib import Path

import pymupdf as fitz
from PIL import Image

from src.ingestion.errors import EmptyInputError, InvalidFormatError
from src.ingestion.validators import IMAGE_SUFFIXES


def images_to_pdf(
    image_paths: list[str | Path], output_path: str | Path
) -> Path:
    if not image_paths:
        raise EmptyInputError("No images provided")

    output = Path(output_path)
    if output.suffix.lower() != ".pdf":
        raise InvalidFormatError(f"Output must end with .pdf: {output.name}")
    if output.exists():
        raise FileExistsError(f"Output file already exists: {output}")

    for raw_path in image_paths:
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")
        suffix = path.suffix.lower()
        if suffix not in IMAGE_SUFFIXES:
            raise InvalidFormatError(f"Unsupported image format: {path.name}")
        if path.stat().st_size == 0:
            raise EmptyInputError(f"Empty image file: {path.name}")

    with fitz.open() as document:
        for raw_path in image_paths:
            path = Path(raw_path)
            try:
                with Image.open(path) as image:
                    image.verify()
            except Exception as exc:
                raise InvalidFormatError(f"Unreadable image: {path.name}") from exc
            try:
                with fitz.open(path) as image_document:
                    pdf_bytes = image_document.convert_to_pdf()
                with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf_document:
                    document.insert_pdf(pdf_document, from_page=0, to_page=0)
            except InvalidFormatError:
                raise
            except Exception as exc:
                raise InvalidFormatError(f"Cannot convert image: {path.name}") from exc
        document.save(output)

    return output
