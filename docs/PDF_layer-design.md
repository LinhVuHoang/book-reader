# PDF Layer Design — Ingestion (no OCR)

- **Status:** Implemented
- **Date:** 2026-11-26
- **Scope:** PDF text extraction, character-based chunking, persistence through the existing repository, and logging. No OCR, RAG, vector search or MCP.
- **Schema:** See skill `database -> references/schema.md` and `docs/database-design.md`. This document does not duplicate the schema.

## 1. Architecture

```text
file_path
  -> validate extension/existence -> SHA-256 -> duplicate check
  -> extract_pages()                         src/ingestion/pdf_extractor.py
  -> create book (processing)
  -> insert pages (text, confidence=None)
  -> chunk_pages()                           src/ingestion/chunker.py
  -> insert chunks + page_chunk links
  -> mark completed
  -> on error: mark failed and re-raise      src/ingestion/pipeline.py
```

| Module | Role |
|---|---|
| `src/ingestion/pdf_extractor.py` | `extract_pages()` and `extract_title()`; pure PDF reading with `pymupdf`. |
| `src/ingestion/chunker.py` | `chunk_pages()`; pure character-window chunking with `PageSpan` offsets. |
| `src/ingestion/pipeline.py` | `ingest_pdf()`; the only module that calls the database repository. |
| `src/ingestion/errors.py` | `IngestionError`, `PdfReadError`, `DuplicateBookError`, `NoTextError`. |
| `config/settings.py` | Chunk defaults and environment overrides. |
| `config/logging_config.py` | `setup_logging()` with console and rotating file handlers. |

Layering rules: `pdf_extractor.py` and `chunker.py` are pure; they never touch the database. Only `pipeline.py` talks to `repository.py`. No SQL exists under `src/ingestion/`.

## 2. Public API

- `extract_pages(file_path: str | Path) -> list[PageText]` — 1-based page numbers; empty pages are kept.
- `chunk_pages(pages, chunk_size, overlap_size) -> list[ChunkSpec]` — returns chunks with per-page spans.
- `ingest_pdf(file_path, db_path=None, chunk_size=None, overlap_size=None) -> int` — returns `book_id`.
- `setup_logging(level=None, log_file=None) -> None` — called by entry points only, never by library code or tests.

## 3. Decisions and reasons

| Decision | Reason |
|---|---|
| Use `pymupdf` (aliased as `fitz` in code), pinned `>=2.1,<3` in `requirements.txt`. | The environment already had `pymupdf4llm`/`pymupdf-layout` 2.x; pinning avoids resolver conflicts. The alias keeps the skill's `fitz` API shape. |
| Defaults `CHUNK_SIZE=1000`, `CHUNK_OVERLAP=200`; env overrides `BOOK_READER_CHUNK_SIZE`, `BOOK_READER_CHUNK_OVERLAP`; function parameters win. | Settings provide defaults only; callers can tune per ingestion. |
| Join page text with no separator and use `step = chunk_size - overlap_size`. | Every chunk character belongs to exactly one page, so offsets stay exact. |
| Validate `chunk_size > 0`, `0 <= overlap_size < chunk_size`. | Prevents infinite loops and meaningless windows. |
| Store empty pages with `content=""` and no `page_chunk` rows. | Keeps page numbers continuous without creating empty spans. |
| Whole book without text raises `NoTextError`; book ends `failed`. | OCR is out of scope for this phase; the failure state makes later OCR handoff visible. |
| SHA-256 duplicate check uses `list_books(include_deleted=True)` and raises `DuplicateBookError`. | Re-ingest is out of scope; soft-deleted books are still identified by hash. |
| Status flow: `processing` → `completed`, or `failed` on any error after book creation. | Failed ingestions are inspectable instead of silently disappearing. |
| Logging uses `logging` only, lazy formatting, `key=value` messages, counts/ids only. | Never log copyrighted page or chunk text; one failure emits one traceback via `logger.exception()` in `pipeline.py`. |
| `setup_logging()` tags its handlers and is idempotent. | Calling it twice does not duplicate console/file output. Empty `BOOK_READER_LOG_FILE` disables the file handler. |
| Test PDFs are generated at test time with PyMuPDF into `tmp_path`. | No binary fixtures are committed. |

## 4. How to run

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m src.database.init_db
python -m pytest tests/ingestion -v
python -m pytest tests/
```

Example library usage:

```python
from src.ingestion.pipeline import ingest_pdf

book_id = ingest_pdf("book.pdf", chunk_size=1000, overlap_size=200)
```

`db_path`, `chunk_size` and `overlap_size` can be passed explicitly; `None` uses `config/settings.py`.

## 5. Verification

- `pytest tests/ingestion -v`: 28 passed.
- `pytest tests/`: 43 passed.
- Manual sample ingestion on a temporary DB produced a `completed` book with 2 pages, 4 chunks, 5 links, and reconstruction invariant `True`.

## 6. Unresolved issues

- Persistence is not atomic across repository calls; a mid-way failure can leave partial pages/chunks, though the book is marked `failed`.
- Chunking is fixed-character windows; sentence/word-aware chunking is a later improvement.
- PDF metadata title is only stripped, not normalized.
- PyMuPDF 2.x deprecates the `fitz` import name; code uses `import pymupdf as fitz` to avoid the warning.
- No CLI entry point exists yet; `ingest_pdf()` is currently a library API.
- Pytest emits one external warning from the `anyio` plugin about `CallSpec2`; it does not affect results.
