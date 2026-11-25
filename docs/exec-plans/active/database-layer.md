# Execution Plan: Database Layer

Status: active
Skill: `database` (`.opencode/skills/database/SKILL.md`)

## How to use this plan

- Work through the steps in order. Do not start a step until the previous one passes its check.
- Before each step, read the files listed under "Read first".
- After each step, run its "Check", then tick the box and write one line under "Notes".
- If a check fails, fix it before moving on. If a decision is unclear, stop and ask.
- Stay in scope: no OCR, PDF processing, vector search, embeddings, RAG or MCP.

## Decisions (already agreed)

1. Install `pytest`; create `requirements-dev.txt`.
2. Default DB path `data/book_reader.db`, overridable by env `BOOK_READER_DB_PATH`; add `data/` to `.gitignore`.
3. Add `CHECK` on `books.status` and `pages.method` in the DB; the repository validates as well.
4. Indexes: only `page_chunk(chunk_id)` is created explicitly. `pages(book_id, page_number)`, `chunks(book_id, chunk_index)` and `page_chunk(page_id)` are already covered by UNIQUE / primary key constraints.
5. The DB path is passed as a function parameter; settings only provide the default.
6. Duplicate `file_hash`: raise a clear exception (re-ingest logic is not a database concern).
7. Duplicate page or chunk: reject, no upsert.

## Steps

### Step 1: README
- [ ] Update `README.md` to describe the 4-table schema (books, pages, chunks, page_chunk).
- Read first: `skill database -> references/schema.md`
- Check: `git diff README.md` shows documentation changes only.
- Notes:

### Step 2: Configuration
- [ ] Create `config/settings.py`
- Read first: `ARCHITECTURE.md` (layering rules)
- Provides: default DB path (`data/book_reader.db`), env override `BOOK_READER_DB_PATH`.
- Check: `python -c "from config.settings import DB_PATH; print(DB_PATH)"` prints the path; setting the env var changes it.
- Notes:

### Step 3: Connection
- [ ] Create `src/database/connection.py`
- Read first: `config/settings.py`
- Provides: connection factory taking an optional `db_path`; context manager; `PRAGMA foreign_keys = ON` on every connection.
- Check: a quick script confirms `PRAGMA foreign_keys` returns 1 on a new connection.
- Notes:

### Step 4: Schema initialization
- [ ] Create `src/database/init_db.py`
- Read first: `skill database -> references/schema.md`, `src/database/connection.py`
- Provides: `init_db(db_path=None)` creating 4 tables (with CHECK constraints), the `page_chunk(chunk_id)` index, in one transaction, idempotent.
- Check: run `python -m src.database.init_db` twice with no error and no data loss.
- Notes:

### Step 5: Repository
- [ ] Create `src/database/repository.py`
- Read first: `references/schema.md`, `connection.py`
- Provides: create/get/list books (exclude `deleted` by default), update status, soft-delete; insert pages; get pages by book and page range; insert chunks; create page-chunk links; get chunks of a page; get pages of a chunk. Parameterized SQL only; type hints; no PDF/OCR logic.
- Check: import succeeds and a manual smoke test inserts one book, one page, one chunk and one link.
- Notes:

### Step 6: Tests
- [ ] Create `tests/database/` and `requirements-dev.txt`
- Read first: `skill database -> references/testing.md`
- Provides: pytest tests with a temporary SQLite DB covering all 10 required cases, plus tests for decisions 3, 6 and 7.
- Check: `pytest tests/database -v` all green.
- Notes:

### Step 7: Documentation and housekeeping
- [ ] Create `docs/database-design.md`; update `.gitignore`
- Provides: architecture overview, how to run, the decisions above with reasons, unresolved issues. `.gitignore` excludes `data/`, `*.db`, `*.db-journal`, `*.db-wal`, `*.db-shm`.
- Check: files exist; `git status` shows no database files.
- Notes:

### Step 8: Final verification
- [ ] Run `python -m src.database.init_db` and `pytest tests/database -v`; fix any failure.
- [ ] Report: architecture, how to run, design decisions, unresolved issues.
- [ ] Move this plan to `docs/exec-plans/completed/`.

## Out of scope

PDF extraction, OCR, chunking logic, vector search, embeddings, RAG, MCP.