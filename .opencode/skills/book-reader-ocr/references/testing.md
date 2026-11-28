# Testing Requirements: OCR Ingestion

Use pytest in `tests/ingestion/`. Keep every test from `book-reader-pdf` passing (update only those whose behavior changed; see `coding.md`, "Behavior changes").

## Test tools

- **Fake engine**: a `FakeOcrEngine` class implementing `OcrEngine` that returns scripted `OcrResult` values per call and counts calls. Almost all OCR logic is tested with it, so these tests run without Tesseract.
- **Sample files**, all generated at test time into `tmp_path` with PyMuPDF and Pillow (no binary fixtures):
  - native PDF: pages with inserted text.
  - scanned PDF: render a text PDF page to an image and place it in a new PDF as an image-only page (no text layer).
  - mixed PDF: some native pages, some image-only pages.
  - blank scanned page: a white image page.
  - fake PDF: a PNG file renamed to `.pdf`.
- **Real engine tests** carry `@pytest.mark.ocr` and are skipped when Tesseract or the `eng` data is missing. Use English text only in them.
- Use a temporary SQLite database initialized with `init_db`.

## Input validation
- A missing file raises `FileNotFoundError`; a directory raises `InvalidFormatError`.
- A 0-byte `.pdf` raises `EmptyInputError`.
- `.txt`, `.docx`, `.png`, `.jpg` raise `InvalidFormatError`; for image suffixes the message mentions `images_to_pdf`.
- A PNG renamed to `.pdf` raises `InvalidFormatError` (header check).
- A file with a valid `%PDF-` header but corrupt content raises `PdfReadError`.
- A PDF with zero pages raises `EmptyInputError`.
- `.PDF` in upper case is accepted.

## Image to PDF
- One image gives a one-page PDF; three images give three pages in the given order.
- An empty list raises `EmptyInputError`; a 0-byte image raises `EmptyInputError`.
- An unsupported suffix or a corrupt image raises `InvalidFormatError`.
- A missing image raises `FileNotFoundError`; an existing output path raises `FileExistsError`; an output not ending in `.pdf` raises `InvalidFormatError`.
- The produced PDF passes `validate_pdf_file`.

## OCR extraction (fake engine)
- Only the pages passed in are OCR'd (assert the call count).
- Results have `method == "ocr"`, keep their page numbers and order.
- A fake score of 92.5 gives `confidence == 0.925`.
- An empty OCR result gives `content == ""` and `confidence is None`, and is not an error.
- Text normalization: `\r\n` becomes `\n`, trailing spaces are removed, three or more newlines collapse to two.
- An engine that raises gives `OcrEngineError`.
- Missing Tesseract or a missing language pack gives `OcrEngineError` from `TesseractEngine` (simulate with a bad `tesseract_cmd` or a nonexistent language).
- Unit test the Tesseract data parsing with a hand-made `image_to_data` dict: `-1` confidences and blank words are ignored, the mean is computed from the rest, lines and paragraphs are rebuilt in order, and no words gives `confidence is None`.

## Confidence scoring
- A score of exactly 80.0 is accepted; 79.99 raises `LowConfidenceError`; 100 is accepted.
- The error carries `page_number`, `confidence` and `threshold`.
- With two pages scoring 95 and 60, the error names the page that scored 60.
- The threshold is configurable: `min_confidence=90` rejects a page scoring 85.
- Accepted scores are stored on the 0 to 1 scale (92 becomes 0.92) and satisfy the database CHECK.

## Chunking with mixed sources
- A text-only page list and the same content marked as OCR pages give identical chunks and spans.
- A mixed list (text, OCR, text) keeps the reconstruction invariant for every chunk.
- A chunk that crosses from a text page into an OCR page has correct spans on both.
- An empty page between two non-empty pages gets no spans.
- All pages empty returns `[]`; an empty list returns `[]`.
- Duplicate page numbers, out-of-order pages, and non-string content raise `ValueError`.
- `merge_pages`: prefers the non-empty page when a number appears in both lists, sorts by page number, raises `ValueError` on gaps.
- The chunker never changes `method` or `confidence`.
- All chunking tests from `book-reader-pdf` still pass.

## Pipeline end to end (fake engine)
- A native-only PDF: the engine is never called, behavior matches the non-OCR pipeline.
- A scanned PDF: pages stored with `method == "ocr"` and `confidence` between 0.8 and 1; chunks and `page_chunk` rows are stored and reconstructable.
- A mixed PDF: each page has the right `method`; native pages have `confidence IS NULL`.
- A low-confidence page: `LowConfidenceError` is raised and `books`, `pages`, `chunks` and `page_chunk` all have zero rows.
- A scanned PDF where every page OCRs to empty (image without text): `NoTextError`, zero rows.
- A scanned book with one blank page among text pages: the blank page is stored empty with `method == "ocr"` and has no links.
- A 0-byte file, a wrong extension, a fake PDF and a zero-page PDF each raise their error with zero rows.
- A duplicate file raises `DuplicateBookError` and the engine is not called.
- Images converted with `images_to_pdf` can be ingested; passing the image path directly to `ingest_pdf` raises `InvalidFormatError`.
- A failure while saving (patched repository function) sets the book to `failed`.
- Custom `chunk_size`, `overlap_size` and `ocr_engine` arguments are respected.

## Real Tesseract (`@pytest.mark.ocr`)
- A scanned page rendered from known English text is read and contains the expected words.
- A clean 300 DPI page scores at or above 80 and is stored with a `confidence` of at least 0.8.
- An end-to-end `ingest_pdf` of a scanned PDF with the default engine completes.
- A blank white image page converted to PDF raises `NoTextError`.

## Logging (`caplog`)
- OCR start logs an `INFO` record with the number of pages needing OCR.
- An empty OCR page logs a `WARNING` with its page number.
- `LowConfidenceError` produces exactly one `ERROR` record with exception info.
- No log record contains the text that was OCR'd (use a distinctive sentence).
- Per-page confidence appears at `DEBUG` level.