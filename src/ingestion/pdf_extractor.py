from __future__ import annotations

import logging
from pathlib import Path

import pymupdf as fitz

from src.ingestion.errors import EmptyInputError, PdfReadError
from src.ingestion.models import PageText

logger = logging.getLogger(__name__)


def _open_document(path: Path) -> fitz.Document:
    try:
        return fitz.open(path)
    except Exception as exc:
        raise PdfReadError(f"Cannot open PDF: {path.name}") from exc


def extract_pages(file_path: str | Path) -> list[PageText]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    try:
        with _open_document(path) as document:
            if document.is_encrypted:
                raise PdfReadError(f"Encrypted PDF: {path.name}")
            if document.page_count == 0:
                raise EmptyInputError(f"PDF has no pages: {path.name}")

            pages: list[PageText] = []
            for number, page in enumerate(document, start=1):
                content = page.get_text("text")
                logger.debug(
                    "page extracted page_number=%d chars=%d", number, len(content)
                )
                pages.append(PageText(page_number=number, content=content))
            return pages
    except PdfReadError:
        raise
    except EmptyInputError:
        raise
    except Exception as exc:
        raise PdfReadError(f"Cannot read PDF: {path.name}") from exc


def extract_title(file_path: str | Path) -> str | None:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    try:
        with _open_document(path) as document:
            if document.is_encrypted:
                raise PdfReadError(f"Encrypted PDF: {path.name}")
            title = (document.metadata.get("title") or "").strip()
            return title or None
    except PdfReadError:
        raise
    except EmptyInputError:
        raise
    except Exception as exc:
        raise PdfReadError(f"Cannot read PDF: {path.name}") from exc
