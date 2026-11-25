# Exec Plan: Database Layer (MVP)

- **Status:** Draft — chờ quyết định các điểm mở
- **Created:** 2026-11-25
- **Scope:** Chỉ tầng database. Không PDF/OCR/chunking/RAG/MCP/vector search.
- **Nguồn ưu tiên:** `.opencode/skills/database/references/schema.md` + `testing.md` > `ARCHITECTURE.md` > `AGENTS.md` > `README.md`.

## 1. Context

- Repo gần như trống: mới có `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `.opencode/`.
- Chưa có `config/`, `src/`, `tests/`, `.gitignore` gốc, `requirements`, `pytest.ini`.
- Python 3.12.10; `pytest` chưa cài.
- Xung đột: `README.md:88` mô tả 2 bảng; `ARCHITECTURE.md:15` + skill mô tả 4 bảng → **chọn 4 bảng** (`books`, `pages`, `chunks`, `page_chunk`).

## 2. Quyết định thiết kế đề xuất

1. Dùng `sqlite3` chuẩn; **không ORM**, không dependency runtime mới.
2. Schema y hệt `references/schema.md`: 4 bảng, `status` ∈ {pending, processing, completed, failed, deleted}, `deleted` = soft delete, FK `ON DELETE CASCADE`, offsets Unicode theo `pages.content`.
3. Index: bỏ các index trùng UNIQUE/PK (`pages(book_id,page_number)`, `chunks(book_id,chunk_index)`, `page_chunk(page_id)`); **chỉ tạo `page_chunk(chunk_id)`** theo cảnh báo `schema.md:95`.
4. `config/settings.py` là nguồn cấu hình duy nhất; hỗ trợ override bằng env `BOOK_READER_DB_PATH`, mặc định `data/book_reader.db`.
5. Mọi hàm repository nhận `db_path: Path | None = None` (fallback `settings.DATABASE_PATH`) hoặc connection — để test dùng `tmp_path` mà không monkeypatch global.
6. `DATETIME` lưu dạng string ISO/CURRENT_TIMESTAMP; không dùng adapter datetime đã deprecated trong Python 3.12.
7. `updated_at` được cập nhật trong repository khi đổi status (không dùng trigger).
8. Không thêm `CHECK` cho `status`/`method` ngoài schema; validate ở repository (tránh lệch schema).

## 3. Các bước triển khai

1. Tạo cấu trúc package + `config/settings.py` + `.gitignore` gốc.
2. `src/database/connection.py`: `sqlite3.connect`, `PRAGMA foreign_keys = ON`, `row_factory = sqlite3.Row`, context manager commit/rollback/close.
3. `src/database/init_db.py`: DDL idempotent (`IF NOT EXISTS`), transaction, index, entry point `python -m src.database.init_db`.
4. `src/database/repository.py`: create/get book, list (ẩn deleted), update status, soft-delete, insert pages, get pages theo book + range, insert chunks, tạo page_chunk, get chunks theo page, get pages theo chunk (kèm offsets). Type hints + parameterized SQL, tách biệt PDF/OCR.
5. `tests/database/`: fixture DB tạm; 10 case bắt buộc:
   - init chạy nhiều lần không lỗi/mất data
   - FK được enforce
   - trùng `page_number` trong 1 book bị từ chối
   - trùng `chunk_index` trong 1 book bị từ chối
   - `confidence` < 0 hoặc > 1 bị từ chối
   - 1 chunk ↔ nhiều page
   - 1 page ↔ nhiều chunk
   - offsets lưu độc lập cho từng quan hệ
   - book bị soft-delete bị loại khỏi list
   - xóa vật lý cascade sang pages/chunks/page_chunk
6. `docs/database-design.md`: ghi quyết định trên + cách chạy.
7. Verify: `python -m src.database.init_db`, `python -m pytest tests/`, sửa lỗi nếu có.

## 4. File sẽ tạo

| File | Nội dung |
|---|---|
| `config/__init__.py`, `src/__init__.py`, `src/database/__init__.py` | Package markers |
| `config/settings.py` | `DATABASE_PATH`, env override |
| `src/database/connection.py` | Connection/PRAGMA/context manager |
| `src/database/init_db.py` | DDL + CLI |
| `src/database/repository.py` | Toàn bộ SQL |
| `tests/database/conftest.py` | Fixture `tmp_path` |
| `tests/database/test_init_db.py` | Init/FK/constraints/cascade |
| `tests/database/test_repository.py` | Book/pages/chunks |
| `tests/database/test_relationships.py` | page_chunk + offsets + soft delete |
| `docs/database-design.md` | Quyết định thiết kế |
| `.gitignore` (gốc) | `*.db`, `*.sqlite*`, `data/`, `__pycache__/`, `.pytest_cache/` |
| Tùy chọn: `requirements-dev.txt`, `pytest.ini` | Chỉ khi được duyệt cài pytest |

## 5. Điểm mở (cần xác nhận trước khi code)

1. Cài `pytest` + tạo `requirements-dev.txt`? (`AGENTS.md:24` cấm dep mới nếu chưa yêu cầu.)
2. DB path mặc định `data/book_reader.db` + env `BOOK_READER_DB_PATH` — đồng ý không?
3. Thêm `CHECK(status)`/`CHECK(method)` hay chỉ validate ở repository?
4. Index: tạo 4 index theo danh sách hay bỏ 3 index trùng như đề xuất?
5. Inject DB path qua tham số hàm hay monkeypatch settings?
6. `file_hash` trùng: raise hay trả book hiện có (re-ingest)?
7. Duplicate page/chunk: reject nghiêm ngặt hay upsert?
8. Có sửa `README.md` (2 bảng → 4 bảng) trong scope này không?

## 6. Definition of Done

- Chạy init 2 lần liên tiếp không lỗi, không mất dữ liệu.
- `python -m pytest tests/` toàn bộ pass.
- Không SQL ngoài `init_db.py`/`repository.py`; không hardcode path; không dependency runtime mới.
