# Architecture

## Purpose

Turn PDF books into structured, queryable content (pages and chunks) that AI agents can read reliably.

## Data flow

```
PDF file
  -> extraction (native text or OCR)      [planned]
  -> pages        (text per PDF page)
  -> chunking                              [planned]
  -> chunks       (ordered pieces of the book)
  -> SQLite       (books, pages, chunks, page_chunk)
  -> agent-facing access layer             [planned]
```

## Layout

```
config/settings.py        configuration (database path, etc.)
src/database/             persistence layer (connection, init_db, repository)
src/extraction/           PDF text extraction and OCR   [planned]
src/chunking/             chunk generation              [planned]
tests/                    pytest tests
docs/                     design docs and plans
```

## Layering rules

- `src/database/` only talks to SQLite. It contains no PDF, OCR or chunking logic.
- Extraction and chunking produce plain Python data; they write to the database only through `repository.py`.
- All SQL lives in `repository.py` and `init_db.py`. Other modules never build SQL.
- Configuration comes from `config/settings.py`; nothing hardcodes paths.

## Key concepts

- A **book** is identified by its file hash; deleting a book is a soft delete (`status = 'deleted'`).
- A **page** holds the extracted text of one PDF page and how it was obtained (`text` or `ocr`).
- A **chunk** is an ordered piece of the whole book and may span several pages.
- **page_chunk** links pages and chunks with character offsets relative to `pages.content`.

Full schema: see skill `database` (`references/schema.md`) and `docs/database-design.md`.

## Current scope

In scope: database layer.
Out of scope for now: vector search, embeddings, RAG, MCP.