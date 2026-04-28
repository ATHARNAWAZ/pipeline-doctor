# Phase 2 Progress — RAG Pipeline & Claude API Integration

**Status: COMPLETE**
**Completed: 2026-03-18**

---

## Deliverables

### 1. `backend/app/services/rag_engine.py`

Production RAG engine using LlamaIndex + pgvector.

Key implementation details:
- **Lazy initialization**: `RAGEngine.__init__` does nothing expensive. `await engine.initialize(db_url)` is called once on first use, not at import time. This keeps tests fast and avoids crashing when pgvector is unavailable.
- **Dual embedding strategy**: Uses `OpenAIEmbedding` (ada-002, 1536-dim) when `OPENAI_API_KEY` is set; falls back to `HuggingFaceEmbedding` with `BAAI/bge-small-en-v1.5` (384-dim) otherwise. The HuggingFace model runs fully on CPU with no external API calls.
- **Keyword fallback**: If pgvector is unreachable, `_fallback_keyword_query()` provides name/tag/description matching. The tool degrades gracefully rather than crashing.
- **One document per model**: Each dbt model becomes a single LlamaIndex `Document` containing name, SQL, columns, tags, and upstream dependencies. SQL is prepended to maximize signal density in the embedding.
- **Structured context string**: `_build_context_string()` produces a markdown document ordered with failing models first, including error messages, truncated SQL (80-line cap), and 2-hop lineage context. This is what Claude reads.
- **pgvector auto-create**: `CREATE EXTENSION IF NOT EXISTS vector` is idempotent — runs on every startup safely.

Dataclasses:
- `IndexingResult`: `models_indexed`, `sources_indexed`, `total_chunks`, `embedding_model`
- `RetrievedContext`: `relevant_nodes`, `context_string`, `retrieval_score`

### 2. `backend/app/services/claude_service.py`

Claude API integration with production-grade error handling.

Key implementation details:
- **System prompt** (`SYSTEM_PROMPT`): Tuned specifically for dbt debugging. Rules are ordered by how often violating them produces bad output. The key constraint is "always use specific model names" — without it Claude produces generic boilerplate.
- **`explain_failure()`**: Non-streaming. Prompt structure: error first, then lineage, then SQL context. Error-first ordering causes Claude to anchor on the actual problem rather than the surrounding context.
- **`stream_response()`**: Genuinely async streaming via `client.messages.stream()` + `async for text_chunk in stream.text_stream`. Yields raw chunks as they arrive. Not buffered.
- **`generate_slack_alert()`**: Asks Claude for a 2-3 sentence root-cause summary, wraps it in Slack Block Kit format. Caps at 5 models in the prompt to stay within token budget.
- **Error handling**: Distinct handling for `RateLimitError` (return graceful message), `AuthenticationError` (raise RuntimeError — bad API key is fatal), `BadRequestError` (content policy — return safe message), all others (log + re-raise).

Dataclasses:
- `FailingModelSummary`: `model_name`, `error_message`, `upstream_models`, `downstream_affected`
- `SlackMessage`: `blocks` (Block Kit list), `text` (fallback string)

### 3. `backend/app/routers/query.py`

FastAPI routes for the Claude/RAG layer. Registered at `/query` prefix in `main.py`.

Endpoints:
- **`POST /query/ask`**: Accepts `{"question": str, "analysis_id": str | None}`. Resolves analysis from `_analysis_store` (shared with `analyze.py`), runs RAG retrieval, collects the streaming response into a single string, returns `{"answer": str, "relevant_models": list[str], "confidence": float}`.
- **`WebSocket /query/stream`**: Client sends `{"question": str, "analysis_id": str | None}`. Server streams `{"chunk": str}` messages then `{"done": true}`. Handles `WebSocketDisconnect` at every send point — mid-stream disconnects are normal and do not crash the handler.

Service singletons (`_rag_engine`, `_claude_service`) are initialized lazily on first request via dependency functions. Failed RAG initialization falls back to keyword search without raising.

### 4. `backend/app/services/slack_notifier.py`

Standalone Slack notification service using `httpx` (no Slack SDK dependency).

Key implementation details:
- **Never raises**: All methods return `bool`. Every exception is caught and logged. A broken Slack webhook cannot kill the pipeline or Lambda handler.
- **`send_failure_alert(alert)`**: Accepts any object with `.blocks` and `.text` attributes — duck-typed compatibility with `SlackMessage` without circular import.
- **`send_recovery_notice(recovered_models)`**: Sends a green checkmark message when previously-failing models are now passing. Caps display at 10 model names.
- **10-second timeout**: Conservative timeout to avoid blocking Lambda execution.

### 5. `backend/lambda_handler.py`

Two Lambda handlers for S3 and SNS/EventBridge triggers.

**`analyze_handler(event, context)`** — S3 PutObject trigger:
1. Extracts bucket/key from `event["Records"][0]["s3"]`
2. Downloads `manifest.json` from S3 (and `run_results.json` if present at same prefix)
3. Parses via `ManifestParser`, builds `LineageGraph`
4. For each failing model: calls `ClaudeService.explain_failure()` with direct SQL context (no pgvector in Lambda)
5. Stores timestamped `analysis_{ts}.json` + `latest_analysis.json` pointer back to S3
6. If failures exist and `SLACK_WEBHOOK_URL` is set, sends Slack alert

**`notify_handler(event, context)`** — SNS/EventBridge trigger:
1. Reads `S3_BUCKET_NAME` and `SLACK_WEBHOOK_URL` from environment
2. Finds most recently modified `latest_analysis.json` in bucket
3. If failures exist, generates Slack alert via Claude and sends it

Both handlers use `asyncio.run()` to execute async service code from Lambda's sync entry point.

---

## Architecture Notes

### RAG + Claude Data Flow

```
manifest.json upload (POST /analyze)
    → ManifestParser → ParsedManifest stored in _analysis_store
    → LineageGraph built, stored in _lineage_store

POST /query/ask or WS /query/stream
    → RAGEngine.query() → pgvector similarity search
    → RetrievedContext (relevant node IDs + pre-formatted context string)
    → ClaudeService._build_question_prompt() or _build_failure_prompt()
    → Claude API (streaming)
    → WebSocket chunks or collected string response
```

### Embedding Model Selection Logic

```
OPENAI_API_KEY set?
    Yes → OpenAIEmbedding (ada-002, 1536-dim, ~$0.0001/1K tokens)
    No  → HuggingFaceEmbedding (BAAI/bge-small-en-v1.5, 384-dim, free, CPU)
```

### Context Window Budget

The `_build_context_string()` method is designed to stay within Claude's context window:
- Max 5 models per RAG retrieval
- SQL truncated to 80 lines per model
- Columns capped at 20 per model
- Upstream/downstream capped at 5 nodes per direction

Estimated context size per query: 2,000–6,000 tokens, well within `claude-sonnet-4-6`'s window.

---

## Files Modified

- `backend/app/main.py` — added `query` router import and `app.include_router(query.router, ...)`

## Files Created

- `backend/app/services/rag_engine.py`
- `backend/app/services/claude_service.py`
- `backend/app/services/slack_notifier.py`
- `backend/app/routers/query.py`
- `backend/lambda_handler.py`
