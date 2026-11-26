# Coding Guide: PDF Ingestion

## Contents
- Dependencies
- Configuration
- Data types
- Extraction rules
- Chunking algorithm
- Pipeline
- Logging
- Errors

## Dependencies

Use `pymupdf` (import name `fitz`) for text extraction. It is also used in tests to generate sample PDFs, so no other PDF library is needed. Add it to `requirements.txt` (create the file if missing); keep `pytest` in `requirements-dev.txt`.

## Configuration

Add to `config/settings.py`:
- `CHUNK_SIZE` default `1000` (characters)
- `CHUNK_OVERLAP` default `200` (characters)

Both may be overridden by environment variables (`BOOK_READER_CHUNK_SIZE`, `BOOK_READER_CHUNK_OVERLAP`). Functions take `chunk_size` and `overlap_size` as parameters; settings only supply the defaults.

Logging settings (see the Logging section):
- `LOG_LEVEL` default `"INFO"` (env `BOOK_READER_LOG_LEVEL`)
- `LOG_FILE` default `"logs/book_reader.log"` (env `BOOK_READER_LOG_FILE`; an empty value disables the file handler)

## Data types

Use frozen dataclasses, defined where they are produced:

```python
@dataclass(frozen=True)
class PageText:
    page_number: int      # 1-based
    content: str

@dataclass(frozen=True)
class PageSpan:
    page_number: int
    start_offset: int     # relative to that page's content
    end_offset: int       # exclusive

@dataclass(frozen=True)
class ChunkSpec:
    chunk_index: int      # 0-based, contiguous
    content: str
    spans: list[PageSpan]
```

## Extraction rules (`pdf_extractor.py`)

`extract_pages(file_path) -> list[PageText]`
- Accept `str` or `Path`. Raise `FileNotFoundError` if it does not exist; raise `PdfReadError` if it cannot be opened, is corrupt or is encrypted.
- Use `page.get_text("text")` for each page, in order, numbering from 1.
- Do not strip, reflow or clean the text. The text stored in `pages.content` is the source of truth for offsets, so chunks must be built from exactly that string.
- A page with no text yields `content=""`. Never skip a page; page numbers must stay continuous.
- Always close the document (context manager).

## Chunking algorithm (`chunker.py`)

`chunk_pages(pages, chunk_size, overlap_size) -> list[ChunkSpec]`

1. Validate parameters (see `SKILL.md`); raise `ValueError` on invalid values.
2. Build the book text by joining the page contents with no separator: `book_text = "".join(p.content for p in pages)`. No separator means every character of a chunk belongs to exactly one page, so offsets stay exact.
3. Record each page's start position in `book_text` (cumulative lengths).
4. `step = chunk_size - overlap_size`. Starting at `start = 0`, repeat while `start < len(book_text)`:
   - `end = min(start + chunk_size, len(book_text))`
   - `content = book_text[start:end]`
   - for every page whose range overlaps `[start, end)` and has a non-empty intersection, add a `PageSpan` with `start_offset = max(start, page_start) - page_start` and `end_offset = min(end, page_end) - page_start`
   - append `ChunkSpec(chunk_index, content, spans)`
   - if `end == len(book_text)`, stop; otherwise `start += step`
5. Empty pages never produce spans. If `book_text` is empty, return an empty list.

Invariant to test: for every chunk, `"".join(page_content[s.start_offset:s.end_offset] for s in spans) == chunk.content`.

Keep it simple: fixed character windows, no sentence or word snapping. Note this as a possible later improvement in the design doc.

## Pipeline (`pipeline.py`)

`ingest_pdf(file_path, db_path=None, chunk_size=None, overlap_size=None) -> int` returns the `book_id`. `None` means use the defaults from settings.

Log as described in the Logging section: `INFO` at start and at the end of the main steps, `WARNING` for empty pages and duplicates, `ERROR` with a traceback on failure.

1. Validate that the file exists and ends with `.pdf` (case-insensitive).
2. Compute the SHA-256 of the file bytes, reading in blocks.
3. If a book with this hash already exists, raise `DuplicateBookError`. Do not re-ingest.
4. `extract_pages`. If every page is empty, raise `NoTextError` (this is where OCR would take over later).
5. Create the book: title from the PDF metadata title if present, otherwise the file name without extension; `status="processing"`; `total_pages` from the extraction.
6. Insert pages (`method="text"`, `confidence=None`) and keep the mapping `page_number -> page_id`.
7. `chunk_pages`; insert chunks and keep `chunk_index -> chunk_id`.
8. Insert one `page_chunk` row per `PageSpan`.
9. Update the book status to `completed`.
10. If anything fails after step 5, set the status to `failed` and re-raise the original error.

Use the repository functions that already exist and check how they return ids. If a bulk or transactional insert is available, prefer it so pages, chunks and links are not left half-written.

## Logging

Use the standard library `logging` module only; add no dependency. Never use `print`.

Setup:
- Every module in `src/ingestion/` starts with `logger = logging.getLogger(__name__)`. Library modules never add handlers or call `basicConfig`.
- Create `config/logging_config.py` with `setup_logging(level: str | None = None, log_file: str | None = None) -> None`. It configures the root logger once: a console handler plus a `RotatingFileHandler` (about 1 MB per file, 3 backups), creates the log directory if needed, and reads defaults from `config/settings.py`. Calling it twice must not add duplicate handlers.
- Only entry points (scripts, a CLI, `__main__`) call `setup_logging()`. Tests do not call it; they use `caplog`.
- Format: `%(asctime)s %(levelname)s %(name)s %(message)s`.

What to log, by level:
- `INFO` (`pipeline.py` only): ingestion started (file name, `chunk_size`, `overlap_size`); file hash computed; pages extracted (count); chunks created (count); book completed (`book_id`, pages, chunks, elapsed seconds).
- `DEBUG`: per-page character counts in the extractor; chunk count and parameters in the chunker; per-step timings.
- `WARNING`: a page with empty text (include `page_number`); duplicate file hash (include the existing `book_id`); a PDF with no extractable text.
- `ERROR`: ingestion failed. Use `logger.exception(...)` once, in `pipeline.py`, at the point where the book is marked `failed` and the error is re-raised. Do not log the same error again in lower layers, so one failure produces one traceback.

Rules:
- Use lazy formatting: `logger.info("pages extracted count=%d", n)`, never f-strings.
- Write messages as `message key=value key=value`, and include `book_id` once it is known.
- Never log page text or chunk content. Log lengths, counts, page numbers and ids only (content is large and may be copyrighted).
- Log the file name, not the full path, unless at `DEBUG`.
- `pdf_extractor.py` and `chunker.py` stay pure: logging is their only side effect.

## Errors (`errors.py`)

```python
class IngestionError(Exception): ...
class PdfReadError(IngestionError): ...
class DuplicateBookError(IngestionError): ...
class NoTextError(IngestionError): ...
```
