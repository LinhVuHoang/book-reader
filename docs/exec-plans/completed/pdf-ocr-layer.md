# Execution Plan: OCR Ingestion Layer

Status: completed
Skill: `book-reader-ocr` (`.opencode/skills/book-reader-ocr/SKILL.md`)
Depends on: database layer and PDF ingestion layer (completed; see `docs/database-design.md` and `docs/PDF_layer-design.md`)

Goal: `ingest_pdf(file_path)` also handles scanned PDFs and images converted to PDF. Pages without native text are read with OCR and scored; pages scoring 80 or higher (scale 0 to 100) are accepted, and a lower score raises an error with nothing saved. `chunker.py` and `pipeline.py` are shared with the non-OCR path.

## How to use this plan

- Work through the steps in order. Do not start a step until the previous one passes its check.
- Before each step, read the files listed under "Read first".
- After each step, run its "Check", then tick the box and write one line under "Notes".
- If a check fails, fix it before moving on. If a decision is unclear, stop and ask.
- Stay in scope: no vector search, embeddings, RAG, MCP, layout analysis or handwriting. Do not change `src/database/`.

## Decisions (proposed; confirm before Step 1)

1. Engine: Tesseract 5 through `pytesseract`, behind the `OcrEngine` interface in `Extract_OCR.py`. PaddleOCR is the candidate replacement if accuracy on real books is not enough.
2. Languages `vie+eng`, render at 300 DPI, if not have `viet`, install it.
3. Input is PDF only, checked by suffix and `%PDF-` header. Images must be converted with `images_to_pdf` first.
4. A page is OCR'd only when its native text is empty.
5. Confidence is on a 0 to 100 scale, accepted at 80 or higher (inclusive), measured per OCR page as the mean word confidence. The database stores score divided by 100, because the schema requires 0 to 1.
6. Any OCR page below the threshold raises `LowConfidenceError` and nothing is saved: validation, OCR and checks finish before the first database write.
7. An OCR page with no text is stored empty (`method = 'ocr'`, confidence NULL), as long as some page has text. If no page has text, `NoTextError` is raised and nothing is saved. This replaces the earlier behavior where `NoTextError` left a `failed` book.
8. OCR text is normalized (line endings, trailing spaces, extra blank lines) before it is stored, so stored text equals chunked text.
9. Tests use a fake engine for logic; tests with the real Tesseract are marked `ocr` and skipped when it is not installed.
10. Logs never contain OCR text.

## Steps

### Step 1: Dependencies and settings
- [x] Add `pytesseract` and `Pillow` to `requirements.txt`; add `OCR_LANGUAGES`, `OCR_DPI`, `OCR_MIN_CONFIDENCE` and `TESSERACT_CMD` (with env overrides) to `config/settings.py`; register the `ocr` pytest marker.
- Read first: `AGENTS.md`, `ARCHITECTURE.md`, `skill book-reader-ocr -> references/coding.md` (Engine choice, Dependencies and configuration)
- Check: `tesseract --list-langs` lists `eng` and `vie`; `python -c "import pytesseract, PIL"` works; settings print `vie+eng`, `300`, `80.0`; `pytest --markers` shows `ocr`.
- Notes: Dependencies, settings and the `ocr` marker are in place; `pytesseract`, `PIL`, settings and `pytest --markers` pass. Tesseract 5.4 is installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`; `--list-langs` now lists `eng`, `osd` and `vie` (verified 2026-11-27). `TesseractEngine()` builds with the default `vie+eng`.

### Step 2: Errors and shared models
- [x] Add `InvalidFormatError`, `EmptyInputError`, `OcrEngineError`, `LowConfidenceError` to `src/ingestion/errors.py`; create `src/ingestion/models.py` with `PageText` (now with `method`, `confidence`), `PageSpan`, `ChunkSpec`; update existing imports.
- Read first: `references/coding.md` (Shared models and errors), existing `src/ingestion/`
- Check: `pytest tests/ingestion -m "not ocr" -v` is still green after moving the dataclasses; `LowConfidenceError` exposes `page_number`, `confidence`, `threshold`.
- Notes: Dataclasses live in `models.py`; all four errors subclass `IngestionError` and `LowConfidenceError` carries the three attributes. Baseline `pytest tests/ -m "not ocr"`: 43 passed.

### Step 3: PDF extraction (validation, image conversion, OCR)
- [x] Create `src/ingestion/validators.py`, `src/ingestion/image_to_pdf.py` and `src/ingestion/Extract_OCR.py`, each with its tests (`test_validators.py`, `test_image_to_pdf.py`, `test_extract_ocr.py`).
- Read first: `references/coding.md` (Input validation, Image to PDF, OCR extraction, Confidence scoring), `references/testing.md` (Input validation, Image to PDF, OCR extraction, Confidence scoring)
- Provides: `validate_pdf_file`, `images_to_pdf`, `OcrEngine`, `TesseractEngine`, `ocr_pages` with the 80 threshold.
- Check: `pytest tests/ingestion/test_validators.py tests/ingestion/test_image_to_pdf.py tests/ingestion/test_extract_ocr.py -m "not ocr" -v` green; `pytest -m ocr` on the real-engine tests green if Tesseract is installed.
- Notes: 33 non-OCR tests pass. `EmptyInputError` is re-raised unchanged by `extract_pages` for a zero-page PDF. Real-engine tests skip unless Tesseract is on PATH or `TESSERACT_CMD` is set; verification with the installed Tesseract is deferred to Step 8.

### Step 4: Chunking
- [x] Update `src/ingestion/chunker.py`: use `models.py`, add `merge_pages`, add input validation to `chunk_pages`; extend `tests/ingestion/test_chunker.py`.
- Read first: `references/coding.md` (Chunker changes), `references/testing.md` (Chunking with mixed sources)
- Check: `pytest tests/ingestion/test_chunker.py -v` green, including all old cases and the mixed-source cases.
- Notes: 22 tests pass. `merge_pages` prefers non-empty content, prefers native on ties, and rejects gaps; `chunk_pages` rejects duplicates, out-of-order pages and non-string content without touching metadata.

### Step 5: Pipeline
- [x] Update `src/ingestion/pipeline.py` as described in "Pipeline changes"; update the old tests whose behavior changed; add end-to-end tests with the fake engine.
- Read first: `src/database/repository.py` (real signatures), `references/coding.md` (Pipeline changes, Behavior changes to existing code), `references/testing.md` (Pipeline end to end, Real Tesseract)
- Check: `pytest tests/ingestion -m "not ocr" -v` green; for every rejected input (invalid format, empty, no text, low confidence) the four tables hold zero rows; a manual ingest of a scanned sample PDF shows `method = 'ocr'` and `confidence` between 0.8 and 1 in `pages`.
- Notes: 84 non-OCR ingestion tests pass, including zero-row checks for all rejected inputs. Design change: when a native page is empty, `merge_pages` keeps the OCR page even if OCR also found no text, so blank scanned pages are stored with `method = 'ocr'`. Old tests updated: no-text now saves nothing; empty native pages receive a fake engine. Manual scanned-image verification deferred to Step 8.

### Step 6: Logging
- [x] Add the OCR log messages in `Extract_OCR.py` and `pipeline.py`; add the logging tests.
- Read first: `references/coding.md` (Logging), `references/testing.md` (Logging)
- Check: `pytest tests/ingestion -k logging -v` green; one failed ingestion produces exactly one `ERROR` record; no OCR text appears in `caplog.text` or in `logs/book_reader.log` after a sample run.
- Notes: 7 logging tests pass. Low-confidence errors log one `ERROR` with `page_number`, `confidence`, `threshold` and exception info; DEBUG logs scores only; `caplog.text` has no OCR text. File-log verification deferred to the Step 8 sample run.

### Step 7: Documentation and cleanup
- [x] Create `docs/OCR_layer-design.md` following the outline in `SKILL.md` (overview, architecture, how to run, decisions with reasons and any changes made during the work, behavior changes, test summary, unresolved issues, next steps; link to skill `database` instead of copying the schema); check `.gitignore`; remove unused code and imports.
- Check: the file exists and has all eight sections; every decision in this plan appears in it, marked as kept or changed; the commands in "How to run" work when copied as written; `git status` shows no database, log or temporary files.
- Notes: `docs/OCR_layer-design.md` has all eight sections and a kept/changed decision table. `.gitignore` already covers data, logs, DB and cache files; `git status` shows only intended source, test, config and doc changes. The `TESSERACT_CMD` example uses PowerShell syntax and was used for the real-engine run in Step 8.

### Step 8: Final verification
- [x] Run `pytest tests/ingestion -m "not ocr" -v`, `pytest tests/ingestion -m ocr -v` (if Tesseract is installed) and `pytest tests/`; fix any failure.
- [x] Ingest one scanned PDF and one image converted with `images_to_pdf`; inspect `books`, `pages`, `chunks`, `page_chunk`.
- [x] Report: architecture, how to run, design decisions, unresolved issues.
- [x] Move this plan to `docs/exec-plans/completed/` and update the exec-plan row in `AGENTS.md`.
- Notes: 89 non-OCR ingestion tests, 4 real-OCR tests (with `TESSERACT_CMD` set), and all 108 tests pass. Manual ingestion of a scanned PDF and an image-converted PDF stored `completed` books with one `ocr` page each, confidence 0.953, one chunk and one `page_chunk` link per book; reconstruction held and the log file contained no book text. After `vie` was installed, a Vietnamese image was converted with `images_to_pdf` and ingested with the default `vie+eng` engine: `completed`, `method='ocr'`, confidence 0.915, all expected words recognized. Committed real-engine tests remain English per the testing guide. Architecture, commands, decisions, behavior changes, limitations and next steps are reported in `docs/OCR_layer-design.md`.

## Out of scope

Handwriting, layout analysis (columns, tables), image preprocessing beyond rendering, sentence-aware chunking, vector search, embeddings, RAG, MCP.
