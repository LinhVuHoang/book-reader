from __future__ import annotations

from pathlib import Path

from src.ingestion.errors import EmptyInputError, InvalidFormatError

IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
)


def validate_pdf_file(file_path: str | Path) -> Path:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")
    if not path.is_file():
        raise InvalidFormatError(f"Not a regular file: {path.name}")

    suffix = path.suffix.lower()
    if suffix != ".pdf":
        if suffix in IMAGE_SUFFIXES:
            raise InvalidFormatError(
                f"Image file given directly: {path.name}; "
                "convert it with images_to_pdf first"
            )
        raise InvalidFormatError(f"Not a PDF file: {path.name}")

    if path.stat().st_size == 0:
        raise EmptyInputError(f"Empty PDF file: {path.name}")

    with path.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise InvalidFormatError(f"Invalid PDF header: {path.name}")

    return path
