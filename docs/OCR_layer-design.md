# OCR Layer Design

- **Status:** Implemented
- **Date:** 2026-11-27
- **Scope:** OCR of scanned PDFs and images converted to PDF, mixed native/OCR pages, confidence checking, chunking and persistence. No handwriting, layout analysis, embeddings, RAG or MCP.
- **Schema:** See skill `database` (`references/schema.md`) and `docs/database-design.md`; this document does not duplicate it.
- **Relationship to the non-OCR layer:** see `docs/PDF_layer-design.md` and `ARCHITECTURE.md`.

## 1. Overview and scope

`ingest_pdf(file_path, ..., ocr_engine=None)` now accepts native PDFs, scanned PDFs, and image pages converted to PDF. A page is OCR'd only when its native text is empty after stripping whitespace. Validation, OCR and the confidence check all finish in memory; a rejected input leaves no rows in any table. OCR pages need a mean word confidence of at least 80 on a 0 to 100 scale.

Out of scope: handwriting, layout analysis (columns and tables), image preprocessing beyond 300 DPI rendering, sentence-aware chunking, vector search, embeddings, RAG and MCP.

## 2. Architecture

```text
validate_pdf_file -> SHA-256 / duplicate check -> extract_pages (native text)
   -> empty native pages -> ocr_pages (render -> OcrEngine -> text + confidence)
   -> merge_pages -> NoTextError check -> chunk_pages -> repository writes
   -> mark completed; failures after book creation mark failed
```

| Module | Role |
|---|---|
| `src/ingestion/validators.py` | PDF-only validation: existence, suffix, size, `%PDF-` header. |
| `src/ingestion/image_to_pdf.py` | `images_to_pdf()`: converts supported images to a temporary PDF, one page per image. |
| `src/ingestion/Extract_OCR.py` | `OcrEngine` interface, `TesseractEngine`, `ocr_pages()`, normalization and confidence. |
| `src/ingestion/models.py` | `PageText`, `PageSpan`, `ChunkSpec`; `PageText` carries `method` and `confidence`. |
| `src/ingestion/errors.py` | `InvalidFormatError`, `EmptyInputError`, `OcrEngineError`, `LowConfidenceError`, `NoTextError`, `PdfReadError`, `DuplicateBookError`. |
| `src/ingestion/chunker.py` | `merge_pages()` and the unchanged character-window `chunk_pages()`. |
| `src/ingestion/pipeline.py` | The only module that combines the steps and calls the repository. |

`Extract_OCR.py` and `chunker.py` never touch the database; `pipeline.py` writes only through `repository.py`. No SQL exists under `src/ingestion/`.

## 3. How to run

Install Tesseract 5 and the `eng` and `vie` language data. On Windows add `tesseract.exe` to `PATH` or set `TESSERACT_CMD` to its full path, then check:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
& $env:TESSERACT_CMD --list-langs
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m src.database.init_db
python -m pytest tests/ingestion -m "not ocr" -v
python -m pytest tests/ingestion -m ocr -v
python -m pytest tests/
```

Configuration from `config/settings.py`, each with an environment override:

| Setting | Default | Environment variable |
|---|---|---|
| `OCR_LANGUAGES` | `vie+eng` | `BOOK_READER_OCR_LANGUAGES` |
| `OCR_DPI` | `300` | `BOOK_READER_OCR_DPI` |
| `OCR_MIN_CONFIDENCE` | `80.0` (0 to 100) | `BOOK_READER_OCR_MIN_CONFIDENCE` |
| `TESSERACT_CMD` | `None` (use `PATH`) | `TESSERACT_CMD` |

Chunk defaults remain `CHUNK_SIZE=1000` and `CHUNK_OVERLAP=200`, with their existing environment overrides and function parameters taking precedence.

Library usage:

```python
from src.ingestion.image_to_pdf import images_to_pdf
from src.ingestion.pipeline import ingest_pdf

pdf_path = images_to_pdf(["page1.png", "page2.png"], "scanned.pdf")
book_id = ingest_pdf(pdf_path, chunk_size=1000, overlap_size=200)
```

`db_path`, `chunk_size`, `overlap_size` and `ocr_engine` can be passed explicitly. Only entry points call `setup_logging()`.

## 4. Decisions

| Decision | Reason / alternative | Status |
|---|---|---|
| Tesseract 5 through `pytesseract`, behind `OcrEngine`; PaddleOCR remains a candidate replacement. | CPU-only, small install, 0 to 100 word confidence, replaceable interface. | Kept |
| `vie+eng`, render at 300 DPI; install `vie` when missing. | Vietnamese books plus English fragments; DPI balances accuracy and speed. | Kept; the current machine has `eng`, `osd` and `vie`, and `TesseractEngine()` builds with default `vie+eng`. Committed real-engine tests still use English per the testing guide. |
| PDF only: suffix plus `%PDF-` header; images must use `images_to_pdf`. | Rejects renamed images and unsupported formats early. | Kept |
| OCR only pages whose native text is empty after `strip()`. | Avoids re-reading pages that already have a text layer. | Kept |
| Mean word confidence, 0 to 100, accepted at 80 inclusive; database stores score divided by 100. | Matches the schema's 0 to 1 CHECK constraint and keeps one threshold scale. | Kept |
| Below-threshold page raises `LowConfidenceError`; nothing is saved. | All checks run before the first write. | Kept |
| Empty OCR page is stored with `method='ocr'` and NULL confidence if another page has text; otherwise `NoTextError` and nothing saved. | Blank pages exist in real books. When a native page is empty, the OCR result wins the merge even if both are empty, preserving `method='ocr'`. | Kept; merge tie-break changed from the coding guide |
| Normalize line endings, trailing spaces and extra blank lines before storage. | Stored page text equals chunked text. | Kept |
| Fake engine for logic tests; real Tesseract tests marked `ocr` and skipped when unusable. | Tests run without Tesseract; real engine coverage stays available. | Kept; real tests require `eng` |
| Logs contain counts, page numbers, scores and ids, never book or OCR text. | Avoids logging copyrighted text. | Kept |

## 5. Behavior changes

| Before (no OCR) | Now |
|---|---|
| Empty native pages were stored as empty text pages. | They are OCR'd; if OCR also finds nothing they stay empty with `method='ocr'`. |
| A book with no text was created and marked `failed`. | `NoTextError` is raised before any write; all four tables stay empty. |
| A `.pdf` suffix was enough to try opening the file. | Suffix, size and header are validated first; invalid inputs raise `InvalidFormatError` or `EmptyInputError`. |
| Duplicate check happened after PDF opening. | SHA-256 duplicate check happens before OCR, so a duplicate scan never calls the engine. |
| Any failure after book creation produced one `ERROR` record. | All failures, including pre-write ones, produce exactly one `ERROR` record with exception info; low-confidence errors also log page number, score and threshold. |

Updated old tests: the no-text case now asserts zero rows instead of a `failed` book; empty-page tests pass a fake engine and assert `method='ocr'`; native-only tests assert that the engine is never called.

## 6. Test summary

- Validation: missing file, directory, wrong suffix, image suffix, empty file, fake PDF, corrupt PDF and zero-page PDF.
- Image conversion: page counts, image order, empty/corrupt/unsupported images, output checks.
- OCR logic with the fake engine: page selection, normalization, threshold boundaries, error attributes, custom threshold, engine failures, Tesseract data parsing and language checks.
- Chunking: old cases plus mixed sources, empty pages, invalid pages and `merge_pages` precedence.
- Pipeline end to end with the fake engine: native, scanned, mixed and blank pages; all rejected inputs leave zero rows; duplicates skip OCR; image-converted PDFs ingest successfully.
- Logging: OCR start/finish, DEBUG scores, empty-page warning, one ERROR for low confidence, no text in logs.
- Real Tesseract: four tests marked `ocr` cover English reading, confidence, end-to-end ingestion and a blank page. They are skipped when no engine or `eng` data is available.
- Result: `pytest tests/` — 108 passed with `TESSERACT_CMD` set; 104 passed and 4 skipped when Tesseract is not on `PATH`. Manual ingestion of a scanned PDF and an image-converted PDF produced `completed` books with `method='ocr'`, confidence `0.953`, reconstructable chunks, and no book text in the log file. After `vie` was installed, a Vietnamese image converted with `images_to_pdf` was ingested with the default engine: `completed`, all expected words recognized, confidence `0.915`.

## 7. Unresolved issues and limitations

- `vie` is installed, but accuracy has only been checked on one short generated Vietnamese sample; real books have not been measured.
- The per-page threshold is strict: one unclear page rejects the whole book.
- No preprocessing beyond rendering; noisy scans may need deskewing or cleanup later.
- Handwriting and multi-column/table layout are not handled.
- Persistence is still not atomic across repository calls; a database failure after book creation can leave partial rows, with the book marked `failed`.
- PyMuPDF 2.x deprecates the `fitz` import name; code uses `import pymupdf as fitz`.
- Pytest emits an unrelated `anyio` plugin deprecation warning.

## 8. Next steps

- Measure accuracy on real Vietnamese scans; switch to `tessdata_best` if the installed data is not accurate enough.
- Compare Tesseract with PaddleOCR on the same pages before changing the engine.
- Add optional image preprocessing and a book-level confidence summary if strict per-page rejection proves impractical.
