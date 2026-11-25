---
name: book-reader-database
description: Designs and implements the SQLite database layer for the book-reader project (tables books, pages, chunks, page_chunk), including connection management, idempotent initialization, a repository module, pytest tests and design documentation. Use this skill whenever the task involves the book-reader database, SQLite schema, tables, indexes, migrations, repository functions, storing PDF page text, chunks, or page-chunk offsets, even if the user does not explicitly say "database skill".
---

# Book Reader — Database Layer

Build the persistent storage layer for `book-reader`, a PDF book reading system that provides structured book content to AI agents. The database stores book metadata, extracted text per PDF page, chunks generated from pages, and the page-chunk relationships. SQLite is used for the MVP.

## Before writing code

- Read the project's `README.md`.
- Read existing architecture and database docs if available (`ARCHITECTURE.md`, `docs/`).
- Understand the existing code structure.
- Do not introduce unnecessary technologies or dependencies.

## Schema

The full schema, constraints and offset semantics are in `references/schema.md`. Read it before writing `init_db.py` or `repository.py`. Follow it exactly.

Key points to keep in mind:
- Four tables: `books`, `pages`, `chunks`, `page_chunk`.
- `books.status = 'deleted'` is a soft delete. Never physically delete books in normal operation.
- Offsets in `page_chunk` are relative to `pages.content`, stored separately per page-chunk row.

## Implementation

### `src/database/connection.py`
- Create and manage SQLite connections.
- Run `PRAGMA foreign_keys = ON` on every connection.
- Use context managers where appropriate.
- Read the database location from project configuration (`config/settings.py`); never hardcode paths.

### `src/database/init_db.py`
- Create all four tables and the indexes listed in `references/schema.md`.
- Make initialization idempotent (`IF NOT EXISTS`).
- Use transactions where appropriate.
- Never drop or overwrite existing data.

### `src/database/repository.py`
Implement these operations:
- Create a book; retrieve a book by ID.
- List books, excluding soft-deleted ones by default.
- Update book status; soft-delete a book.
- Insert pages; retrieve pages by book and page range.
- Insert chunks.
- Create page-chunk relationships.
- Retrieve chunks associated with a page; retrieve pages associated with a chunk.

Keep SQL operations separate from business logic.

## Engineering principles

- Use Python type hints.
- Keep functions small and focused.
- Use parameterized SQL queries only.
- Do not mix database access with PDF/OCR processing.
- Do not add SQLAlchemy or any ORM unless explicitly requested.
- Do not implement vector search, embeddings, RAG, OCR, or MCP at this stage.
- Document important design decisions.
- Do not implement unrelated project modules.

## Testing

Use pytest with a temporary SQLite database. The list of required test cases is in `references/testing.md`. Read it before writing tests.

## Deliverables

Create:
- `config/settings.py`
- `src/database/connection.py`
- `src/database/init_db.py`
- `src/database/repository.py`
- `tests/database/`
- `docs/database-design.md`

Also update `.gitignore` to exclude generated database files and temporary database artifacts.

## Before finishing

1. Run database initialization.
2. Run all database tests.
3. Fix any failures.
4. Explain the implemented architecture and how to run it.
5. Report design decisions and any unresolved issues.