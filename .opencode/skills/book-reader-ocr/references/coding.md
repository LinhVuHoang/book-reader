# Coding Guide: OCR Ingestion

## Contents
- Engine choice and system requirements
- Dependencies and configuration
- Shared models and errors
- Input validation
- Image to PDF
- OCR extraction (`Extract_OCR.py`)
- Confidence scoring
- Chunker changes
- Pipeline changes
- Behavior changes to existing code
- Logging

## Engine choice and system requirements

Engine: **Tesseract 5**, used through `pytesseract`. Reasons: it needs no GPU, installs small, runs quickly on CPU, reports a per-word confidence from 0 to 100 (the scale of the 80 threshold), and has a Vietnamese model. It sits behind the `OcrEngine` interface, so PaddleOCR can replace it later if accuracy on real books is not enough.

System requirements (not installable with pip):
- The Tesseract program. On Windows install a Tesseract 5 build and make sure it is on `PATH`, or set `TESSERACT_CMD` to the full path of `tesseract.exe`.
- Language data for `eng` and `vie` (prefer the `tessdata_best` files). Without the right language data, accented Vietnamese text is misread.
- Check: `tesseract --list-langs` must list `eng` and `vie`.

## Dependencies and configuration

Add to `requirements.txt`: `pytesseract` and `Pillow`. PyMuPDF (already used) renders pages and converts images to PDF.

Add to `config/settings.py` (each overridable by an environment variable):
- `OCR_LANGUAGES` default `"vie+eng"` (`BOOK_READER_OCR_LANGUAGES`)
- `OCR_DPI` default `300` (`BOOK_READER_OCR_DPI`)
- `OCR_MIN_CONFIDENCE` default `80.0`, scale 0 to 100 (`BOOK_READER_OCR_MIN_CONFIDENCE`)
- `TESSERACT_CMD` default `None`, meaning use `PATH` (`TESSERACT_CMD`)

Register a pytest marker `ocr` in the project's pytest configuration (create `pytest.ini` if none exists). Tests that run the real Tesseract carry `@pytest.mark.ocr` and are skipped automatically when Tesseract or `vie` data is missing.

## Shared models and errors

Create `src/ingestion/models.py` and move the dataclasses there (update imports in the existing modules and tests):

```python
@dataclass(frozen=True)
class PageText:
    page_number: int                  # 1-based
    content: str
    method: Literal["text", "ocr"] = "text"
    confidence: float | None = None   # stored scale 0..1; None for native text

@dataclass(frozen=True)
class PageSpan:
    page_number: int
    start_offset: int
    end_offset: int                   # exclusive

@dataclass(frozen=True)
class ChunkSpec:
    chunk_index: int
    content: str
    spans: list[PageSpan]
```

Add to `src/ingestion/errors.py` (all subclass `IngestionError`):

| Exception | Raised when |
|---|---|
| `InvalidFormatError` | not a `.pdf`, wrong header, an image given to `ingest_pdf`, unsupported or corrupt image in `images_to_pdf` |
| `EmptyInputError` | zero-byte file, PDF with zero pages, empty image list |
| `OcrEngineError` | Tesseract is missing, or a language pack is missing, or the engine call fails |
| `LowConfidenceError` | an OCR page scores below the threshold (carries `page_number`, `confidence`, `threshold`) |
| `NoTextError` | already exists; now means: no page has text even after OCR |

## Input validation (`validators.py`)

`validate_pdf_file(file_path) -> Path`, in this order:
1. `FileNotFoundError` if the path does not exist.
2. `InvalidFormatError` if it is not a regular file.
3. `InvalidFormatError` if the suffix is not `.pdf` (case-insensitive). If the suffix is an image suffix, the message must say to convert it with `images_to_pdf`.
4. `EmptyInputError` if the size is 0 bytes.
5. `InvalidFormatError` if the first bytes are not `%PDF-` (catches a PNG renamed to `.pdf`).

A file with a valid header that PyMuPDF cannot open still raises `PdfReadError` from the extractor. A PDF with zero pages raises `EmptyInputError`.

## Image to PDF (`image_to_pdf.py`)

`images_to_pdf(image_paths, output_path) -> Path`
- Accept `.png .jpg .jpeg .tif .tiff .bmp .webp` (case-insensitive). Anything else raises `InvalidFormatError`.
- Empty list raises `EmptyInputError`; a zero-byte image raises `EmptyInputError`; an unreadable or corrupt image raises `InvalidFormatError`.
- Missing image raises `FileNotFoundError`. `output_path` must end with `.pdf` (else `InvalidFormatError`) and must not already exist (`FileExistsError`).
- One image becomes one page, in the given order. Use PyMuPDF: open the image, `convert_to_pdf()`, and insert it into the output document.
- An image that contains no text is not detected here; OCR finds it later and the pipeline raises `NoTextError`.

## OCR extraction (`Extract_OCR.py`)

```python
@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float | None      # 0..100; None when no word was recognised

class OcrEngine(Protocol):
    def recognize(self, image: "PIL.Image.Image") -> OcrResult: ...
```

`TesseractEngine(languages, tesseract_cmd=None)` implements `OcrEngine`. Its constructor raises `OcrEngineError` if Tesseract is not found or a requested language is missing (check with `pytesseract.get_languages`). It calls `pytesseract.image_to_data(..., output_type=Output.DICT)` once per page and builds both text and confidence from that single result:
- Keep only entries whose stripped text is non-empty and whose `conf` is at least 0 (Tesseract uses -1 for non-word rows).
- Build text by grouping words by `(block_num, par_num, line_num)`; join words in a line with a space, lines with `\n`, and separate paragraphs and blocks with one blank line.

`ocr_pages(file_path, page_numbers, engine=None, dpi=None, min_confidence=None) -> list[PageText]`
- Defaults come from settings; `engine=None` builds a `TesseractEngine`.
- For each page number (1-based): render with PyMuPDF at `dpi` into a Pillow image, call `engine.recognize`, normalize the text (below), and build a `PageText(method="ocr", ...)`.
- Return pages in the order of `page_numbers`. Close the document when finished.
- Wrap engine failures in `OcrEngineError`.
- Do not preprocess images beyond rendering at the configured DPI; Tesseract already binarizes. Heavier preprocessing is a later improvement.

Text normalization (OCR pages only, applied before the text is stored, so stored content equals chunked content): convert `\r\n` and `\r` to `\n`, strip trailing spaces on each line, collapse three or more consecutive newlines into two, and strip leading and trailing blank lines. Do not otherwise alter the text.

## Confidence scoring

- Page score = the mean of the kept word confidences (0 to 100). No kept words means an empty page: `content=""` and `confidence=None`.
- A page with text is **accepted when score >= `min_confidence`** (default 80, inclusive). 80.0 passes; 79.99 fails.
- A failing page raises `LowConfidenceError(page_number, confidence, threshold)` immediately (fail fast).
- Accepted pages store `confidence = score / 100` in `PageText` (0 to 1), which is what the database column requires.
- An empty OCR page is not an error by itself (blank pages exist in real books). It is stored with `method="ocr"`, `content=""`, `confidence=None`, and gets no `page_chunk` rows.

## Chunker changes (`chunker.py`)

Keep the chunking algorithm from `book-reader-pdf` unchanged; text and OCR pages use the same code. Change the module so mixed sources work:

1. Import the dataclasses from `models.py`. `PageText` now carries `method` and `confidence`; the chunker ignores them for the algorithm and never modifies them.
2. Add `merge_pages(native_pages, ocr_pages) -> list[PageText]`: combine the two lists into one list sorted by `page_number`. If a page number appears in both, keep the one with non-empty content (prefer the native page when both are non-empty or both empty). Raise `ValueError` if the merged result has gaps (page numbers must run 1..N).
3. `chunk_pages(pages, chunk_size, overlap_size)` now validates its input and raises `ValueError` for: duplicate page numbers, pages not in increasing order, or a non-string `content`. An empty list returns `[]`. Pages with empty content take part in the page list but contribute no characters and no spans.
4. Keep the invariant: joining the page slices of a chunk's spans reproduces `chunk.content` exactly.

## Pipeline changes (`pipeline.py`)

`ingest_pdf(file_path, db_path=None, chunk_size=None, overlap_size=None, ocr_engine=None) -> int`

1. `validate_pdf_file(file_path)`.
2. Compute the SHA-256; raise `DuplicateBookError` if it exists (before any OCR work).
3. `extract_pages` for native text; zero pages raises `EmptyInputError`.
4. For pages whose native content is empty after `strip()`, call `ocr_pages` with those page numbers (and `ocr_engine`). `LowConfidenceError` propagates.
5. `merge_pages`. If no merged page has non-empty content, raise `NoTextError`.
6. Only now touch the database: create the book (`processing`, `total_pages`), insert pages with their own `method` and `confidence`, run `chunk_pages`, insert chunks and `page_chunk` rows, set `completed`.
7. If anything fails after the book row exists, set `failed` and re-raise.

Steps 1 to 5 never write to the database, so an invalid, empty, no-text or low-confidence input leaves no rows in any table.

## Behavior changes to existing code

| Before (no OCR) | Now |
|---|---|
| Pages with no native text were stored empty | They are OCR'd; only pages OCR also finds empty are stored empty |
| `NoTextError`: book marked `failed` | `NoTextError`: nothing is saved, because the check happens before the first database write |
| Any `.pdf` path was opened | Suffix, size and `%PDF-` header are validated first |

Update the existing tests that asserted the old behavior, and say so in the step Notes.

## Logging

Follow the logging rules of `book-reader-pdf`. OCR additions:
- `INFO` (pipeline): OCR started (`pages_needing_ocr`, `languages`, `dpi`); OCR finished (`pages`, `mean_confidence`, elapsed seconds).
- `DEBUG` (`Extract_OCR.py`): per page `page_number`, `confidence`, `characters`.
- `WARNING`: an OCR page with no text (include `page_number`).
- `ERROR`: log once in `pipeline.py` with `logger.exception` when ingestion fails, including `LowConfidenceError` (`page_number`, `confidence`, `threshold`).
- Never log OCR text, page text or chunk text. Log counts, page numbers, scores and ids.