from __future__ import annotations

import logging
from collections.abc import Sequence

from src.ingestion.models import ChunkSpec, PageSpan, PageText

logger = logging.getLogger(__name__)


def merge_pages(
    native_pages: Sequence[PageText], ocr_pages: Sequence[PageText]
) -> list[PageText]:
    native = {page.page_number: page for page in native_pages}
    ocr = {page.page_number: page for page in ocr_pages}
    if len(native) != len(native_pages) or len(ocr) != len(ocr_pages):
        raise ValueError("duplicate page numbers in input")

    merged: list[PageText] = []
    for number in sorted(set(native) | set(ocr)):
        native_page = native.get(number)
        ocr_page = ocr.get(number)
        if native_page is None:
            merged.append(ocr_page)
        elif ocr_page is None:
            merged.append(native_page)
        elif native_page.content.strip():
            merged.append(native_page)
        else:
            merged.append(ocr_page)

    if [page.page_number for page in merged] != list(range(1, len(merged) + 1)):
        raise ValueError("page numbers must run from 1 to N without gaps")
    return merged


def chunk_pages(
    pages: Sequence[PageText], chunk_size: int, overlap_size: int
) -> list[ChunkSpec]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap_size < 0:
        raise ValueError("overlap_size must not be negative")
    if overlap_size >= chunk_size:
        raise ValueError("overlap_size must be less than chunk_size")

    seen: set[int] = set()
    previous_number = 0
    for page in pages:
        if not isinstance(page.content, str):
            raise ValueError("page content must be a string")
        if page.page_number in seen:
            raise ValueError(f"duplicate page number: {page.page_number}")
        if page.page_number <= previous_number:
            raise ValueError("pages must be in increasing page_number order")
        seen.add(page.page_number)
        previous_number = page.page_number

    book_text = "".join(page.content for page in pages)
    if not book_text:
        return []

    page_ranges: list[tuple[int, int, int, str]] = []
    cursor = 0
    for page in pages:
        start = cursor
        end = start + len(page.content)
        page_ranges.append((page.page_number, start, end, page.content))
        cursor = end

    step = chunk_size - overlap_size
    chunks: list[ChunkSpec] = []
    start = 0
    chunk_index = 0
    while start < len(book_text):
        end = min(start + chunk_size, len(book_text))
        content = book_text[start:end]
        spans: list[PageSpan] = []
        for page_number, page_start, page_end, page_content in page_ranges:
            if not page_content:
                continue
            span_start = max(start, page_start)
            span_end = min(end, page_end)
            if span_start < span_end:
                spans.append(
                    PageSpan(
                        page_number=page_number,
                        start_offset=span_start - page_start,
                        end_offset=span_end - page_start,
                    )
                )

        chunks.append(
            ChunkSpec(chunk_index=chunk_index, content=content, spans=spans)
        )
        chunk_index += 1
        if end == len(book_text):
            break
        start += step

    logger.debug(
        "chunks created count=%d chunk_size=%d overlap_size=%d",
        len(chunks),
        chunk_size,
        overlap_size,
    )
    return chunks
