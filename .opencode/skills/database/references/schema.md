# Database Schema

## Contents
- books
- pages
- chunks
- page_chunk
- Indexing

## Table: books

| Column | Type | Constraint |
|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| title | TEXT | NOT NULL |
| file_path | TEXT | NOT NULL |
| file_hash | TEXT | UNIQUE, NOT NULL |
| total_pages | INTEGER | NOT NULL, CHECK > 0 |
| status | TEXT | NOT NULL |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |
| updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

Allowed `status` values: `pending`, `processing`, `completed`, `failed`, `deleted`.

`deleted` represents soft deletion. Do not physically delete books during normal application operations.

## Table: pages

| Column | Type | Constraint |
|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| book_id | INTEGER | NOT NULL, FOREIGN KEY |
| page_number | INTEGER | NOT NULL, CHECK > 0 |
| content | TEXT | NOT NULL |
| method | TEXT | NOT NULL |
| confidence | REAL | NULL |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

Rules:
- `book_id` references `books(id)`.
- Use ON DELETE CASCADE for physical deletion.
- UNIQUE(book_id, page_number).
- `method` accepts `text` or `ocr`.
- `confidence` must be NULL or between 0 and 1.
- Native text extraction may have NULL confidence.

## Table: chunks

| Column | Type | Constraint |
|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| book_id | INTEGER | NOT NULL, FOREIGN KEY |
| chunk_index | INTEGER | NOT NULL |
| content | TEXT | NOT NULL |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

Rules:
- `book_id` references `books(id)`.
- Use ON DELETE CASCADE for physical deletion.
- UNIQUE(book_id, chunk_index).
- `chunk_index` represents the order of a chunk within a book.

## Table: page_chunk

| Column | Type | Constraint |
|---|---|---|
| page_id | INTEGER | NOT NULL, FOREIGN KEY |
| chunk_id | INTEGER | NOT NULL, FOREIGN KEY |
| start_offset | INTEGER | NOT NULL |
| end_offset | INTEGER | NOT NULL |

Rules:
- Composite primary key: (page_id, chunk_id).
- `page_id` references `pages(id)`.
- `chunk_id` references `chunks(id)`.
- Use ON DELETE CASCADE for physical deletion.
- `start_offset >= 0`.
- `end_offset >= start_offset`.

Offset semantics:
- Offsets are relative to the corresponding `pages.content`.
- Each row represents the portion of a chunk located on one page.
- A chunk can span multiple pages; a page can contain multiple chunks.
- Store both offsets separately for every page-chunk relationship.
- Use Python Unicode string indexing consistently when calculating offsets.

## Indexing

Create indexes where useful:
- pages(book_id, page_number)
- chunks(book_id, chunk_index)
- page_chunk(page_id)
- page_chunk(chunk_id)

Avoid redundant indexes when a primary key or UNIQUE constraint already provides the required index (for example, UNIQUE(book_id, page_number) already indexes that pair, and the composite primary key of `page_chunk` already covers lookups by `page_id`).