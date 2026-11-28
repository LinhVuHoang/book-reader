# book-reader

`book-reader` is a PDF book reading system that provides structured book content (pages and chunks) to AI agents. The MVP stores data in SQLite.

## Where to look

Read only the documents relevant to the current task.

| Task | Read |
|---|---|
| Overall design, module boundaries, data flow | `ARCHITECTURE.md` |
| Database schema, repository, tests | skill `database` (`.opencode/skills/database/SKILL.md`) |
| How the database layer was built, how to run it | `docs/database-design.md` |
| PDF ingestion (no OCR): extract pages, chunk, save to database, logging | skill `book-reader-pdf` (`.opencode/skills/book-reader-pdf/SKILL.md`) |
| How the PDF ingestion layer was built, how to run it | `docs/PDF_layer-design.md` |
| OCR ingestion: scanned PDFs and images (converted to PDF), confidence check, mixed text and OCR pages | skill `book-reader-ocr` (`.opencode/skills/book-reader-ocr/SKILL.md`) |
| How the OCR layer was built, how to run it | `docs/OCR_layer-design.md` |
| Other design decisions and rationale | `docs/design-docs/` |
| Current task and progress | `docs/exec-plans/active/` (none currently)
| Finished plans (history only) | `docs/exec-plans/completed/` (database, PDF ingestion, OCR ingestion: `pdf-ocr-layer.md`) |

## Rules

- Only read documents related to the current task; do not load everything.
- If documents conflict, the more specific one wins (a skill or design doc over this file).
- Keep layers separate: database access (`src/database/`) must not be mixed with PDF processing (`src/ingestion/`). The ingestion layer writes to the database only through `repository.py`.
- Do not add dependencies beyond those required by a skill or the active plan.
- Stay within the current scope. Do not implement vector search, embeddings, RAG, or MCP until a plan in `docs/exec-plans/active/` says so.
- Ingestion accepts PDF files only. Images must first be converted to PDF (`images_to_pdf`); other formats are rejected.
- OCR pages need a confidence of at least 80 (scale 0 to 100). A lower score raises an error and nothing is saved to the database.
- Do not hardcode paths, OCR settings or default chunk settings; read them from `config/settings.py`.
- Use the `logging` module, never `print`, and never log book text, including OCR text (log counts, page numbers, scores and ids only).
- `docs/exec-plans/active/` holds the plans in progress. Read the plan that matches the current task. If more than one matches or none does, ask which one to use.
- When working from an exec plan, follow its steps in order, tick completed steps, and add notes.
- When a plan is finished, move it to `docs/exec-plans/completed/`.
- Record important design decisions in `docs/design-docs/`; database decisions go in `docs/database-design.md`, PDF ingestion decisions in `docs/PDF_layer-design.md` and OCR decisions in `docs/OCR_layer-design.md`.
## Commands

```
pytest tests/                       # run all tests
pytest tests/ingestion -m "not ocr" # ingestion tests that do not need Tesseract installed
pytest tests/ingestion -m ocr       # tests that run the real Tesseract engine
tesseract --list-langs              # must list eng and vie
python -m src.database.init_db      # initialize the database
```