# Book Reader — PDF Reader for AI Agents

An agent-powered PDF book reader that converts digital and scanned books into structured, page-level data, allowing AI agents to retrieve, summarize, and answer questions about specific pages through MCP tools.

## 1. Overview

**Book Reader** is a tool designed to help AI agents interact with PDF books by title and page number.

Instead of running OCR every time a user asks a question, the system processes each book once, extracts its text, and stores the results in a local database. Subsequent requests retrieve the preprocessed content directly, making page-level access fast and cost-efficient.

### Key Features

- **PDF Processing:** Extract text from digital PDFs and perform OCR on scanned pages.
- **One-time OCR:** Process each book once and reuse the extracted content.
- **Page-level Storage:** Store extracted text and metadata for individual pages.
- **MCP Integration:** Expose book ingestion and page retrieval through MCP tools.
- **Agentic Workflow:** Separate planning, generation, and evaluation responsibilities.
- **Hallucination Control:** Validate page coverage and check whether generated summaries are grounded in source content.
- **Iterative Refinement:** Allow the planner and generator to retry failed requests, with a maximum of three iterations.

## 2. System Architecture

The system consists of two main workflows:

1. **Ingestion Pipeline:** Processes PDF books and stores extracted text.
2. **Agent Execution Pipeline:** Retrieves stored content and generates answers based on user requests.

### Ingestion Pipeline

PDF → Page Extraction → Text Detection → OCR (if needed) → SQLite Database

- Digital PDFs: Extract existing text using PyMuPDF.
- Scanned PDFs: Perform OCR using RapidOCR.
- Store extracted text, extraction method, and OCR confidence for each page.

### Agent Execution Pipeline

User Request → Planner → Generator → Evaluator → Final Answer

**Planner**
- Understand the user's request.
- Identify the target book and requested page range.
- Validate book and page availability.
- Divide large requests into batches of at most 10 pages.
- Generate a structured execution plan in JSON.

**Generator**
- Execute the planner's instructions.
- Retrieve page content through MCP tools.
- Summarize individual batches.
- Combine batch summaries into a coherent response.

**Evaluator**
- Code-based validation:
  - Check whether all requested pages have been retrieved.
  - Detect missing or low-confidence OCR content.
  - Validate page coverage.
- LLM-based evaluation:
  - Check whether the generated summary is supported by the source text.
  - Identify unsupported claims or hallucinations.
  - Provide structured feedback for regeneration.

**Retry Mechanism**

If evaluation fails, feedback is returned to the planner/generator for refinement.

Maximum retry attempts: **3 iterations**.

Simple page retrieval requests bypass the LLM-based planning and evaluation stages to reduce latency and API costs.

## 3. Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| PDF Processing | PyMuPDF |
| OCR | RapidOCR |
| OCR Benchmark | Tesseract |
| Database | SQLite |
| MCP Server | FastMCP / Official MCP SDK |
| Agent Planner | LLM API |
| Generator | LLM API + MCP Client |
| Evaluator | Python + LLM API |
| Data Format | JSON |

## 4. Database Design

The database uses SQLite with two primary tables.

### `books`

Stores book-level metadata.

| Field | Description |
|---|---|
| `id` | Unique book identifier |
| `title` | Book title |
| `file_path` | Original PDF path |
| `total_pages` | Total number of pages |
| `created_at` | Ingestion timestamp |

### `pages`

Stores extracted content at page level.

| Field | Description |
|---|---|
| `id` | Unique page identifier |
| `book_id` | Reference to the book |
| `page_number` | Original PDF page number |
| `content` | Extracted page text |
| `method` | Extraction method: text extraction or OCR |
| `confidence` | OCR confidence score |
| `created_at` | Processing timestamp |

Each page is associated with a book through `book_id`.

## 5. MCP Tools

The MCP server exposes three tools:

| Tool | Description |
|---|---|
| `ingest_book` | Process a PDF book and store its extracted pages |
| `list_books` | Retrieve available books and their metadata |
| `get_pages` | Retrieve content from specified pages or page ranges |

### Example Usage

**List available books**

```json
{
  "tool": "list_books",
  "arguments": {}
}
```

**Retrieve specific pages**

```json
{
  "tool": "get_pages",
  "arguments": {
    "book_title": "Book A",
    "start_page": 10,
    "end_page": 15
  }
}
```

*Note: These are illustrative tool-call examples. Actual MCP schemas will be defined during implementation.*

## 6. Project Workflow

### Phase 1 — Book Ingestion

1. Load a PDF from an allowed directory.
2. Extract individual pages.
3. Detect whether each page contains selectable text.
4. Extract existing text or run OCR when necessary.
5. Store page content and metadata in SQLite.
6. Validate the ingestion results.

### Phase 2 — MCP Server

1. Implement the three MCP tools.
2. Define input schemas and validation rules.
3. Restrict file access to an explicitly allowed directory.
4. Test integration with Claude Desktop or Claude Code.

### Phase 3 — Agent Execution

1. Implement a generator using a fixed execution plan.
2. Integrate MCP client for page retrieval.
3. Add code-based evaluation.
4. Implement an LLM-based planner.
5. Add LLM-based evaluation and feedback loops.

### Phase 4 — Testing and Benchmarking

1. Prepare 15–20 representative user queries.
2. Evaluate page retrieval accuracy.
3. Measure OCR Character Error Rate (CER).
4. Compare OCR performance on CPU and GPU.
5. Evaluate agent reliability and API costs.

## 7. Evaluation Metrics

### OCR Evaluation

| Metric | Purpose |
|---|---|
| Character Error Rate (CER) | Measure character-level OCR accuracy |
| Processing Time | Measure OCR latency per page |
| CPU vs GPU | Compare inference speed across hardware |
| Confidence | Identify potentially unreliable OCR results |

CER is calculated as:

\[
CER = \frac{S+D+I}{N}
\]

Where:
- S: Substitutions
- D: Deletions
- I: Insertions
- N: Number of characters in the reference text

### Agent Evaluation

| Metric | Purpose |
|---|---|
| First-pass Success Rate | Percentage of requests passing evaluation on the first attempt |
| Average Iterations | Average number of execution attempts |
| Page Coverage | Percentage of requested pages successfully retrieved |
| Hallucination Rate | Percentage of generated answers containing unsupported claims |
| Cost per Request | Average LLM API cost per user request |

## 8. Design Principles & Security

- **Process Once, Retrieve Many:** Avoid repeated OCR inference by persisting extracted page content.
- **Separation of Concerns:** Keep ingestion, retrieval, planning, generation, and evaluation independent.
- **Controlled Context Size:** Limit each retrieval batch to a maximum of 10 pages.
- **Untrusted Document Content:** Treat OCR output and PDF text as untrusted data, never as agent instructions.
- **Restricted File Access:** Only allow ingestion from explicitly configured directories.
- **Cost Optimization:** Bypass unnecessary LLM calls for straightforward page retrieval.
- **Grounded Generation:** Require generated summaries to be supported by retrieved source content.

## 9. Project Roadmap

- [ ] Implement PDF ingestion pipeline.
- [ ] Support digital and scanned PDFs.
- [ ] Integrate RapidOCR and Tesseract.
- [ ] Implement SQLite database.
- [ ] Implement MCP server and three tools.
- [ ] Test MCP integration with Claude Desktop / Claude Code.
- [ ] Build generator with a fixed execution plan.
- [ ] Implement code-based evaluator.
- [ ] Implement LLM-based planner.
- [ ] Implement LLM-based evaluator and retry mechanism.
- [ ] Prepare evaluation dataset.
- [ ] Benchmark OCR performance on CPU and GPU.
- [ ] Evaluate agent reliability, hallucination rate, and API costs.

## 10. Future Improvements

Potential extensions beyond the initial scope:

- Semantic search and RAG for book-level knowledge retrieval.
- Advanced image preprocessing for low-quality scanned documents.
- VLM-based fallback for complex page layouts.
- Better OCR confidence calibration.
- Support for multiple document formats.
- Persistent execution logs and observability.

---

**Project Focus:** OCR Engineering · MCP · Agentic AI · Harness Engineering · LLM Evaluation