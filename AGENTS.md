# book-reader

`book-reader` is a PDF book reading system that provides structured book content (pages and chunks) to AI agents. The MVP stores data in SQLite.

## Where to look

Read only the documents relevant to the current task.

| Task | Read |
|---|---|
| Overall design, module boundaries | `ARCHITECTURE.md` |
| Database schema, repository, tests | skill `database` (`.opencode/skills/database/SKILL.md`) |
| How the database layer was built, how to run it | `docs/database-design.md` |
| Other design decisions and rationale | `docs/design-docs/` |
| Current task and progress | `docs/exec-plans/active/` |
| Finished plans (history only) | `docs/exec-plans/completed/` |

## Rules

- Only read documents related to the current task; do not load everything.
- If documents conflict, the more specific one wins (a skill or design doc over this file).
- Keep layers separate: database access must not be mixed with PDF/OCR processing.
- Do not add dependencies beyond those required by a skill or the active plan.
- Stay within the current scope. Do not implement vector search, embeddings, RAG, or MCP until a plan in `docs/exec-plans/active/` says so.
- Do not hardcode paths; read them from `config/settings.py`.
- `docs/exec-plans/active/` holds the plans in progress. Read the plan that matches the current task. If more than one matches or none does, ask which one to use.
- When working from an exec plan, follow its steps in order, tick completed steps, and add notes.
- When a plan is finished, move it to `docs/exec-plans/completed/`.
- Record important design decisions in `docs/design-docs/`; database decisions go in `docs/database-design.md`.

## Commands

```
pytest tests/                    # run all tests
python -m src.database.init_db   # initialize the database
```