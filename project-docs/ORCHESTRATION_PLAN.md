# Pipeline Doctor — Complete Orchestration Plan
**Version**: 1.0
**Date**: 2026-03-18
**Orchestrator**: AgentsOrchestrator
**Status**: ACTIVE — This document drives the full build pipeline

---

## Overview

Pipeline Doctor is a production-grade, open source AI-powered dbt pipeline debugger. Data engineers upload their dbt manifest.json and run_results.json, and the tool answers "why did my orders model fail?" using actual pipeline context via RAG + Claude.

This document is the authoritative build reference. Every agent in the pipeline must read this before executing their phase. No phase begins until its quality gate is cleared.

---

## Project Coordinates

- **Root**: `C:/python_development/MY_PORTFOLIO_PROJECTS/pipeline-doctor/`
- **Unix path**: `/c/python_development/MY_PORTFOLIO_PROJECTS/pipeline-doctor/`
- **Platform**: Windows 11, bash shell, Unix path syntax throughout
- **Python**: 3.11+
- **Node**: 18+
- **Terraform**: >= 1.5

---

## Build Phases

```
Phase 0: Foundation & Sample Data       [Orchestrator + PM]
Phase 1: Backend Core                   [Backend Architect]
Phase 2: RAG Pipeline                   [AI Engineer]
Phase 3: FastAPI Layer                  [Backend Architect]
Phase 4: React Frontend                 [Frontend Developer]
Phase 5: AWS Infrastructure             [DevOps Automator]
Phase 6: CI/CD Pipeline                 [DevOps Automator]
Phase 7: Integration + Final QA         [testing-reality-checker]
```

Phases 1 and 2 can execute in parallel once Phase 0 is complete.
Phases 3 depends on Phases 1 and 2.
Phase 4 can start when Phase 3 API contracts are published (not necessarily fully implemented).
Phase 5 and 6 can run in parallel with Phase 4.
Phase 7 only starts when all prior phases pass QA.

---

## Phase 0: Foundation and Sample Data

**Assigned to**: project-manager-senior
**Output directory**: `/c/python_development/MY_PORTFOLIO_PROJECTS/pipeline-doctor/`

### Deliverables

#### 0.1 — Full directory scaffold
Create every directory and placeholder file as listed in the project structure. Files should exist but may be empty stubs. The exact structure:

```
pipeline-doctor/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              (stub)
│   │   ├── config.py            (stub)
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── analysis.py      (stub)
│   │   │   ├── lineage.py       (stub)
│   │   │   └── chat.py          (stub)
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── manifest_parser.py   (stub)
│   │   │   ├── rag_engine.py        (stub)
│   │   │   ├── claude_service.py    (stub)
│   │   │   └── lineage_graph.py     (stub)
│   │   └── models/
│   │       ├── __init__.py
│   │       └── schemas.py       (stub)
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py          (stub)
│   │   ├── test_manifest_parser.py  (stub)
│   │   ├── test_rag_engine.py       (stub)
│   │   └── test_api.py              (stub)
│   └── requirements.txt         (stub)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DAGViewer/
│   │   │   │   ├── DAGViewer.tsx    (stub)
│   │   │   │   ├── ModelNode.tsx    (stub)
│   │   │   │   └── index.ts         (stub)
│   │   │   ├── ChatPanel/
│   │   │   │   ├── ChatPanel.tsx    (stub)
│   │   │   │   ├── MessageBubble.tsx (stub)
│   │   │   │   └── index.ts         (stub)
│   │   │   └── ModelDetail/
│   │   │       ├── ModelDetail.tsx  (stub)
│   │   │       └── index.ts         (stub)
│   │   ├── stores/
│   │   │   ├── pipelineStore.ts     (stub)
│   │   │   └── chatStore.ts         (stub)
│   │   ├── hooks/
│   │   │   ├── usePipeline.ts       (stub)
│   │   │   └── useWebSocket.ts      (stub)
│   │   ├── types/
│   │   │   └── index.ts             (stub)
│   │   ├── App.tsx                  (stub)
│   │   └── main.tsx                 (stub)
│   ├── package.json                 (real — see spec below)
│   ├── tsconfig.json                (real)
│   ├── tailwind.config.js           (real — dark theme config)
│   └── vite.config.ts               (real)
├── infra/
│   ├── main.tf                  (stub)
│   ├── lambda.tf                (stub)
│   ├── s3.tf                    (stub)
│   ├── eventbridge.tf           (stub)
│   ├── sns.tf                   (stub)
│   ├── cloudwatch.tf            (stub)
│   └── variables.tf             (stub)
├── .github/
│   └── workflows/
│       ├── test.yml             (stub)
│       └── deploy.yml           (stub)
├── sample_data/
│   └── sample_manifest.json     (REAL — see spec below)
├── docker-compose.yml           (real — see spec below)
├── .env.example                 (real)
├── .gitignore                   (real)
└── README.md                    (stub — final version in Phase 7)
```

#### 0.2 — sample_manifest.json (REAL, not a stub)

This file is the primary test fixture used by every other phase. It must be realistic and internally consistent — not toy data.

The fintech pipeline modelled:
- 5 source tables: `raw_transactions`, `raw_customers`, `raw_products`, `raw_events`, `raw_sessions`
- 5 staging models: `stg_transactions`, `stg_customers`, `stg_products`, `stg_events`, `stg_sessions`
- 3 intermediate models: `int_customer_orders`, `int_product_revenue`, `int_session_funnel`
- 4 mart models: `mart_daily_revenue`, `mart_customer_lifetime_value`, `mart_product_performance`, `mart_conversion_funnel`
- 2 exposures: `revenue_dashboard`, `customer_health_dashboard`

The manifest must follow the dbt manifest v10 schema with these fields populated per node:
- `unique_id`, `name`, `resource_type`, `schema`, `database`, `fqn`
- `raw_code` (realistic SQL, not placeholder)
- `description` (plain English, sounds like a real data engineer wrote it)
- `depends_on.nodes` (correct lineage)
- `columns` (with name, description, data_type)
- `tags`, `config.materialized`, `config.schema`
- `compiled_code` (same as raw_code for simplicity)

Also create `sample_data/sample_run_results.json` following dbt run_results v4 schema. Introduce 2 deliberate failures:
- `mart_daily_revenue` fails with a column reference error: `"column "transaction_date" does not exist"`
- `stg_transactions` has a test failure: `"not_null_stg_transactions_transaction_id"` — null values found in 47 rows

These failures must be realistic — include `execution_time`, `status: "error"`, `adapter_response`, `message` fields.

#### 0.3 — docker-compose.yml (REAL)

```yaml
# This runs the full stack locally. postgres with pgvector is the only dependency
# that requires careful setup — the vector extension must be installed before the
# app tries to create tables.
version: '3.9'
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: pipeline_doctor
      POSTGRES_USER: pipeline_doctor
      POSTGRES_PASSWORD: pipeline_doctor_local
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pipeline_doctor"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://pipeline_doctor:pipeline_doctor_local@postgres:5432/pipeline_doctor
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - S3_BUCKET_NAME=${S3_BUCKET_NAME}
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000
      - VITE_WS_URL=ws://localhost:8000
    volumes:
      - ./frontend/src:/app/src
    depends_on:
      - backend

volumes:
  pgdata:
```

#### 0.4 — .env.example (REAL)

```bash
# Claude / Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Database (local dev — matches docker-compose)
DATABASE_URL=postgresql://pipeline_doctor:pipeline_doctor_local@localhost:5432/pipeline_doctor

# AWS (only needed for cloud features + infra)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=pipeline-doctor-manifests-dev

# Slack (optional — enables failure alerts)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# App config
LOG_LEVEL=INFO
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000
```

#### 0.5 — .gitignore (REAL)

Standard Python + Node + Terraform .gitignore. Must include: `.env`, `__pycache__`, `node_modules`, `.terraform`, `*.tfstate`, `*.tfstate.backup`, `.terraform.lock.hcl`, `dist/`, `build/`, `*.egg-info/`, `.pytest_cache/`, `.coverage`, `htmlcov/`.

#### 0.6 — frontend/package.json (REAL)

Exact dependencies required:
```json
{
  "name": "pipeline-doctor-ui",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint src --ext ts,tsx",
    "test": "vitest"
  },
  "dependencies": {
    "@anthropic-ai/sdk": "^0.20.0",
    "@xyflow/react": "^12.0.0",
    "axios": "^1.6.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-markdown": "^9.0.0",
    "react-syntax-highlighter": "^15.5.0",
    "rehype-highlight": "^7.0.0",
    "zustand": "^4.5.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@types/react-syntax-highlighter": "^15.5.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^8.57.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "vitest": "^1.5.0"
  }
}
```

#### 0.7 — backend/requirements.txt (REAL)

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
anthropic==0.25.0
llama-index==0.10.40
llama-index-vector-stores-postgres==0.1.4
llama-index-embeddings-openai==0.1.9
psycopg2-binary==2.9.9
sqlalchemy==2.0.30
pgvector==0.2.5
networkx==3.3
boto3==1.34.0
python-multipart==0.0.9
python-dotenv==1.0.1
pydantic==2.7.0
pydantic-settings==2.2.1
pytest==8.2.0
pytest-asyncio==0.23.0
pytest-cov==5.0.0
httpx==0.27.0
```

### Quality Gate 0

Before Phase 1 begins, verify:
- [ ] All directories exist at correct paths
- [ ] sample_manifest.json is valid JSON and passes `python -m json.tool`
- [ ] sample_run_results.json is valid JSON with exactly 2 failures
- [ ] docker-compose.yml is valid YAML
- [ ] .env.example contains all required variables
- [ ] requirements.txt and package.json exist with correct content
- [ ] No actual secrets in any committed file

---

## Phase 1: Backend Core Services

**Assigned to**: Backend Architect
**Depends on**: Phase 0 complete
**Output directory**: `/c/python_development/MY_PORTFOLIO_PROJECTS/pipeline-doctor/backend/`

### Deliverables

#### 1.1 — backend/app/config.py

Use `pydantic-settings` with a `Settings` class. All values from environment, never hardcoded. Include:
- `anthropic_api_key: str`
- `database_url: str`
- `aws_access_key_id: Optional[str]`
- `aws_secret_access_key: Optional[str]`
- `aws_region: str = "us-east-1"`
- `s3_bucket_name: Optional[str]`
- `slack_webhook_url: Optional[str]`
- `log_level: str = "INFO"`
- `environment: str = "development"`
- `cors_origins: list[str]`

Use `model_config = SettingsConfigDict(env_file=".env")`. Expose a cached `get_settings()` function using `@lru_cache`.

#### 1.2 — backend/app/services/manifest_parser.py

This is the most important backend service. It must handle real dbt manifests which can be 50MB+ on large projects.

Requirements:
- `ManifestParser` class, not a collection of loose functions
- `parse(manifest_path: Path, run_results_path: Path) -> ParsedPipeline` — primary entry point
- Parse node types: `model`, `test`, `source`, `exposure` — ignore seeds/snapshots for now
- For each model extract: unique_id, name, schema, database, raw_sql, compiled_sql, description, depends_on, columns (name + description + type), materialization, tags, fqn
- For each test extract: name, model_name, column_name, test_type, status (from run_results)
- Merge run_results status into node data — a model is "failing" if any of its tests fail OR if the model itself errored
- Build a `FailureSummary` per failing model: error message, failing tests, execution time
- Return type `ParsedPipeline` is a dataclass/Pydantic model, not a raw dict

Important implementation notes:
- Use `ijson` for streaming parse if manifest > 10MB (add ijson to requirements.txt)
- The `nodes` key in manifest contains models, tests, sources mixed together — filter by `resource_type`
- Source nodes live under `sources` key, not `nodes`
- Exposure nodes live under `exposures` key
- `depends_on.nodes` gives full unique_ids like `model.project.stg_transactions` — strip the prefix to get the model name

Error handling: if a file doesn't exist, raise `ManifestNotFoundError` (custom exception) with the path in the message. If JSON is malformed, raise `ManifestParseError` with line number if available.

#### 1.3 — backend/app/services/lineage_graph.py

Build and query the DAG using NetworkX.

Requirements:
- `LineageGraph` class
- `build(parsed_pipeline: ParsedPipeline) -> None` — constructs the DiGraph
- `get_upstream(model_name: str, depth: int = None) -> list[str]` — all ancestors, optional depth limit
- `get_downstream(model_name: str, depth: int = None) -> list[str]` — all descendants
- `get_critical_path(failing_model: str) -> list[str]` — shortest path from any source to failing model
- `get_impact_analysis(model_name: str) -> ImpactAnalysis` — what downstream models are affected if this model fails
- `to_cytoscape_format() -> dict` — export as node/edge dict for frontend rendering (React Flow compatible)
- `find_root_cause_candidates(failing_model: str) -> list[str]` — upstream models that also have failures, ordered by proximity

The `to_cytoscape_format` / React Flow export format:
```python
{
    "nodes": [
        {
            "id": "stg_transactions",
            "data": {
                "label": "stg_transactions",
                "status": "passing",  # "passing" | "failing" | "warning" | "unknown"
                "materialization": "view",
                "schema": "staging",
                "description": "..."
            },
            "position": {"x": 0, "y": 0}  # layout computed by dagre or similar
        }
    ],
    "edges": [
        {
            "id": "stg_transactions->int_customer_orders",
            "source": "stg_transactions",
            "target": "int_customer_orders",
            "type": "smoothstep"
        }
    ]
}
```

Node positions: compute a simple layered layout. Sources at x=0, staging at x=200, intermediate at x=400, marts at x=600. Y position = index * 120 within layer.

#### 1.4 — backend/app/models/schemas.py

Pydantic v2 schemas for API request/response contracts. These are the contracts the frontend depends on — they must be complete and stable.

Schemas needed:
```python
# Request
class AnalyzeRequest(BaseModel): ...     # manifest upload metadata
class AskRequest(BaseModel):
    question: str
    model_context: Optional[str] = None  # if user clicked a specific model

# Response
class ModelNode(BaseModel):
    unique_id: str
    name: str
    schema_name: str
    database: str
    description: str
    materialization: str
    status: Literal["passing", "failing", "warning", "unknown"]
    tags: list[str]
    sql: str
    columns: list[ColumnSchema]
    upstream: list[str]
    downstream: list[str]

class ColumnSchema(BaseModel):
    name: str
    description: str
    data_type: str

class FailureDetail(BaseModel):
    model_name: str
    error_message: str
    failing_tests: list[str]
    execution_time_seconds: float
    root_cause_candidates: list[str]
    ai_explanation: Optional[str] = None

class PipelineStatus(BaseModel):
    total_models: int
    passing: int
    failing: int
    warnings: int
    last_run_at: Optional[datetime]
    project_name: str

class LineageResponse(BaseModel):
    model_name: str
    upstream: list[ModelNode]
    downstream: list[ModelNode]
    critical_path: list[str]

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime
    model_context: Optional[str] = None
```

#### 1.5 — backend/tests/test_manifest_parser.py (REAL TESTS)

Write real pytest tests against the sample data:
- `test_parse_returns_correct_model_count` — expects exactly 17 models (5 staging + 3 intermediate + 4 marts + 5 sources)
- `test_failing_models_detected` — expects `mart_daily_revenue` and `stg_transactions` to be in failures
- `test_lineage_dependencies_correct` — `mart_daily_revenue` depends on `int_customer_orders`
- `test_column_extraction` — `stg_transactions` has a `transaction_id` column
- `test_malformed_manifest_raises` — parsing garbage JSON raises `ManifestParseError`
- `test_missing_file_raises` — missing file raises `ManifestNotFoundError`

Use the sample_manifest.json at `sample_data/` as the fixture. The `conftest.py` should define a `parsed_pipeline` fixture that calls `ManifestParser().parse(...)` once and reuses it.

Coverage target: these 6 tests must achieve >80% coverage of manifest_parser.py.

### Quality Gate 1

Before Phase 2 begins, verify:
- [ ] `python -m pytest backend/tests/test_manifest_parser.py -v` — all 6 tests pass
- [ ] `python -m pytest --cov=backend/app/services/manifest_parser.py --cov-report=term` — >80% coverage
- [ ] `ManifestParser().parse(sample_data/sample_manifest.json, sample_data/sample_run_results.json)` completes without exception
- [ ] `LineageGraph` correctly identifies `mart_daily_revenue` as downstream of `stg_transactions`
- [ ] All Pydantic schemas import without error
- [ ] No hardcoded credentials in any file

---

## Phase 2: RAG Pipeline and Claude Integration

**Assigned to**: engineering-ai-engineer
**Depends on**: Phase 0 complete (can run in parallel with Phase 1)
**Output directory**: `/c/python_development/MY_PORTFOLIO_PROJECTS/pipeline-doctor/backend/app/services/`

### Deliverables

#### 2.1 — backend/app/services/rag_engine.py

The RAG engine is the intelligence layer. It takes dbt context and makes it queryable.

Requirements:
- `RAGEngine` class with async methods throughout
- `async def ingest(parsed_pipeline: ParsedPipeline) -> IngestResult` — builds/updates the vector store
- `async def query(question: str, model_context: Optional[str] = None) -> RetrievedContext` — semantic search
- `async def get_model_context(model_name: str) -> str` — retrieve everything about a specific model

Vector store: use `pgvector` via `llama-index-vector-stores-postgres`. Connection string from `settings.database_url`.

Chunking strategy (this matters for retrieval quality):
- One chunk per model: `[model_name] description + column descriptions` (semantic metadata)
- One chunk per model: raw SQL (for technical queries about transformations)
- One chunk per test failure: `[FAILURE] model_name: error_message` (for debugging queries)
- Chunk overlap: 50 tokens. Max chunk size: 512 tokens.

Embedding model: use `llama-index`'s default embedding (text-embedding-ada-002 via OpenAI) OR if `OPENAI_API_KEY` not set, fall back to a local HuggingFace model (`BAAI/bge-small-en-v1.5` via `llama-index-embeddings-huggingface`). Log which embedding provider is being used at startup.

Add `llama-index-embeddings-huggingface` and `openai` to requirements.txt.

On `ingest()`: delete existing vectors for the same project before re-inserting (re-ingestion must be idempotent).

`RetrievedContext` dataclass:
```python
@dataclass
class RetrievedContext:
    relevant_chunks: list[str]
    model_names_mentioned: list[str]  # extract from retrieved chunks
    failure_context: list[str]       # chunks specifically about failures
    confidence_score: float          # average similarity score of top-k results
```

#### 2.2 — backend/app/services/claude_service.py

The Claude integration. This is the user-facing intelligence.

Requirements:
- `ClaudeService` class
- `async def explain_failure(failure: FailureDetail, context: RetrievedContext) -> str` — non-streaming, used by Slack alerts
- `async def stream_answer(question: str, context: RetrievedContext, history: list[ChatMessage]) -> AsyncIterator[str]` — streaming, used by WebSocket
- `async def generate_slack_alert(failure: FailureDetail, context: RetrievedContext) -> SlackAlert` — formatted Slack message

Model: `claude-sonnet-4-6` (exact model ID, do not change)

System prompt for all calls:
```
You are a senior data engineer helping debug dbt pipeline failures.
You have access to the full dbt project context including model SQL,
descriptions, dependencies, and test results.

Be specific: mention actual model names, column names, and table names
from the context. Do not give generic advice. If you see a column reference
error in mart_daily_revenue, say exactly that.

When explaining failures, follow this structure:
1. What failed and what the exact error is
2. Why it likely failed (root cause, with model names)
3. What to check first (specific, actionable steps)
4. Whether upstream models are also affected

If you don't have enough context to answer confidently, say so.
```

Streaming implementation: use `anthropic.AsyncAnthropic`, stream `text_deltas` from `messages.stream()` context manager. Yield each delta immediately — do not buffer.

Token budget: set `max_tokens=2048` for explain_failure, `max_tokens=4096` for stream_answer.

`SlackAlert` dataclass:
```python
@dataclass
class SlackAlert:
    text: str           # plain text fallback
    blocks: list[dict]  # Slack Block Kit format
    model_name: str
    severity: Literal["error", "warning"]
```

The Slack Block Kit message should include:
- Header: `:red_circle: Pipeline Failure: {model_name}`
- Section: error message in a code block
- Section: AI explanation (first 300 chars + "See full analysis in Pipeline Doctor")
- Context: run timestamp

#### 2.3 — backend/tests/test_rag_engine.py (REAL TESTS)

Tests must use pytest-asyncio. Mock the pgvector connection for unit tests (don't require a live DB).

Tests:
- `test_ingest_creates_correct_chunk_count` — 17 models × 2 chunk types + 2 failure chunks = 36 chunks
- `test_query_returns_relevant_context` — mock the vector store, assert `RetrievedContext` fields populated
- `test_idempotent_ingest` — calling ingest twice should not double the chunk count
- `test_claude_service_streams` — mock anthropic client, assert stream_answer yields strings

### Quality Gate 2

Before Phase 3 begins, verify:
- [ ] `test_rag_engine.py` and relevant tests pass
- [ ] `ClaudeService` imports without error (mocked)
- [ ] `RAGEngine.ingest()` runs without error against sample_manifest.json (requires live postgres+pgvector OR mock)
- [ ] System prompt is exactly as specified — do not paraphrase
- [ ] Streaming is truly async — no `asyncio.run()` blocking calls inside the service
- [ ] `claude-sonnet-4-6` is the model ID, not claude-3 or anything else

---

## Phase 3: FastAPI Application Layer

**Assigned to**: Backend Architect
**Depends on**: Phases 1 and 2 complete
**Output directory**: `/c/python_development/MY_PORTFOLIO_PROJECTS/pipeline-doctor/backend/app/`

### Deliverables

#### 3.1 — backend/app/main.py

The FastAPI application entry point.

Requirements:
- Lifespan context manager for startup/shutdown (not deprecated `@app.on_event`)
- On startup: initialize database connection, create pgvector extension if not exists, create tables
- CORS middleware: origins from `settings.cors_origins`
- Include all routers with `/api/v1` prefix
- Mount static files if `ENVIRONMENT=production`
- Root health check at `GET /health` returning `{"status": "ok", "version": "0.1.0"}`
- Structured logging with `structlog` or standard `logging` in JSON format when `ENVIRONMENT=production`
- Global exception handler: catch unhandled exceptions, log them, return 500 with correlation ID

Add `structlog` to requirements.txt.

#### 3.2 — backend/app/routers/analysis.py

```python
POST /api/v1/analyze
```
- Accepts `multipart/form-data` with two file fields: `manifest` and `run_results`
- Validate both files are valid JSON before proceeding
- Run `ManifestParser.parse()`, then `LineageGraph.build()`, then `RAGEngine.ingest()`
- Store the `ParsedPipeline` in application state (in-memory is fine for v0.1)
- Return `PipelineStatus` schema
- Include `background_tasks` to run ingestion async — return immediately with job ID

```python
GET /api/v1/failures
```
- Return list of `FailureDetail` objects for all currently failing models
- If no pipeline has been analyzed yet, return 404 with message "No pipeline loaded. POST to /api/v1/analyze first."

```python
GET /api/v1/status
```
- Return current `PipelineStatus`

#### 3.3 — backend/app/routers/lineage.py

```python
GET /api/v1/lineage/{model_name}
```
- Return `LineageResponse` for the given model
- If model not found, return 404

```python
GET /api/v1/graph
```
- Return the full graph in React Flow format (calls `lineage_graph.to_cytoscape_format()`)
- This is called on page load to render the DAG

#### 3.4 — backend/app/routers/chat.py

```python
POST /api/v1/ask
```
- Accepts `AskRequest`
- Non-streaming. Call `RAGEngine.query()` then `ClaudeService.explain_failure()` or a general answer
- Return `{"answer": "...", "model_context": ["model_names_mentioned"]}`

```python
WebSocket /api/v1/stream
```
- Client sends JSON: `{"question": "...", "model_context": "optional_model_name"}`
- Server calls `RAGEngine.query()` then `ClaudeService.stream_answer()`
- Streams each text delta as a JSON frame: `{"type": "delta", "content": "..."}`
- On completion: `{"type": "done"}`
- On error: `{"type": "error", "message": "..."}`

#### 3.5 — backend/tests/test_api.py (REAL TESTS)

Use `httpx.AsyncClient` with `ASGITransport`. Mock all services (no live DB or API calls).

Tests:
- `test_health_check` — GET /health returns 200
- `test_analyze_endpoint_accepts_files` — POST /analyze with sample files returns 200 with PipelineStatus
- `test_failures_before_analyze_returns_404` — GET /failures with no pipeline loaded returns 404
- `test_lineage_endpoint` — GET /lineage/stg_transactions returns correct upstream/downstream
- `test_graph_endpoint` — GET /graph returns nodes and edges

### Quality Gate 3

Before Phase 4 begins, verify:
- [ ] `pytest backend/tests/ -v` — all tests pass
- [ ] `uvicorn app.main:app --reload` starts without error
- [ ] `curl http://localhost:8000/health` returns `{"status": "ok"}`
- [ ] `curl -F "manifest=@sample_data/sample_manifest.json" -F "run_results=@sample_data/sample_run_results.json" http://localhost:8000/api/v1/analyze` — returns PipelineStatus JSON
- [ ] `curl http://localhost:8000/api/v1/graph` — returns nodes and edges matching sample data
- [ ] `curl http://localhost:8000/api/v1/failures` — returns 2 failures matching the deliberately introduced ones
- [ ] OpenAPI docs at `/docs` show all 6 endpoints

---

## Phase 4: React Frontend

**Assigned to**: Frontend Developer
**Depends on**: Phase 3 API contracts published (schemas.py complete, endpoints defined)
**Output directory**: `/c/python_development/MY_PORTFOLIO_PROJECTS/pipeline-doctor/frontend/`

### Design System — Critical

This is a tool for engineers. It must look like a terminal, not a dashboard.

- Background: `#0d1117` (GitHub dark, not pure black)
- Surface: `#161b22`
- Border: `#30363d`
- Text primary: `#e6edf3`
- Text muted: `#8b949e`
- Accent: `#58a6ff` (GitHub blue)
- Failure red: `#f85149`
- Success green: `#3fb950`
- Warning yellow: `#d29922`
- Font: `JetBrains Mono` for code, `Inter` for UI text
- No rounded corners on cards (use `rounded-sm` maximum)
- Borders everywhere, not shadows
- No gradients

### Deliverables

#### 4.1 — frontend/src/types/index.ts

TypeScript types matching backend schemas exactly:
```typescript
export interface ModelNode {
  unique_id: string;
  name: string;
  schema_name: string;
  database: string;
  description: string;
  materialization: string;
  status: 'passing' | 'failing' | 'warning' | 'unknown';
  tags: string[];
  sql: string;
  columns: ColumnSchema[];
  upstream: string[];
  downstream: string[];
}

export interface ColumnSchema {
  name: string;
  description: string;
  data_type: string;
}

export interface FailureDetail {
  model_name: string;
  error_message: string;
  failing_tests: string[];
  execution_time_seconds: number;
  root_cause_candidates: string[];
  ai_explanation?: string;
}

export interface PipelineStatus {
  total_models: number;
  passing: number;
  failing: number;
  warnings: number;
  last_run_at?: string;
  project_name: string;
}

export interface GraphData {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  model_context?: string;
}
```

#### 4.2 — frontend/src/stores/pipelineStore.ts

Zustand store for pipeline state:
```typescript
interface PipelineStore {
  status: PipelineStatus | null;
  graphData: GraphData | null;
  failures: FailureDetail[];
  selectedModel: ModelNode | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  uploadManifest: (manifest: File, runResults: File) => Promise<void>;
  fetchGraph: () => Promise<void>;
  fetchFailures: () => Promise<void>;
  selectModel: (modelName: string) => Promise<void>;
  clearError: () => void;
}
```

#### 4.3 — frontend/src/stores/chatStore.ts

Zustand store for chat state:
```typescript
interface ChatStore {
  messages: ChatMessage[];
  isStreaming: boolean;
  activeModelContext: string | null;

  // Actions
  sendMessage: (question: string) => Promise<void>;
  setModelContext: (modelName: string | null) => void;
  clearHistory: () => void;
}
```

WebSocket management: the `sendMessage` action opens a WebSocket to `WS_URL/api/v1/stream`, sends the question, appends deltas to the last assistant message as they arrive, sets `isStreaming = false` on `done`. Reconnect on disconnect (max 3 attempts).

#### 4.4 — frontend/src/components/DAGViewer/DAGViewer.tsx

The DAG visualisation component.

Requirements:
- Use `@xyflow/react` (React Flow v12)
- Custom node component `ModelNode.tsx`:
  - Background: surface color (`#161b22`)
  - Border: color-coded by status (red/green/yellow/grey)
  - Show model name, materialization badge, status indicator dot
  - On click: call `pipelineStore.selectModel(name)` — this populates the ModelDetail panel
- Edge style: `smoothstep` with muted color
- Enable `fitView` on initial load
- Minimap: dark themed, visible in bottom-right
- Controls: zoom in/out/reset in bottom-left
- Background: dot pattern, very subtle (`#21262d`)
- Failing nodes should pulse (CSS animation) — use a subtle border glow, not a jarring animation
- Do not show node handles — this is a read-only diagram

ModelNode.tsx status color map:
```typescript
const STATUS_COLORS = {
  passing: '#3fb950',
  failing: '#f85149',
  warning: '#d29922',
  unknown: '#8b949e',
} as const;
```

#### 4.5 — frontend/src/components/ChatPanel/ChatPanel.tsx

The chat interface. This is the primary user interaction.

Requirements:
- Fixed height panel (flex, fills available space)
- Messages list: scrolls independently, newest at bottom
- Each message in `MessageBubble.tsx`:
  - User messages: right-aligned, accent blue background
  - Assistant messages: left-aligned, surface background, full width for code
  - Render markdown with `react-markdown` + `react-syntax-highlighter`
  - Code blocks: use `dracula` theme from `react-syntax-highlighter`
  - Show model name badge if `model_context` is set
- While streaming: show a blinking cursor at end of assistant message
- Input: full-width text input at bottom, send on Enter (Shift+Enter for newline)
- Placeholder text: "Ask about your pipeline... e.g. 'Why did mart_daily_revenue fail?'"
- If `selectedModel` is set in pipelineStore: show a chip "Context: {model_name}" above the input with an X to clear it
- Show spinner while waiting for first stream delta (after send, before first character arrives)

#### 4.6 — frontend/src/components/ModelDetail/ModelDetail.tsx

Side panel shown when a node is clicked in the DAG.

Requirements:
- Shows when `pipelineStore.selectedModel` is not null
- Sections (collapsible):
  1. Status badge + execution time (if failing)
  2. Description (from dbt docs)
  3. Columns table: name | type | description
  4. SQL: syntax-highlighted code block (use `react-syntax-highlighter` with `sql` language)
  5. Dependencies: "Upstream: [model1, model2]" as clickable chips — clicking a chip navigates the DAG to that model
  6. Failing Tests: list with test name + error message
- "Ask Claude about this model" button: sets `model_context` in chatStore to this model name and focuses the chat input

#### 4.7 — frontend/src/App.tsx

Main application layout:
```
┌─────────────────────────────────────────────────────────────────┐
│  PIPELINE DOCTOR                    [Upload manifest] [Status]  │  <- TopBar
├───────────────────────────────────┬─────────────────────────────┤
│                                   │                             │
│         DAG Viewer                │        Chat Panel           │
│     (React Flow graph)            │    (streaming chat UI)      │
│                                   │                             │
│  [Model Detail slides in from     │                             │
│   bottom when node clicked]       │                             │
│                                   │                             │
└───────────────────────────────────┴─────────────────────────────┘
```

- Left panel: 60% width, `DAGViewer` + `ModelDetail` (ModelDetail as overlay panel at bottom of DAG)
- Right panel: 40% width, `ChatPanel`
- Top bar: `PIPELINE DOCTOR` in monospace, upload button, failure count badge
- Upload flow: clicking "Upload manifest" opens a file picker for two files (manifest.json + run_results.json), calls `pipelineStore.uploadManifest()`, shows progress
- On page load: call `pipelineStore.fetchGraph()` and `pipelineStore.fetchFailures()`
- Error toast: when `pipelineStore.error` is set, show a toast in top-right corner with the error message

#### 4.8 — Tailwind configuration

`tailwind.config.js` must define custom colors:
```javascript
module.exports = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#0d1117',
        'bg-surface': '#161b22',
        'border-default': '#30363d',
        'text-primary': '#e6edf3',
        'text-muted': '#8b949e',
        'accent': '#58a6ff',
        'failure': '#f85149',
        'success': '#3fb950',
        'warning': '#d29922',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
}
```

### Quality Gate 4

Before Phase 5 begins, verify:
- [ ] `cd frontend && npm install && npm run build` completes without TypeScript errors
- [ ] `npm run lint` passes with 0 errors
- [ ] App renders at localhost:3000 with dark theme visible
- [ ] DAG renders with sample data (nodes visible, color-coded)
- [ ] Chat input sends a message and receives streaming response (requires backend running)
- [ ] Clicking a node opens ModelDetail panel
- [ ] No light-coloured backgrounds anywhere in the UI — only `#0d1117` / `#161b22`
- [ ] Mobile viewport is not broken (doesn't need to be pretty, just not white-screen)

---

## Phase 5: AWS Infrastructure

**Assigned to**: DevOps Automator
**Depends on**: Phase 0 complete (can run in parallel with Phases 1-4)
**Output directory**: `/c/python_development/MY_PORTFOLIO_PROJECTS/pipeline-doctor/infra/`

### Deliverables

All infrastructure as Terraform. Must be deployable to a real AWS account. Use `us-east-1` as the default region. All resource names use a `pipeline-doctor` prefix and a `var.environment` suffix (e.g., `pipeline-doctor-manifests-dev`).

#### 5.1 — infra/variables.tf

```hcl
variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "slack_webhook_url" {
  description = "Slack incoming webhook URL for failure alerts"
  type        = string
  sensitive   = true
  default     = ""
}

variable "anthropic_api_key" {
  description = "Anthropic API key for Claude"
  type        = string
  sensitive   = true
}
```

#### 5.2 — infra/main.tf

Provider config + Terraform state backend config (S3 backend, commented out by default with instructions to enable for team use).

#### 5.3 — infra/s3.tf

Two S3 buckets:
1. `pipeline-doctor-manifests-{env}` — receives uploaded manifests
   - Versioning enabled
   - Lifecycle rule: delete objects after 90 days
   - Server-side encryption (AES256)
   - Public access blocked
   - Event notification to EventBridge (all PUT events)
2. `pipeline-doctor-results-{env}` — stores AI analysis results
   - Same security settings
   - No event notifications

#### 5.4 — infra/lambda.tf

Two Lambda functions:

1. `pipeline-doctor-analyzer-{env}`:
   - Triggered by EventBridge (S3 PUT on manifests bucket)
   - Runtime: `python3.11`
   - Handler: `lambda_handler.analyze`
   - Memory: 1024 MB (RAG inference needs RAM)
   - Timeout: 300 seconds (manifest parsing + embedding can be slow)
   - Environment variables: `ANTHROPIC_API_KEY`, `DATABASE_URL`, `S3_BUCKET_NAME`, `SNS_TOPIC_ARN`
   - IAM role: read from manifests bucket, write to results bucket, publish to SNS, CloudWatch logs

2. `pipeline-doctor-notifier-{env}`:
   - Triggered by SNS topic
   - Runtime: `python3.11`
   - Handler: `lambda_handler.notify`
   - Memory: 256 MB
   - Timeout: 30 seconds
   - Environment variables: `SLACK_WEBHOOK_URL`
   - IAM role: CloudWatch logs only

Lambda deployment package: use S3-based deployment (not inline zip). The Terraform references a `lambda_package.zip` that the CI/CD pipeline creates. Include a `null_resource` with local-exec to create the zip during `terraform apply` in dev mode.

Also create `/c/python_development/MY_PORTFOLIO_PROJECTS/pipeline-doctor/backend/lambda_handler.py`:
- `analyze(event, context)`: parse S3 event, download manifest from S3, run ManifestParser + RAGEngine, publish failure summary to SNS
- `notify(event, context)`: parse SNS message, call ClaudeService.generate_slack_alert(), POST to Slack webhook

#### 5.5 — infra/eventbridge.tf

EventBridge rule:
- Name: `pipeline-doctor-s3-trigger-{env}`
- Event pattern: S3 Object Created events from the manifests bucket
- Target: Lambda `pipeline-doctor-analyzer-{env}`
- Add necessary Lambda permission for EventBridge to invoke

#### 5.6 — infra/sns.tf

SNS topic: `pipeline-doctor-failures-{env}`
- Subscription: Lambda `pipeline-doctor-notifier-{env}`
- KMS encryption (use AWS managed key)

#### 5.7 — infra/cloudwatch.tf

Log groups with 30-day retention for both Lambda functions.

Alarms:
- Lambda error rate > 5% for 5 minutes → SNS notification
- Lambda duration > 80% of timeout → SNS notification

#### 5.8 — infra/outputs.tf

Outputs: Lambda ARNs, S3 bucket names, SNS topic ARN, all formatted for use in `.env` files.

### Quality Gate 5

Before Phase 6 begins, verify:
- [ ] `terraform init` succeeds in `/infra/`
- [ ] `terraform validate` passes with 0 errors
- [ ] `terraform plan` produces a plan with no errors (may require dummy AWS credentials)
- [ ] All sensitive variables marked `sensitive = true`
- [ ] No AWS credentials hardcoded anywhere in `.tf` files
- [ ] Lambda handler file exists at `backend/lambda_handler.py`
- [ ] Resource naming convention `pipeline-doctor-{resource}-{env}` is consistent

---

## Phase 6: CI/CD Pipeline

**Assigned to**: DevOps Automator
**Depends on**: Phase 0 complete (can run in parallel with Phases 1-5)
**Output directory**: `/c/python_development/MY_PORTFOLIO_PROJECTS/pipeline-doctor/.github/workflows/`

### Deliverables

#### 6.1 — .github/workflows/test.yml

Trigger: push to any branch, PR to main.

Jobs (run in parallel where possible):

`backend-test`:
- Runs on: `ubuntu-latest`
- Services: `pgvector/pgvector:pg16` as `postgres` (health check required)
- Steps:
  1. Checkout
  2. Setup Python 3.11
  3. Cache pip dependencies (key on `requirements.txt` hash)
  4. `pip install -r backend/requirements.txt`
  5. Run pytest with coverage: `pytest backend/tests/ --cov=backend/app --cov-report=xml --cov-fail-under=80`
  6. Upload coverage to Codecov

`frontend-test`:
- Runs on: `ubuntu-latest`
- Steps:
  1. Checkout
  2. Setup Node 18
  3. Cache npm (key on `package-lock.json` hash)
  4. `npm ci` in `frontend/`
  5. `npm run lint`
  6. `npm run build`

`terraform-validate`:
- Runs on: `ubuntu-latest`
- Steps:
  1. Checkout
  2. Setup Terraform 1.5
  3. `terraform init -backend=false` in `infra/`
  4. `terraform validate`

#### 6.2 — .github/workflows/deploy.yml

Trigger: push to `main` branch only, after test workflow passes.

```yaml
on:
  push:
    branches: [main]
  workflow_run:
    workflows: ["Test"]
    types: [completed]
    branches: [main]
```

Jobs:

`deploy-lambda`:
- Runs on: `ubuntu-latest`
- Environment: `production` (requires manual approval in GitHub Environments)
- Steps:
  1. Checkout
  2. Setup Python 3.11
  3. Configure AWS credentials (from `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` secrets)
  4. Build Lambda package: `pip install -r backend/requirements.txt -t lambda_build/ && cp -r backend/app lambda_build/ && cp backend/lambda_handler.py lambda_build/ && cd lambda_build && zip -r ../lambda_package.zip .`
  5. Upload to S3: `aws s3 cp lambda_package.zip s3://${{ secrets.LAMBDA_PACKAGE_BUCKET }}/lambda_package.zip`
  6. Update Lambda functions: `aws lambda update-function-code --function-name pipeline-doctor-analyzer-prod --s3-bucket ... --s3-key lambda_package.zip`
  7. Deploy with Terraform: `terraform apply -auto-approve -var="environment=prod" -var="anthropic_api_key=${{ secrets.ANTHROPIC_API_KEY }}"`

`deploy-frontend`:
- Build React app: `npm run build`
- Sync to S3: `aws s3 sync dist/ s3://${{ secrets.FRONTEND_BUCKET }} --delete`
- Invalidate CloudFront: `aws cloudfront create-invalidation --distribution-id ...`

Required GitHub Secrets (documented in README):
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `ANTHROPIC_API_KEY`
- `LAMBDA_PACKAGE_BUCKET`
- `FRONTEND_BUCKET`
- `CLOUDFRONT_DISTRIBUTION_ID`

### Quality Gate 6

Before Phase 7 begins, verify:
- [ ] Both workflow YAML files are valid (use `actionlint` or equivalent)
- [ ] `test.yml` would run all three jobs
- [ ] `deploy.yml` is gated on test passing and manual approval
- [ ] No secrets hardcoded — all from GitHub Secrets via `${{ secrets.* }}`
- [ ] Cache steps present in both backend and frontend jobs

---

## Phase 7: Integration, Final QA, and README

**Assigned to**: testing-reality-checker
**Depends on**: ALL prior phases complete
**Output directory**: Root of project

### Deliverables

#### 7.1 — Integration Verification

Run the full stack via docker-compose and verify end-to-end flow:

1. `docker-compose up --build` — all services start
2. Upload `sample_data/sample_manifest.json` + `sample_data/sample_run_results.json` via the frontend upload button
3. DAG renders with correct model count (17 nodes visible)
4. `mart_daily_revenue` and `stg_transactions` show as red/failing in the DAG
5. Click `mart_daily_revenue` → ModelDetail shows SQL, error message, failing tests
6. Type "Why did mart_daily_revenue fail?" in chat → Claude responds with specific model name in the answer
7. Streaming works — characters appear one by one, not in a batch

#### 7.2 — README.md (FINAL, REAL)

Replace the stub README with a complete document. This is the portfolio piece — it must be excellent.

Structure:
```markdown
# Pipeline Doctor

> Stop digging through logs. Ask why your dbt models failed.

[Short 3-sentence description of what it does and who it's for]

## The Problem
[2-3 paragraphs about the actual pain. Quote real scenarios: "your mart_daily_revenue
fails at 2am. By morning you've got a Slack thread, a Jira ticket, and three engineers
staring at a 200-line SQL file that touches six upstream models."]

## What Pipeline Doctor Does
[Bullet points — concrete, specific]

## Architecture

[ASCII diagram showing:
manifest.json → ManifestParser → LineageGraph
                                      ↓
                              RAG Engine (pgvector)
                                      ↓
                          Claude (claude-sonnet-4-6)
                                      ↓
                              FastAPI → React UI
                                      ↓
                          AWS Lambda → Slack Alerts]

## Quick Start

### Prerequisites
- Docker and Docker Compose
- An Anthropic API key (get one at console.anthropic.com)

### Run locally
\`\`\`bash
git clone https://github.com/[username]/pipeline-doctor
cd pipeline-doctor
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
docker-compose up
# Open http://localhost:3000
\`\`\`

### Connect your own dbt project
\`\`\`bash
# After a dbt run:
dbt docs generate  # creates manifest.json and run_results.json
# Find them in your dbt project's target/ directory
\`\`\`
Then upload both files via the UI or POST to /api/v1/analyze.

## dbt Manifest Format
Pipeline Doctor expects dbt manifest v10 (dbt >= 1.5).
[Explain what fields are required and where they come from]

## Environment Variables
[Table: variable name | required | description | example]

## API Reference
[Short table of all 6 endpoints]

## Deploying to AWS
[High-level steps to run terraform apply]

## Contributing
[How to run tests, code style expectations]

## License
MIT
```

Do NOT use the phrase "this project demonstrates" or "this showcases my skills". Write it like a tool that ships to users, not a tutorial.

#### 7.3 — Final quality sweep

Fix any issues found during integration:
- Broken imports
- Missing env variable handling
- Type mismatches between frontend types and backend responses
- Any endpoint returning wrong status codes

### Quality Gate 7 — Final Ship Criteria

The project is DONE when ALL of these pass:

**Functionality:**
- [ ] `docker-compose up` starts all services without manual intervention
- [ ] Manifest upload flow works end to end
- [ ] DAG renders with 17 nodes, 2 failing (red)
- [ ] Chat answers "why did mart_daily_revenue fail?" with specific model name in response
- [ ] Streaming is visible (not batched)
- [ ] ModelDetail shows SQL, columns, dependencies
- [ ] `/api/v1/failures` returns 2 failures
- [ ] `/api/v1/graph` returns correct node/edge count

**Code Quality:**
- [ ] `pytest backend/tests/ --cov=backend/app --cov-fail-under=80` passes
- [ ] `npm run build` completes with 0 TypeScript errors
- [ ] `npm run lint` passes with 0 errors
- [ ] No hardcoded API keys, credentials, or localhost URLs
- [ ] No `# TODO` comments left in production code paths

**Infrastructure:**
- [ ] `terraform validate` passes
- [ ] `lambda_handler.py` exists and has both `analyze` and `notify` handlers

**Documentation:**
- [ ] README has real problem statement (no "this demonstrates")
- [ ] `.env.example` documents all variables
- [ ] `sample_data/` has both manifest and run_results with 2 failures

---

## Agent Assignment Summary

| Phase | Agent | Parallel With |
|-------|-------|---------------|
| 0 | project-manager-senior | none |
| 1 | Backend Architect | Phase 2 |
| 2 | engineering-ai-engineer | Phase 1 |
| 3 | Backend Architect | none (needs 1+2) |
| 4 | Frontend Developer | Phases 5, 6 |
| 5 | DevOps Automator | Phases 1, 2, 4, 6 |
| 6 | DevOps Automator | Phases 1, 2, 4, 5 |
| 7 | testing-reality-checker | none (needs all) |

---

## Critical Implementation Rules

These apply to every agent in every phase. Non-negotiable.

1. **All file paths in this document are absolute**. When writing code, import paths and file references must use the correct relative paths within the project, but when running bash commands use absolute paths.

2. **No mock data in production code paths**. Sample data lives only in `sample_data/` and test fixtures. The application must work with real dbt manifests.

3. **Variable naming**: use specific names. `manifest_node_data` not `data`. `failing_model_names` not `result`. `upstream_dependencies` not `deps`.

4. **Comments sound human**:
   - Good: `# manifest.json on big projects can have 2000+ nodes, only grab what we need`
   - Bad: `# This iterates through the nodes dictionary`

5. **Claude model ID**: `claude-sonnet-4-6` everywhere. Not `claude-3-sonnet`, not `claude-sonnet`, not any other variant.

6. **Pydantic v2**: use `model_config = ConfigDict(...)` not class `Config`. Use `model_validator`, not `@validator`.

7. **No `print()` statements in production code**. Use `logging.getLogger(__name__)`.

8. **Error messages in exceptions must include context**:
   - Good: `raise ManifestParseError(f"Failed to parse manifest at {path}: {e}")`
   - Bad: `raise ManifestParseError("Parse failed")`

9. **The frontend uses TypeScript strictly** — `"strict": true` in tsconfig. No `any` types except where genuinely unavoidable, and those must be commented.

10. **Tests must use the sample data files**, not inline mock dicts that could get out of sync with the real schema.

---

## File to Create First

Every agent must create a `project-docs/PHASE_{N}_PROGRESS.md` when starting their phase, and update it when done. Format:

```markdown
# Phase N Progress

**Agent**: [agent name]
**Started**: [timestamp]
**Status**: IN_PROGRESS | COMPLETE | BLOCKED

## Completed
- [list of deliverables done]

## In Progress
- [current work]

## Blockers
- [any issues]
```

This lets the orchestrator track state without running the code.

---

*This document is the ground truth for the pipeline-doctor build. Any ambiguity in a phase spec should be resolved by referencing the project structure, code quality rules, and quality gates above.*
