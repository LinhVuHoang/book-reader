---
name: book-reader-pdf
description: Implements the PDF ingestion pipeline (no OCR) for the book-reader project. Given a PDF file_path, it extracts text page by page, splits the book text into chunks using chunk_size and overlap_size, and saves the book, pages, chunks and page-chunk offsets to SQLite through the database repository, with pytest tests covering paging, chunking and storage. Use this skill whenever the task involves reading or ingesting PDF files, extracting text per page, chunking text, chunk size or overlap, page-to-chunk offsets, or the src/ingestion modules of book-reader, even if the user does not say "PDF skill".
---

# Book Reader — PDF Ingestion (no OCR)

Build the ingestion layer that turns one PDF file into rows in the book-reader database. The entry point takes a `file_path`, extracts the text of each page, chunks the text with a chosen `chunk_size` and `overlap_size`, and stores everything through the existing database layer.

OCR is out of scope. Pages with no extractable text are stored with empty content and are not linked to any chunk.

## Before writing code

- Read `AGENTS.md`, `ARCHITECTURE.md` and the active plan `docs/exec-plans/active/pdf-ingestion-layer.md`.
- Read the existing `src/database/repository.py` and `connection.py`. Use the real function names and signatures; do not guess them and do not change the database layer unless the plan says so.
- Read `references/coding.md` before writing any code in `src/ingestion/`.
- Read `references/testing.md` before writing tests.

## Pipeline

```
file_path -> validate -> hash -> extract pages -> create book (processing)
          -> insert pages -> chunk -> insert chunks -> insert page_chunk links
          -> mark book completed        (on any error: mark failed, re-raise)
```

Modules (all under `src/ingestion/`):
- `pdf_extractor.py`: `file_path` to a list of pages. Pure; no database.
- `chunker.py`: pages to chunks with per-page spans. Pure; no database, no file access.
- `pipeline.py`: `ingest_pdf(...)`, the only place that combines the steps and calls the repository.
- `errors.py`: small exception classes.

## Key requirements

- Input is a single `file_path`; page numbers are 1-based.
- Chunking uses `chunk_size` and `overlap_size` in characters, with defaults from `config/settings.py`. Reject invalid values (`chunk_size <= 0`, `overlap_size < 0`, `overlap_size >= chunk_size`).
- Offsets in `page_chunk` are relative to `pages.content`, using Python string indexing. Joining the page slices of a chunk must reproduce `chunks.content` exactly.
- Keep extraction and chunking separate from database access. Only `pipeline.py` talks to `repository.py`.
- Never write SQL in `src/ingestion/`.
- Log with the standard `logging` module (never `print`), log counts and ids but never page or chunk text. Details are in `references/coding.md`.

## Engineering principles

- Use Python type hints.
- Keep functions small and focused.
- Pass `db_path` as a parameter through to the database layer; never hardcode paths.
- Add only the dependencies named in the active plan.
- Do not implement OCR, vector search, embeddings, RAG or MCP.
- Document important design decisions.
- Do not implement unrelated project modules.

## Testing

Use pytest with temporary SQLite databases and PDFs generated at test time. Test cases are listed in `references/testing.md`. Tests cover extraction (paging), chunking, saving to the database, and logging.

## Deliverables

Create:
- `src/ingestion/pdf_extractor.py`, `chunker.py`, `pipeline.py`, `errors.py`
- `config/logging_config.py` and additions to `config/settings.py` (chunk defaults, log level and file)
- `tests/ingestion/`
- `docs/PDF_layer-design.md`

Update dependency files and `.gitignore` only as the plan says.

## Before finishing

1. Run `pytest tests/ingestion -v` and then the whole suite `pytest tests/`.
2. Ingest a sample PDF with `ingest_pdf` against a temporary database and check the stored rows.
3. Fix any failures.
4. Write `docs/PDF_layer-design.md`: architecture, how to run, decisions with reasons, unresolved issues. Do not copy the schema; link to the `database` skill.
5. Report design decisions and unresolved issues.
