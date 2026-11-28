# Architecture

## Purpose

Turn PDF books, including scanned books and images converted to PDF, into structured, queryable content (pages and chunks) that AI agents can read reliably.

## Data flow

```
input file (file_path)
  -> validate: must be a non-empty, valid PDF           validators.py
       (images are converted first: images_to_pdf)      image_to_pdf.py
  -> hash (SHA-256), reject duplicates                  pipeline.py
  -> native text per page                               pdf_extractor.py
  -> pages with no native text -> OCR                   Extract_OCR.py
       render page (300 DPI) -> OCR engine -> text + confidence (0-100)
       confidence < 80 -> LowConfidenceError, NOTHING is saved
  -> merge native and OCR pages (page order, method)    chunker.py: merge_pages
  -> no text anywhere -> NoTextError, nothing saved
  -> chunking (chunk_size, overlap_size)                chunker.py: chunk_pages
  -> write: book, pages, chunks, page_chunk             pipeline.py via repository.py
  -> SQLite (books, pages, chunks, page_chunk)
  -> agent-facing access layer                          [planned]
```

All validation, OCR and confidence checks finish in memory before the first database write, so a rejected input leaves no rows behind. Only failures after the book row exists (a database error while saving) mark the book `failed`.

## Layout

```
config/settings.py        configuration (database path, chunk defaults, OCR settings, log level and file)
config/logging_config.py  setup_logging(): console and rotating file handlers
src/database/             persistence layer (connection, init_db, repository)
src/ingestion/            ingestion layer
    models.py             shared dataclasses: PageText, PageSpan, ChunkSpec
    errors.py             ingestion exceptions
    validators.py         input validation (PDF only, non-empty, valid header)
    image_to_pdf.py       images_to_pdf(): convert images into a PDF
    pdf_extractor.py      native text per page
    Extract_OCR.py        OCR: engine interface, Tesseract engine, ocr_pages(), confidence
    chunker.py            merge_pages() and chunk_pages(): works for text and OCR pages
    pipeline.py           ingest_pdf(): orchestrates everything and saves
tests/database/           database tests
tests/ingestion/          extraction, OCR, chunking and end-to-end tests
docs/                     design docs and plans
```

## Layering rules

- `src/database/` only talks to SQLite. It contains no PDF, OCR or chunking logic.
- `validators.py`, `image_to_pdf.py`, `pdf_extractor.py`, `Extract_OCR.py` and `chunker.py` never touch the database. Only `pipeline.py` combines the steps, and it writes to the database only through `repository.py`.
- `chunker.py` is pure and does not care where a page came from: native text and OCR pages go through the same code.
- OCR engines sit behind a small `OcrEngine` interface in `Extract_OCR.py`. The rest of the code never imports an OCR library directly, so the engine can be replaced and faked in tests.
- All SQL lives in `repository.py` and `init_db.py`. Other modules never build SQL.
- Configuration comes from `config/settings.py`; nothing hardcodes paths, OCR settings or chunk defaults.
- Logging uses the standard `logging` module. Library code only calls `logging.getLogger(__name__)`; only entry points call `setup_logging()`. Logs contain counts, page numbers, scores and ids, never page, chunk or OCR text.

## Key concepts

- A **book** is identified by the SHA-256 hash of its file; deleting a book is a soft delete (`status = 'deleted'`). Ingesting a hash that already exists is rejected.
- Input is **PDF only**. An image is accepted only after it has been converted to a PDF.
- A **page** holds the text of one PDF page (1-based `page_number`) and how it was obtained: `method = 'text'` (native) or `'ocr'`. A page is OCR'd only when it has no native text.
- **Confidence**: the OCR engine reports a page score from 0 to 100. A page is accepted at 80 or higher. The database stores the score divided by 100 (0 to 1, as the schema requires); native text pages store NULL.
- A **chunk** is an ordered piece (`chunk_index`) of the whole book text, produced with `chunk_size` and `overlap_size` in characters; it may span several pages and consecutive chunks overlap.
- **page_chunk** links pages and chunks with character offsets relative to `pages.content`. For every chunk, joining the page slices given by its links reproduces `chunks.content` exactly. This holds for text and OCR pages alike.

Full schema: skill `database` (`references/schema.md`) and `docs/database-design.md`.
Ingestion details: skills `book-reader-pdf` and `book-reader-ocr`, `docs/PDF_layer-design.md`, and `docs/OCR_layer-design.md` once it exists.

## Current scope

In scope: database layer (done), PDF ingestion without OCR (done), OCR ingestion for scanned PDFs and images converted to PDF.
Out of scope for now: handwriting, layout analysis (columns, tables), sentence-aware chunking, vector search, embeddings, RAG, MCP.