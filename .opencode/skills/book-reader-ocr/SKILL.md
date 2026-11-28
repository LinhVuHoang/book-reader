---
name: book-reader-ocr
description: Adds OCR to the book-reader ingestion pipeline so scanned PDFs, and images converted to PDF, can be ingested. Pages without native text are rendered and read with Tesseract, scored with a confidence value (accepted at 80 or higher on a 0 to 100 scale, otherwise an error is raised and nothing is saved), merged with native-text pages, chunked and stored through the database repository. Includes input validation (PDF only, empty files, invalid formats, images without text), the Extract_OCR.py module, changes to chunker.py and pipeline.py, and pytest tests. Use this skill whenever the task involves OCR, scanned books, images of pages, Tesseract, OCR confidence, converting images to PDF, or mixing OCR and non-OCR pages in book-reader, even if the user does not say "OCR skill".
---

# Book Reader — OCR Ingestion

Extend the existing PDF ingestion layer (skill `book-reader-pdf`) so that scanned books can be ingested. Reuse `chunker.py` and `pipeline.py`; add `Extract_OCR.py` and the small modules around it. Do not build a second pipeline.

## Before writing code

- Read `AGENTS.md`, `ARCHITECTURE.md` and the active plan `docs/exec-plans/active/pdf-ocr-layer.md`.
- Read `docs/PDF_layer-design.md` and the existing `src/ingestion/` modules and tests. Match their style and keep them working.
- Read `src/database/repository.py` for the real function signatures. Do not change the database layer.

## Route the work

This skill has two parts. Read the matching reference before doing that part:

| You are about to... | Read first |
|---|---|
| Write or change code in `src/ingestion/`, `config/settings.py`, or dependency files | `references/coding.md` |
| Write or change tests in `tests/ingestion/` | `references/testing.md` |

Do both in the order the plan gives: for each step write the code, then its tests, then run the step's Check.

## Rules that must hold

- **Input is PDF only.** Anything else is rejected with `InvalidFormatError`. Images are accepted only after `images_to_pdf` has converted them.
- **Nothing is saved on rejected input.** Validation, OCR and the confidence check finish in memory before the first database write.
- **Confidence threshold:** an OCR page needs a score of 80 or higher (scale 0 to 100). Lower raises `LowConfidenceError` and nothing is saved. The database stores the score divided by 100, because the schema requires 0 to 1.
- **Reject bad data early:** empty file, zero pages, wrong format, and input with no text anywhere raise specific errors (see `references/coding.md`).
- **One chunker, one pipeline.** `chunker.py` handles text and OCR pages identically; `pipeline.py` decides per page whether OCR is needed.
- The OCR engine is used through the `OcrEngine` interface so it can be faked in tests.
- No SQL outside the database layer. No `print`. Never log page or OCR text.

## Engineering principles

- Use Python type hints; keep functions small and focused.
- Pass settings as parameters, with defaults from `config/settings.py`.
- Add only the dependencies named in the active plan.
- Do not implement vector search, embeddings, RAG, MCP, layout analysis or handwriting.
- Do not implement unrelated modules.

## Deliverables

- `src/ingestion/models.py`, `validators.py`, `image_to_pdf.py`, `Extract_OCR.py`
- changes to `src/ingestion/errors.py`, `chunker.py`, `pipeline.py` and `config/settings.py`
- tests under `tests/ingestion/`
- `docs/OCR_layer-design.md`

## Before finishing

1. Run `pytest tests/ingestion -m "not ocr" -v`, then `pytest tests/ingestion -m ocr -v` if Tesseract is installed, then `pytest tests/`.
2. Ingest a scanned sample PDF and an image converted with `images_to_pdf`, and inspect the stored rows.
3. Fix any failures.
4. Write `docs/OCR_layer-design.md` after the code and tests are done (see the outline below).
5. Report design decisions and unresolved issues.

## Outline of `docs/OCR_layer-design.md`

Write it from what was actually built, not from the plan. Keep it short and do not copy the database schema; link to skill `database` (`references/schema.md`) instead.

1. **Overview and scope**: what the OCR layer does and what it does not do.
2. **Architecture**: modules in `src/ingestion/` and the data flow, in a few lines; link to `ARCHITECTURE.md`.
3. **How to run**: installing Tesseract and the `vie` and `eng` data, settings and environment variables (`OCR_LANGUAGES`, `OCR_DPI`, `OCR_MIN_CONFIDENCE`, `TESSERACT_CMD`), example calls to `images_to_pdf` and `ingest_pdf`, and the test commands (`-m "not ocr"` and `-m ocr`).
4. **Decisions**: a table with the decision, the reason, and the alternatives considered. Start from the plan's Decisions and record every change made during the work.
5. **Behavior changes** compared with the non-OCR pipeline, and which old tests were updated.
6. **Test summary**: what is covered, and which tests were skipped and why (for example, no Tesseract installed).
7. **Unresolved issues and limitations**: for example, accuracy on real Vietnamese books not measured, the per-page threshold being strict, scans needing preprocessing, handwriting and layout not handled.
8. **Next steps**: suggested follow-ups, such as comparing PaddleOCR on real pages.
