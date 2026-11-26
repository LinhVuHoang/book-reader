# Testing Requirements: PDF Ingestion

Use pytest. Put tests in `tests/ingestion/`. Generate sample PDFs at test time with PyMuPDF into `tmp_path` (for example `fitz.open()`, `page.insert_text(...)`), so no binary fixtures are committed. Use a temporary SQLite database initialized with `init_db`.

## Extraction (paging)
- A 3-page PDF returns 3 pages with `page_number` 1, 2, 3 in order.
- Each page contains the text that was written on it.
- A page with no text returns `content == ""` and keeps its page number.
- A missing file raises `FileNotFoundError`.
- A corrupt or non-PDF file raises `PdfReadError`.

## Chunking
- Every chunk is at most `chunk_size` characters.
- Consecutive chunks overlap by exactly `overlap_size` characters (except where the last chunk is shorter).
- `chunk_index` starts at 0 and is contiguous.
- Text shorter than `chunk_size` gives exactly one chunk.
- Empty input gives no chunks.
- A chunk that crosses a page boundary has spans for both pages with correct offsets.
- A page that is longer than `chunk_size` is covered by several chunks.
- Invariant: for every chunk, joining the page slices from its spans equals `chunk.content`.
- Invalid parameters raise `ValueError`: `chunk_size <= 0`, `overlap_size < 0`, `overlap_size >= chunk_size`.
- Unicode text (for example Vietnamese with diacritics) gives correct offsets.

## Logging
Use pytest's `caplog` fixture; do not call `setup_logging()` in these tests (except the setup tests below).
- A successful `ingest_pdf` logs an `INFO` start and an `INFO` completion message that contains the `book_id`.
- A page with no text logs a `WARNING` that contains its page number.
- A duplicate file logs a `WARNING` and raises `DuplicateBookError`.
- A failure during saving logs exactly one `ERROR` record with exception info, and the book ends with `status == "failed"`.
- No log record contains the text of a page or chunk (use a distinctive sentence in the test PDF and assert it never appears in `caplog.text`).
- `setup_logging()` called twice does not add duplicate handlers.
- `setup_logging()` creates the log directory and file under a temporary path.

## Saving to the database (end to end)
- `ingest_pdf` returns a `book_id`; the book has `status == "completed"`, the right `total_pages`, a 64-character hash, and a title.
- The number of stored pages equals the PDF page count, with `method == "text"` and `confidence IS NULL`.
- Stored chunks match the output of `chunk_pages` for the same pages and parameters.
- `page_chunk` rows match the spans, and for every stored chunk, joining the stored page slices reproduces the stored chunk content.
- Empty pages are stored but have no `page_chunk` rows.
- Ingesting the same file twice raises `DuplicateBookError` and creates no extra rows.
- A PDF with no extractable text raises `NoTextError` and the book ends with `status == "failed"`.
- Custom `chunk_size` and `overlap_size` passed to `ingest_pdf` are respected.
- If saving fails midway (for example a patched repository function raises), the book ends with `status == "failed"`.
