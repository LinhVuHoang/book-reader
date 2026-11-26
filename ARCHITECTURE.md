# Architecture

## Purpose

Turn PDF books into structured, queryable content (pages and chunks) that AI agents can read reliably.

## Data flow

```
PDF file (file_path)
  -> extraction (native text, no OCR)     src/ingestion/pdf_extractor.py
  -> pages        (text per PDF page)
  -> chunking (chunk_size, overlap_size)  src/ingestion/chunker.py
  -> chunks + page spans (offsets per page)
  -> pipeline writes via repository       src/ingestion/pipeline.py
  -> SQLite       (books, pages, chunks, page_chunk)
  -> agent-facing access layer            [planned]
```
OCR for scanned pages is a later stage; pages without extractable text are stored with empty content for now.

## Layout

```
config/settings.py        configuration (database path, chunk defaults, log level and file)
config/logging_config.py  setup_logging(): console and rotating file handlers
src/database/             persistence layer (connection, init_db, repository)
src/ingestion/            PDF ingestion layer (no OCR)
    pdf_extractor.py      file_path -> list of pages
    chunker.py            pages -> chunks with per-page spans
    pipeline.py           ingest_pdf(): orchestrates extraction, chunking, saving
    errors.py             ingestion exceptions
src/ocr/                  OCR for scanned pages         [planned]
tests/database/           database tests
tests/ingestion/          extraction, chunking and end-to-end tests
docs/    
```

## Layering rules

- `src/database/` only talks to SQLite. It contains no PDF, OCR or chunking logic.
- `pdf_extractor.py` and `chunker.py` are pure: no database access, no file writes. They take and return plain Python data.
- Only `pipeline.py` combines extraction, chunking and persistence, and it writes to the database only through `repository.py`.
- All SQL lives in `repository.py` and `init_db.py`. Other modules never build SQL.
- Configuration comes from `config/settings.py`; nothing hardcodes paths or chunk defaults.
- Logging uses the standard `logging` module. Library code only calls `logging.getLogger(__name__)`; only entry points call `setup_logging()`. Logs contain counts and ids, never page or chunk text.

## Key concepts

- A **book** is identified by the SHA-256 hash of its file; deleting a book is a soft delete (`status = 'deleted'`). Ingesting a file whose hash already exists is rejected.
- A **page** holds the extracted text of one PDF page (1-based `page_number`) and how it was obtained (`text` now, `ocr` later).
- A **chunk** is an ordered piece (`chunk_index`) of the whole book text, produced with `chunk_size` and `overlap_size` (in characters). A chunk may span several pages, and consecutive chunks overlap.
- **page_chunk** links pages and chunks with character offsets relative to `pages.content`. For every chunk, joining the page slices given by its links reproduces `chunks.content` exactly.

Full schema: see skill `database` (`references/schema.md`) and `docs/database-design.md`.

## Current scope

In scope: database layer (done), PDF ingestion without OCR.
Out of scope for now: OCR, vector search, embeddings, RAG, MCP.