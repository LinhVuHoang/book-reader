# Exec Plan: PDF ingestion layer (no OCR)

- **Status:** completed
- **Created:** 2026-11-26
- **Confirmed:** 2026-11-26. The user confirmed the proposed decisions and asked to continue.
- **Skill source:** `.opencode/skills/book-reader-pdf/SKILL.md`
- **Goal:** Extract text from PDF, chunk it, persist pages/chunks/page_chunk through the existing repository, and add logging — without OCR or any higher-level retrieval feature.

## Scope

### In scope

- Use `pymupdf` to extract text from PDF pages (all text pages in the file, no OCR).
- Chunking by character count with overlap; chunks may cross page boundaries.
- Save `books`, `pages`, `chunks`, `page_chunk` using `src/database/repository.py`.
- Idempotency by SHA-256 of the whole PDF file; duplicate ingest raises `DuplicateBookError` and does not re-ingest.
- Logging via `logging` only; never log book text.
- Configuration in `config/settings.py`; tests in `tests/ingestion/`.
- PDF ingestion design decisions documented in `docs/PDF_layer-design.md`.

### Out of scope

- OCR/scanned PDF handling.
- Sentence/word/semantic chunking.
- Vector search, embeddings, RAG, MCP.
- CLI wrapper, retry, transaction across repository calls.

## Proposed decisions (confirm before coding)

- [x] `pymupdf` is used for extraction (`import pymupdf as fitz` to avoid the `fitz` deprecation warning).
- [x] Default `CHUNK_SIZE=1000`, `CHUNK_OVERLAP=200` in settings with env override `BOOK_READER_CHUNK_SIZE` / `BOOK_READER_CHUNK_OVERLAP`.
- [x] Pages content joined without separator; overlap windows can cross pages and offsets are page-local.
- [x] Empty pages are stored with empty content and no `page_chunk`; whole book with no text raises `NoTextError` and book status becomes `failed`.
- [x] Duplicate SHA-256 raises `DuplicateBookError` before creating any new rows.
- [x] `chunk_index` is 0-based and contiguous.
- [x] Test PDFs generated at test time with PyMuPDF; no binary fixtures committed.
- [x] `db_path` is an optional argument to `ingest_pdf`; default comes from settings.
- [x] Logging uses `setup_logging()` from an entry point only; library modules use `logging.getLogger(__name__)`.

## Steps

### 1. Dependencies and configuration

- [x] Add `pymupdf` to `requirements.txt`.
- [x] Add chunk defaults and LOG_LEVEL/LOG_FILE to `config/settings.py`.
- [x] Add `config/logging_config.py` with `setup_logging()` and a small test.
- **Check:** settings defaults and env override verified.

### 2. Errors and dataclasses

- [x] Define `DuplicateBookError`, `NoTextError`, `PdfReadError` in `src/ingestion/errors.py`.
- [x] Define dataclasses near production sites: `PageText` in `pdf_extractor.py`, `PageSpan` and `ChunkSpec` in `chunker.py`.
- **Check:** error classes and dataclasses instantiated successfully.

### 3. PDF extraction module

- [x] Implement `src/ingestion/pdf_extractor.py` with `extract_pages(file_path) -> list[PageText]`.
- [x] Keep empty pages as `content=""`, 1-based page numbers.
- [x] Raise `FileNotFoundError` for missing input and `PdfReadError` for invalid/corrupt PDFs.
- [x] Add `extract_title()` using PDF metadata, falling back to `None`; `pipeline.py` uses it for book title.
- **Check:** `pytest tests/ingestion/test_pdf_extractor.py -v` — 4 passed.

### 4. Chunking module

- [x] Implement `src/ingestion/chunker.py` with `chunk_pages(pages, chunk_size, overlap_size) -> list[ChunkSpec]`.
- [x] Join page texts without separator, use `step = chunk_size - overlap_size`.
- [x] Compute `PageSpan` with page-local `start_offset` and `end_offset`.
- [x] Validate parameters; raise `ValueError` for non-positive chunk size or overlap outside `0 <= overlap < chunk_size`.
- [x] Add tests for size, overlap, empty input, cross-page spans, long pages, reconstruction and Unicode offsets.
- **Check:** `pytest tests/ingestion/test_chunker.py -v` — 11 passed.

### 5. Pipeline module

- [x] Implement `src/ingestion/pipeline.py` with `ingest_pdf(file_path, db_path=None, chunk_size=None, overlap_size=None) -> int`.
- [x] Compute SHA-256, check duplicates, create `books` row with status `processing`.
- [x] Insert pages with `method="text"` and `confidence=NULL`.
- [x] Call chunker, insert chunks and page_chunk links with exact indices/offsets.
- [x] Mark book `completed` on success; on error mark `failed` and re-raise.
- [x] Add tests for end-to-end persistence, empty pages, duplicate handling, no-text failure, custom chunk params and mid-way failure.
- **Check:** `pytest tests/ingestion -v` — 28 passed.

### 6. Logging behavior

- [x] Log start and finish at INFO with `book_id`.
- [x] Log empty pages at WARNING with page number (never content).
- [x] Log duplicate detection at WARNING with existing `book_id`.
- [x] On failure, log exactly one ERROR with exception info at the point the book is marked `failed`.
- [x] Add tests verifying no log record contains page/chunk text and that repeated `setup_logging()` does not duplicate handlers.
- **Check:** covered in `tests/ingestion/test_pipeline.py` and `tests/ingestion/test_logging_config.py`; full suite 43 passed.

### 7. Documentation and cleanup

- [x] Write `docs/PDF_layer-design.md` with architecture, config/env, decisions and reasons, run instructions and unresolved issues.
- [x] Ensure `.gitignore` covers generated DB/log files including `logs/`.
- [x] Verify no accidental DB/PDF artifacts appear in git status.
- **Check:** `git check-ignore -v data/book_reader.db logs/book_reader.log custom-step2.db` shows ignore rules.

### 8. Final verification

- [x] Run `python -m pytest tests/ingestion -v` — 28 passed.
- [x] Run `python -m pytest tests/` — 43 passed.
- [x] Run `python -m compileall -q config src tests` — no syntax errors.
- [x] Manual sample ingestion on a temporary DB: `completed`, 2 pages, 4 chunks, 5 links, reconstruction invariant `True`.
- [x] Update this plan with notes and verification results, then move it to `docs/exec-plans/completed/`.
- [x] Update the exec-plan row in `AGENTS.md`.

## Verification summary

- `pytest tests/ingestion -v`: 28 passed.
- `pytest tests/`: 43 passed.
- `python -m compileall -q config src tests`: no output, no errors.
- Manual sample ingestion result: `completed 2 2 4 5 True`.
- One external warning remains from `anyio` (`CallSpec2` renamed); it does not affect results.

## Implementation notes

- The skill tool did not list `book-reader-pdf`; its files were read directly from `.opencode/skills/book-reader-pdf/`.
- `requirements.txt` pins `pymupdf>=2.1,<3` because the environment had `pymupdf4llm` and `pymupdf-layout` 2.x installed; pinning avoids resolver conflicts.
- Persistence is intentionally not atomic across repository calls. Mid-way failures leave the book `failed` and may leave partial rows; no re-ingest path exists yet.
- `setup_logging()` tags handlers so tests can remove only their own handlers. Empty `BOOK_READER_LOG_FILE` disables file logging.
- No CLI wrapper was added; `ingest_pdf()` is a library API used directly by tests and callers.
