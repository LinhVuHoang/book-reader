from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Protocol

from PIL import Image

from config import settings
from src.database.repository import (
    ChunkData,
    PageChunkData,
    PageData,
    create_book,
    insert_chunks,
    insert_page_chunks,
    insert_pages,
    list_books,
    update_book_status,
)
from src.ingestion.Extract_OCR import OcrResult, ocr_pages
from src.ingestion.chunker import chunk_pages, merge_pages
from src.ingestion.errors import (
    DuplicateBookError,
    LowConfidenceError,
    NoTextError,
)
from src.ingestion.models import PageText
from src.ingestion.pdf_extractor import extract_pages, extract_title
from src.ingestion.validators import validate_pdf_file

logger = logging.getLogger(__name__)


class OcrEngineLike(Protocol):
    def recognize(self, image: Image.Image) -> OcrResult: ...


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ingest_pdf(
    file_path: str | Path,
    db_path: Path | None = None,
    chunk_size: int | None = None,
    overlap_size: int | None = None,
    ocr_engine: OcrEngineLike | None = None,
) -> int:
    started = time.perf_counter()
    try:
        path = validate_pdf_file(file_path)
        effective_chunk_size = (
            settings.CHUNK_SIZE if chunk_size is None else chunk_size
        )
        effective_overlap = (
            settings.CHUNK_OVERLAP if overlap_size is None else overlap_size
        )

        logger.info(
            "ingestion started file_name=%s chunk_size=%d overlap_size=%d",
            path.name,
            effective_chunk_size,
            effective_overlap,
        )

        file_hash = _sha256(path)
        logger.info("file hash computed file_name=%s", path.name)

        existing = next(
            (
                book
                for book in list_books(include_deleted=True, db_path=db_path)
                if book.file_hash == file_hash
            ),
            None,
        )
        if existing is not None:
            logger.warning(
                "duplicate file hash file_name=%s book_id=%d", path.name, existing.id
            )
            raise DuplicateBookError(f"PDF already ingested: {path.name}")

        pages = extract_pages(path)
        logger.info("pages extracted file_name=%s count=%d", path.name, len(pages))

        ocr_numbers = [
            page.page_number for page in pages if not page.content.strip()
        ]
        for page in pages:
            if not page.content.strip():
                logger.warning(
                    "empty page file_name=%s page_number=%d",
                    path.name,
                    page.page_number,
                )

        ocr_pages_result: list[PageText] = []
        if ocr_numbers:
            languages = getattr(ocr_engine, "languages", settings.OCR_LANGUAGES)
            logger.info(
                "ocr started file_name=%s pages_needing_ocr=%d languages=%s dpi=%d",
                path.name,
                len(ocr_numbers),
                languages,
                settings.OCR_DPI,
            )
            ocr_started = time.perf_counter()
            ocr_pages_result = ocr_pages(
                path, ocr_numbers, engine=ocr_engine
            )
            scores = [
                page.confidence
                for page in ocr_pages_result
                if page.confidence is not None
            ]
            mean_confidence = (
                sum(scores) / len(scores) if scores else None
            )
            logger.info(
                "ocr finished file_name=%s pages=%d mean_confidence=%s "
                "elapsed_seconds=%.3f",
                path.name,
                len(ocr_pages_result),
                mean_confidence,
                time.perf_counter() - ocr_started,
            )

        merged = merge_pages(pages, ocr_pages_result)
        if not any(page.content.strip() for page in merged):
            logger.warning("no extractable text file_name=%s", path.name)
            raise NoTextError(f"No extractable text: {path.name}")

        title = extract_title(path) or path.stem
        book = create_book(
            title=title,
            file_path=str(path),
            file_hash=file_hash,
            total_pages=len(merged),
            status="processing",
            db_path=db_path,
        )
        logger.debug("book created book_id=%d", book.id)

        try:
            page_rows = insert_pages(
                book.id,
                [
                    PageData(
                        page_number=page.page_number,
                        content=page.content,
                        method=page.method,
                        confidence=page.confidence,
                    )
                    for page in merged
                ],
                db_path=db_path,
            )
            page_ids = {row.page_number: row.id for row in page_rows}

            specs = chunk_pages(merged, effective_chunk_size, effective_overlap)
            logger.info("chunks created book_id=%d count=%d", book.id, len(specs))

            chunk_rows = insert_chunks(
                book.id,
                [
                    ChunkData(chunk_index=spec.chunk_index, content=spec.content)
                    for spec in specs
                ],
                db_path=db_path,
            )
            chunk_ids = {row.chunk_index: row.id for row in chunk_rows}

            links = [
                PageChunkData(
                    page_id=page_ids[span.page_number],
                    chunk_id=chunk_ids[spec.chunk_index],
                    start_offset=span.start_offset,
                    end_offset=span.end_offset,
                )
                for spec in specs
                for span in spec.spans
            ]
            insert_page_chunks(links, db_path=db_path)

            update_book_status(book.id, "completed", db_path=db_path)
            elapsed = time.perf_counter() - started
            logger.info(
                "book completed book_id=%d pages=%d chunks=%d elapsed_seconds=%.3f",
                book.id,
                len(merged),
                len(specs),
                elapsed,
            )
            return book.id
        except BaseException:
            update_book_status(book.id, "failed", db_path=db_path)
            raise
    except BaseException as exc:
        if isinstance(exc, LowConfidenceError):
            logger.exception(
                "ingestion failed file_name=%s error=%s page_number=%d "
                "confidence=%s threshold=%s",
                file_path,
                type(exc).__name__,
                exc.page_number,
                exc.confidence,
                exc.threshold,
            )
        else:
            logger.exception(
                "ingestion failed file_name=%s error=%s",
                file_path,
                type(exc).__name__,
            )
        raise
