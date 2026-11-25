# Database Design — MVP

- **Status:** Accepted
- **Date:** 2026-11-25
- **Scope:** Chỉ tầng database. Không PDF/OCR/chunking/RAG/MCP/vector search.
- **Nguồn ưu tiên:** `.opencode/skills/database/references/schema.md` > `ARCHITECTURE.md` > `AGENTS.md` > `README.md`.
- Tài liệu này ghi nhận các quyết định từ `docs/exec-plans/active/0001-database-layer.md` và là nguồn quyết định khi triển khai.

## 1. Các quyết định đã duyệt

| # | Quyết định | Cách ghi nhận khi triển khai |
|---|---|---|
| 1 | Cài `pytest` và tạo `requirements-dev.txt` | `requirements-dev.txt` chứa `pytest>=8.0,<10`; lệnh kiểm tra: `python -m pytest tests/` |
| 2 | DB mặc định `data/book_reader.db`, override bằng env `BOOK_READER_DB_PATH`; bỏ qua `data/` trong git | `config/settings.py` chỉ cung cấp giá trị mặc định; `.gitignore` chứa `data/` và các artifact DB tạm |
| 3 | Thêm `CHECK(status)` và `CHECK(method)` ở DB | DDL enforce `status IN ('pending','processing','completed','failed','deleted')` và `method IN ('text','ocr')` |
| 4 | Bỏ 3 index trùng, chỉ giữ `page_chunk(chunk_id)` | Không tạo index cho `pages(book_id, page_number)`, `chunks(book_id, chunk_index)` hay `page_chunk(page_id)` |
| 5 | Truyền DB path qua tham số hàm | Mọi hàm repository nhận `db_path: Path | None = None`; nếu `None` thì dùng `settings.DATABASE_PATH`. Test dùng `tmp_path`, không monkeypatch global |
| 6 | `file_hash` trùng thì raise exception rõ ràng | Không trả book hiện có, không upsert; raise exception có thông điệp nêu rõ hash/book bị trùng |
| 7 | Page/chunk trùng thì reject, không upsert | Dùng `UNIQUE(book_id, page_number)` và `UNIQUE(book_id, chunk_index)`; tuyệt đối không dùng `INSERT ... ON CONFLICT` cho các trường hợp này |
| 8 | Sửa `README.md` nằm trong scope | `README.md` mục 4 đã được cập nhật từ 2 bảng sang 4 bảng |

## 2. Schema và ràng buộc

Schema gồm 4 bảng: `books`, `pages`, `chunks`, `page_chunk`.

### `books`

- `id`: `INTEGER PRIMARY KEY AUTOINCREMENT`.
- `title`, `file_path`: `NOT NULL`.
- `file_hash`: `UNIQUE`, `NOT NULL`; trùng thì raise exception rõ ràng theo quyết định #6.
- `total_pages`: `NOT NULL`, `CHECK(total_pages > 0)`.
- `status`: `NOT NULL`, `CHECK(status IN ('pending','processing','completed','failed','deleted'))` theo quyết định #3.
- `created_at`, `updated_at`: mặc định `CURRENT_TIMESTAMP`.
- `status = 'deleted'` là soft delete; không xóa vật lý book trong vận hành bình thường. `list_books` loại book đã xóa mềm theo mặc định.

### `pages`

- `id`: `INTEGER PRIMARY KEY AUTOINCREMENT`.
- `book_id`: `NOT NULL`, FK tới `books(id)`, `ON DELETE CASCADE`.
- `page_number`: `NOT NULL`, `CHECK(page_number > 0)`, `UNIQUE(book_id, page_number)`.
- `content`: `NOT NULL`.
- `method`: `NOT NULL`, `CHECK(method IN ('text','ocr'))` theo quyết định #3.
- `confidence`: `NULL` hoặc nằm trong `[0, 1]`; tiếp tục enforce bằng `CHECK(confidence IS NULL OR (confidence BETWEEN 0 AND 1))` để khớp rule của schema reference.
- `created_at`: mặc định `CURRENT_TIMESTAMP`.

### `chunks`

- `id`: `INTEGER PRIMARY KEY AUTOINCREMENT`.
- `book_id`: `NOT NULL`, FK tới `books(id)`, `ON DELETE CASCADE`.
- `chunk_index`: `NOT NULL`, `UNIQUE(book_id, chunk_index)`, thể hiện thứ tự chunk trong book.
- `content`: `NOT NULL`.
- `created_at`: mặc định `CURRENT_TIMESTAMP`.

### `page_chunk`

- Khóa chính ghép `(page_id, chunk_id)`.
- `page_id`: FK tới `pages(id)`, `ON DELETE CASCADE`.
- `chunk_id`: FK tới `chunks(id)`, `ON DELETE CASCADE`.
- `start_offset`, `end_offset`: `NOT NULL`, `CHECK(start_offset >= 0)`, `CHECK(end_offset >= start_offset)`.
- Offset tính theo Python Unicode string indexing và tương đối với `pages.content` của từng page.
- Một chunk có thể trải nhiều page; một page có thể thuộc nhiều chunk. Mỗi quan hệ lưu offset riêng.

## 3. Index

Chỉ tạo index sau theo quyết định #4:

```sql
CREATE INDEX IF NOT EXISTS idx_page_chunk_chunk_id ON page_chunk(chunk_id);
```

Không tạo các index trùng:

- `pages(book_id, page_number)`: đã được phủ bởi `UNIQUE(book_id, page_number)`.
- `chunks(book_id, chunk_index)`: đã được phủ bởi `UNIQUE(book_id, chunk_index)`.
- `page_chunk(page_id)`: đã được phủ bởi khóa chính `(page_id, chunk_id)`.

## 4. Nguyên tắc triển khai repository

- Dùng `sqlite3` chuẩn; không ORM, không dependency runtime mới.
- Mọi connection bật `PRAGMA foreign_keys = ON` và dùng `sqlite3.Row`.
- Mọi SQL nằm trong `src/database/init_db.py` và `src/database/repository.py`; dùng parameterized query.
- `init_db.py` idempotent (`IF NOT EXISTS`), không drop/overwrite dữ liệu cũ.
- `settings.DATABASE_PATH` là giá trị mặc định; `BOOK_READER_DB_PATH` có thể override; tham số `db_path` của repository có độ ưu tiên cao nhất.
- `updated_at` được cập nhật khi repository đổi status của book.
- Không trộn logic PDF/OCR/chunking vào tầng database.

## 5. Kiểm tra

- `python -m src.database.init_db`: chạy init nhiều lần không lỗi, không mất dữ liệu.
- `python -m pytest tests/`: dùng DB tạm qua `tmp_path`.
- Các case bắt buộc: init lặp, FK được enforce, trùng `page_number` bị từ chối, trùng `chunk_index` bị từ chối, `confidence` ngoài `[0, 1]` bị từ chối, 1 chunk ↔ nhiều page, 1 page ↔ nhiều chunk, offsets lưu độc lập, soft-delete ẩn book, xóa vật lý cascade sang các bảng liên quan.

## 6. Phạm vi ngoài MVP

Không implement vector search, embeddings, RAG, MCP, PDF extraction, OCR hay chunking trong phase này.
