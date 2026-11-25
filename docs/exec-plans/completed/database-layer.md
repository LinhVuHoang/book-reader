# Execution Plan: Database Layer

Status: completed
Completed: 2026-11-25
Skill: `database` (`.opencode/skills/database/SKILL.md`)
Decision source: `docs/database-design.md`

## How to use this plan

- Work through the steps in order. Do not start a step until the previous one passes its check.
- Before each step, read the files listed under "Read first".
- After each step, run its "Check", then tick the box and write one line under "Notes".
- If a check fails, fix it before moving on. If a decision is unclear, stop and ask.
- Stay in scope: no OCR, PDF processing, vector search, embeddings, RAG or MCP.

## Decisions (already agreed)

1. Install `pytest`; create `requirements-dev.txt`.
2. Default DB path `data/book_reader.db`, overridable by env `BOOK_READER_DB_PATH`; add `data/` to `.gitignore`.
3. Add `CHECK` on `books.status`, `pages.method` and the `pages.confidence` range in the DB; duplicate `file_hash` is validated in the repository with a clear exception.
4. Indexes: only `page_chunk(chunk_id)` is created explicitly. `pages(book_id, page_number)`, `chunks(book_id, chunk_index)` and `page_chunk(page_id)` are already covered by UNIQUE / primary key constraints.
5. The DB path is passed as a function parameter; settings only provide the default.
6. Duplicate `file_hash`: raise `DuplicateBookHashError`.
7. Duplicate page or chunk: reject, no upsert.
8. Updating `README.md` to the 4-table schema is in scope.

## Steps

### Step 1: README
- [x] Update `README.md` to describe the 4-table schema (books, pages, chunks, page_chunk).
- Read first: `skill database -> references/schema.md`
- Check: `README.md:86` describes SQLite with four tables.
- Notes: Đã có sẵn; `git diff README.md` rỗng vì thay đổi đã được commit trong `e795bb0`.

### Step 2: Configuration
- [x] Create `config/settings.py`
- Read first: `ARCHITECTURE.md` (layering rules)
- Provides: default DB path (`data/book_reader.db`), env override `BOOK_READER_DB_PATH`.
- Check: `python -c "from config.settings import DATABASE_PATH; print(DATABASE_PATH)"` prints the path; setting the env var changes it.
- Notes: Plan cũ ghi `DB_PATH`; design doc và code dùng `DATABASE_PATH`. Đã kiểm tra default và env override đều đúng.

### Step 3: Connection
- [x] Create `src/database/connection.py`
- Read first: `config/settings.py`
- Provides: connection factory taking an optional `db_path`; context manager; `PRAGMA foreign_keys = ON` on every connection.
- Check: a quick script confirms `PRAGMA foreign_keys` returns 1 on a new connection.
- Notes: Kết quả `1 True` (foreign keys bật, `sqlite3.Row` được dùng).

### Step 4: Schema initialization
- [x] Create `src/database/init_db.py`
- Read first: `skill database -> references/schema.md`, `src/database/connection.py`
- Provides: `init_db(db_path=None)` creating 4 tables (with CHECK constraints), the `page_chunk(chunk_id)` index, in one transaction, idempotent.
- Check: run `python -m src.database.init_db` twice with no error and no data loss.
- Notes: CLI chạy 2 lần OK; trên DB tạm, book vẫn tồn tại sau init lần 2 (`True`).

### Step 5: Repository
- [x] Create `src/database/repository.py`
- Read first: `references/schema.md`, `connection.py`
- Provides: create/get/list books (exclude `deleted` by default), update status, soft-delete; insert pages; get pages by book and page range; insert chunks; create page-chunk links; get chunks of a page; get pages of a chunk. Parameterized SQL only; type hints; no PDF/OCR logic.
- Check: import succeeds and a manual smoke test inserts one book, one page, one chunk and one link.
- Notes: Smoke test trả `1 1 1 (1, 1, 0, 3)`; SQL chỉ nằm trong `init_db.py` và `repository.py`.

### Step 6: Tests
- [x] Create `tests/database/` and `requirements-dev.txt`
- Read first: `skill database -> references/testing.md`
- Provides: pytest tests with a temporary SQLite DB covering all 10 required cases, plus tests for decisions 3, 6 and 7.
- Check: `pytest tests/database -v` all green.
- Notes: `15 passed`, 1 warning từ plugin `anyio` về `CallSpec2` (không phải code dự án).

### Step 7: Documentation and housekeeping
- [x] Create `docs/database-design.md`; update `.gitignore`
- Provides: architecture overview, how to run, the decisions above with reasons, unresolved issues. `.gitignore` excludes `data/`, `*.db`, `*.db-journal`, `*.db-wal`, `*.db-shm`.
- Check: files exist; `git status` shows no database files.
- Notes: Cả hai file tồn tại; `git status` sạch và `git check-ignore` xác nhận DB artifacts bị bỏ qua.

### Step 8: Final verification
- [x] Run `python -m src.database.init_db` and `pytest tests/database -v`; fix any failure.
- [x] Report: architecture, how to run, design decisions, unresolved issues.
- [x] Move this plan to `docs/exec-plans/completed/`.
- Notes: Architecture gồm `config/settings.py` (default path/env), `connection.py` (connect/context manager), `init_db.py` (DDL idempotent), `repository.py` (SQL + dataclasses), `tests/database/` (pytest fixtures/tests). Chạy bằng `python -m src.database.init_db` và `python -m pytest tests/`.

## Verification summary

- `python -m src.database.init_db`: OK, chạy nhiều lần được.
- `python -m pytest tests/database -v`: 15 passed, 1 warning ngoài.
- `python -m compileall -q config src tests`: OK.
- `git check-ignore -v data/book_reader.db data/book_reader.db-wal custom-step2.db`: tất cả bị ignore.

## Unresolved issues

- Chưa có migration/schema versioning; `CREATE TABLE IF NOT EXISTS` không tự cập nhật DB đã tồn tại.
- `DATABASE_PATH` được resolve lúc import `config.settings`; đổi env sau khi import cần reload module hoặc restart process.
- `CURRENT_TIMESTAMP` có độ chính xác theo giây.
- `delete_book_physically()` chỉ dành cho kiểm tra cascade/bảo trì; luồng nghiệp vụ dùng soft delete.
- Chưa có lệnh lint/typecheck được định nghĩa trong repo.
- Warning pytest từ plugin `anyio` cần được xử lý khi nâng cấp lên pytest 10.

## Out of scope

PDF extraction, OCR, chunking logic, vector search, embeddings, RAG, MCP.
