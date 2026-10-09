# Document RAG with SQL analysis

The assistant combines two evidence paths in the existing Streamlit app:

- **SQL:** reviewed parameterized queries calculate filtered values, rates and rankings.
- **RAG:** semantic retrieval supplies project explanations with citations and inspectable source passages.

Gemini chooses `search_documents`, `query_analysis`, or both. No model-generated SQL is executed.
Explicit requests for explanations or project methods also enforce retrieval in the application when the model skips its search tool. This preserves the SQL results while supplying passages before the final explanation.

## Knowledge base

Only these four files are indexed:

| File | Explains |
|---|---|
| `docs/metric_contract.md` | Metric eligibility, denominators, time coverage and evidence limitations |
| `docs/cleaning_decisions.md` | Duplicate rules, missing values, normalization and modeling decisions |
| `docs/data_dictionary.md` | Table grain, columns, flags and money units |
| `docs/dataset_inventory.md` | Public Kaggle source files, columns and source profiling |

These are project-authored documents, not official Amazon policies. Raw order rows, `.env`, credentials, arbitrary files and user uploads are not indexed. The explicit allowlist is in `assistant/rag.py`.

The current corpus contains 17 passages. Chunks preserve whole source lines, including table rows, and retain title, section, relative filename, content hash and line range. Each passage has at most 1,600 characters. Larger tables may span several passages.

## Build and use

This computer's index is already built. Open the usual **Start AI Analyst.cmd** launcher; no Power BI or database refresh is required.

To rebuild after changing a knowledge document, double-click **Build Knowledge Index.cmd**, or run:

```powershell
.\.venv-assistant\Scripts\python.exe -m assistant.rag build
.\.venv-assistant\Scripts\python.exe -m assistant.rag status
```

The existing `GEMINI_API_KEY` in `.env` is used. The optional `GEMINI_EMBEDDING_MODEL` setting defaults to the tested text embedding model `gemini-embedding-001`. The generation model remains `gemini-3.5-flash-lite`.

Documents use `RETRIEVAL_DOCUMENT`; queries use `RETRIEVAL_QUERY`. Embeddings have 768 dimensions and are explicitly normalized. Cosine similarity searches the local JSON vector index, returning at most four passages with similarity at least 0.5. A search score is not an answer-confidence probability. With this small corpus, a separate vector database or retrieval framework is unnecessary.

The portable index is stored in `data/knowledge/index.json`, excluded from Git. File fingerprints, source content, dimensions and model must match before search can run. Missing or changed documents produce an actionable rebuild message; app startup never silently incurs an index-building API bill. Index writes replace the file only after a complete build.

Google's [embedding documentation](https://ai.google.dev/gemini-api/docs/embeddings) describes the task types and dimensionality. Indexing sends the four allowlisted project documents to Gemini; a search sends its query for embedding; generation receives retrieved passages and aggregated SQL evidence. Provider terms and quotas apply. The index itself remains local.

## Example questions

- How were duplicates identified? Is Order ID plus SKU enough?
- Why were missing amounts kept null?
- What does `amount_minor` mean?
- Explain shipped sales value and whether it means collected revenue.
- Show Kurta sales in Maharashtra and explain how sales are defined.

Document answers contain references such as `[D1]`. The **Project source passages** panel shows the exact corresponding excerpt, filename and source lines. Labels are local to that question. Sources shown for an extractive fallback are retrieved passages, not a claim that an unverified generated answer used them.

An unknown citation ID, absent citations in a document-only answer, or unsupported numerical prose triggers a safe fallback. Financial figures and percentages must pass the existing SQL numeric check. Literal nonfinancial document numbers, such as column types, may be quoted from cited passages. Citation validation verifies IDs and the numerical check verifies digit values; neither guarantees semantic entailment or catches every misleading interpretation. Users can inspect the actual evidence.

Unsupported return policies, profit, retention, causal conclusions and forecasts must not be inferred from document similarity. A retrieved passage can be related without answering the question.

Cancellation/return questions receive a direct count answer from a companion SQL summary of the entire filtered population. This summary is independent of the displayed status row limit and includes both order-line and distinct-order counts. Returned to Seller and Returning to Seller remain distinct. The app states explicitly that cancellation/return reasons are not recorded, rather than sending users to notes or guessing causes. The status chart uses order-line counts; recorded monetary values remain in the table and do not represent cancellation losses or refunds. Unsupported policy questions keep the explicit missing-policy answer.

## Requests and verification

Each question has at most three generation requests, one embedding search and four SQL analyses, bounded by the remaining session allowance. All attempted generation/embedding requests count in **Session API calls**. A low remaining allowance can produce an extractive or SQL fallback. Index-building requests run separately; the initial build used one batched embedding request for 17 passages. Provider account limits are independent of the browser session counter.

Run regression tests without external provider calls:

```powershell
.\.venv-assistant\Scripts\python.exe -m pytest tests -q
```

Run the bounded live evaluation (up to 24 generation/embedding calls):

```powershell
.\.venv-assistant\Scripts\python.exe -m assistant.evaluate_rag
```

`tests/test_rag.py` covers source provenance, normalized retrieval, changed/tampered index rejection, citations, no-evidence fallback, mixed SQL/document answers and request accounting. `tests/test_assistant_ui.py` checks the rendered source panel. Live checks are written incrementally to `reports/rag_live_evaluation.json`; curated examples are not a general accuracy benchmark.

The initial full regression run passed 87 tests. After the live routing fixes, 30 affected integration checks passed; final citation handling passed 19 grounding checks and the source-panel check passed separately. These overlapping counts must not be added. Five retrieval examples and four final answer examples passed live checks, including mixed Kurta/Maharashtra SQL and documentation, duplicate methodology, the sales definition and an unsupported policy request. The actual website was checked with a document question and a mixed question. See `reports/rag_completion.json` and `reports/screenshots_assistant/rag_*.png`.
