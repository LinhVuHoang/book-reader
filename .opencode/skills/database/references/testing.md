# Testing Requirements

Use pytest and a temporary SQLite database (for example, pytest's `tmp_path` fixture). Place tests in `tests/database/`.

Required test cases:
- Database initialization can run multiple times without error or data loss.
- Foreign key constraints are enforced.
- Duplicate page numbers within one book are rejected.
- Duplicate chunk indexes within one book are rejected.
- Invalid confidence values (below 0 or above 1) are rejected.
- A chunk can be associated with multiple pages.
- A page can be associated with multiple chunks.
- Offsets are stored independently for each page-chunk relationship.
- Soft-deleted books are excluded from normal listing.
- Physical deletion cascades to related records (pages, chunks, page_chunk).