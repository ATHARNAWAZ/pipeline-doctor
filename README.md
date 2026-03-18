# pipeline-doctor

> AI-powered dbt pipeline debugger — upload your manifest, ask what broke, get a diagnosis.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)

---

You are getting paged at 2am. Your `mart_revenue` model failed. You open dbt's error output and see a cryptic SQL error. You manually trace upstream through 15 models to figure out whether the problem is in `mart_revenue` itself or something it depends on. You find it — `int_customer_transactions` is the culprit — but by then it is 3am and the revenue dashboard has been broken for an hour.

I built pipeline-doctor because that situation is entirely avoidable. Upload your `manifest.json` and `run_results.json`, ask "why did `mart_revenue` fail?", and get a plain-English diagnosis with the root cause, the offending SQL line, and which downstream models are blocked. The whole thing takes under 30 seconds.

---

## How it works (the short version)

1. Upload your dbt artifacts — `manifest.json` and `run_results.json`
2. pipeline-doctor parses them into a NetworkX DAG, indexes all your models into pgvector, and identifies failing nodes
3. Ask a question in plain English via the web UI or the API
4. The RAG engine retrieves the most relevant model code and lineage context
5. Claude Sonnet 4.6 reads that context — including the actual SQL, column definitions, error messages, and upstream/downstream chain — and gives you a specific diagnosis

There is no fine-tuning, no magic. It is a focused system prompt, good context assembly, and a model that is actually good at reading SQL.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        pipeline-doctor                          │
│                                                                 │
│  ┌──────────┐    ┌────────────────┐    ┌─────────────────────┐ │
│  │ manifest │───▶│ Manifest Parser│───▶│   NetworkX DAG      │ │
│  │  .json   │    │  + Run Results │    │  (lineage graph)    │ │
│  └──────────┘    └────────────────┘    └─────────┬───────────┘ │
│                                                   │             │
│  ┌──────────┐    ┌────────────────┐    ┌─────────▼───────────┐ │
│  │  Natural │───▶│  RAG Engine    │───▶│  Claude Sonnet 4.6  │ │
│  │ Language │    │  (LlamaIndex + │    │  (AI diagnosis)     │ │
│  │ Question │    │   pgvector)    │    └─────────────────────┘ │
│  └──────────┘    └────────────────┘                            │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    AWS (optional)                        │  │
│  │  S3 (manifest storage) → EventBridge → Lambda → Slack   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

The backend is a FastAPI app. The frontend is a React + Vite app with an interactive lineage DAG visualization. PostgreSQL with pgvector stores the model embeddings. Everything runs in Docker locally.

---

## Quick Start

**Prerequisites:** Docker and Docker Compose, an Anthropic API key.

```bash
git clone https://github.com/ATHARNAWAZ/pipeline-doctor
cd pipeline-doctor
cp .env.example .env
```

Open `.env` and set your `ANTHROPIC_API_KEY`. That is the only required change.

```bash
docker-compose up -d
```

The backend starts on port 8000, the frontend on port 5173, and PostgreSQL on 5432. The backend waits for Postgres to be healthy before starting.

**Upload your dbt artifacts:**

```bash
# With both manifest and run results (recommended — enables failure analysis)
curl -X POST http://localhost:8000/analyze \
  -F "manifest=@/path/to/your/target/manifest.json" \
  -F "run_results=@/path/to/your/target/run_results.json"

# Manifest only (static lineage analysis, no failure data)
curl -X POST http://localhost:8000/analyze \
  -F "manifest=@/path/to/your/target/manifest.json"
```

**Ask a question:**

```bash
curl -X POST http://localhost:8000/query/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Why did mart_customer_ltv fail?"}'
```

**Or use the web UI:**

Open [http://localhost:5173](http://localhost:5173). Upload your artifacts with the file picker, then use the chat interface to ask questions. The lineage graph renders as an interactive DAG — click any node to see its SQL, columns, run status, and upstream/downstream connections.

---

## Connecting your dbt project

After running `dbt run` or `dbt compile`, both artifact files are in your project's `target/` directory:

```
your-dbt-project/
└── target/
    ├── manifest.json       # compiled project graph — produced by dbt compile, run, or test
    └── run_results.json    # execution results — produced by dbt run or dbt test
```

**Required dbt version:** manifest format v10+, which corresponds to dbt 1.5 and above. If you are on an older version, upgrade dbt — there are no workarounds for older manifest schemas.

```bash
# Verify your manifest version
python -c "import json; m=json.load(open('target/manifest.json')); print(m['metadata']['dbt_schema_version'])"
# Should print: https://schemas.getdbt.com/dbt/manifest/v10/manifest.json (or higher)
```

**Typical upload workflow after a dbt run:**

```bash
dbt run --select +mart_customer_ltv  # or dbt run for the full project

curl -X POST http://localhost:8000/analyze \
  -F "manifest=@target/manifest.json" \
  -F "run_results=@target/run_results.json"
```

The parser handles large manifests (500+ model projects produce 50MB+ files) without loading the whole document into memory at once. Malformed individual nodes are skipped with a warning rather than crashing the parse — production manifests are messy.

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Your API key from [console.anthropic.com](https://console.anthropic.com). The only thing that costs money. |
| `DATABASE_URL` | Yes | `postgresql://pipeline_doctor:localdev@localhost:5432/pipeline_doctor` | PostgreSQL connection string. Must point to a Postgres instance with pgvector installed. Docker Compose provides this automatically. |
| `POSTGRES_PASSWORD` | No | `localdev` | Password for the Docker Compose Postgres instance. Ignored when using an external DB. |
| `OPENAI_API_KEY` | No | — | If set, uses OpenAI `text-embedding-ada-002` for embeddings (1536-dim, slightly better quality). If not set, falls back to `BAAI/bge-small-en-v1.5` running locally on CPU (384-dim, no API cost, works offline). |
| `SLACK_WEBHOOK_URL` | No | — | Incoming webhook URL for failure alerts. Create one at [api.slack.com/apps](https://api.slack.com/apps) → Incoming Webhooks. The Notifier Lambda posts Block Kit messages here. |
| `S3_BUCKET_NAME` | No | `pipeline-doctor-local` | S3 bucket for manifest storage in the AWS deployment. Not used in local Docker setup. |
| `AWS_REGION` | No | `us-east-1` | AWS region for the Terraform deployment. |
| `AWS_ACCESS_KEY_ID` | No | — | AWS credentials for the Terraform deployment. Not needed for local Docker setup. |
| `AWS_SECRET_ACCESS_KEY` | No | — | AWS credentials for the Terraform deployment. |
| `LOG_LEVEL` | No | `INFO` | Structlog level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`. Use `DEBUG` to see full prompt assembly and token counts. |

---

## API Reference

The full OpenAPI spec is at [http://localhost:8000/docs](http://localhost:8000/docs) when the backend is running.

### POST /analyze

Upload dbt artifacts and build the lineage graph. Returns an `analysis_id` used by subsequent endpoints.

```bash
curl -X POST http://localhost:8000/analyze \
  -F "manifest=@target/manifest.json" \
  -F "run_results=@target/run_results.json"
```

```json
{
  "analysis_id": "a3f2c1b0-...",
  "node_count": 127,
  "source_count": 8,
  "exposure_count": 3,
  "failing_models": [
    {
      "unique_id": "model.fintech_pipeline.mart_customer_ltv",
      "name": "mart_customer_ltv",
      "status": "error",
      "error_message": "division by zero\nLINE 34: .../ customer_lifetime_days..."
    }
  ],
  "lineage_summary": {
    "total_nodes": 138,
    "total_edges": 201
  }
}
```

### POST /query/ask

Ask a natural language question. Returns the full answer synchronously. Good for API clients, scripts, and Slack integrations.

```bash
curl -X POST http://localhost:8000/query/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What models depend on stg_transactions?"}'
```

```json
{
  "answer": "Three models depend on `stg_transactions`: ...",
  "relevant_models": ["model.fintech_pipeline.stg_transactions", "..."],
  "confidence": 0.847
}
```

`confidence` is the cosine similarity score from pgvector retrieval (0.0–1.0). It is 0.0 when the RAG engine fell back to keyword search (e.g. pgvector unavailable).

### WS /query/stream

WebSocket endpoint for streaming responses. The web UI uses this for the typewriter effect.

**Protocol:**

```
Client → Server:  {"question": "Why did mart_customer_ltv fail?", "analysis_id": null}
Server → Client:  {"chunk": "The `mart_customer_ltv`"}
Server → Client:  {"chunk": " model failed with a"}
Server → Client:  {"chunk": " division by zero error..."}
Server → Client:  {"done": true}
```

If something goes wrong mid-stream, the server sends `{"error": "..."}` before closing.

### GET /lineage/{model_name}

Return upstream and downstream lineage for a specific model.

```bash
curl http://localhost:8000/lineage/mart_customer_ltv
curl "http://localhost:8000/lineage/mart_customer_ltv?depth=3"  # limit traversal depth
```

```json
{
  "model_name": "mart_customer_ltv",
  "unique_id": "model.fintech_pipeline.mart_customer_ltv",
  "upstream": ["model.fintech_pipeline.int_customer_transactions", "..."],
  "downstream": ["exposure.fintech_pipeline.revenue_dashboard"],
  "upstream_count": 4,
  "downstream_count": 1
}
```

### GET /lineage

Return the full graph in the format consumed by the React Flow frontend. Also useful for debugging the parsed DAG.

```bash
curl http://localhost:8000/lineage
```

### GET /analyze/failures

Return failing models from the most recent analysis. Useful for polling after a dbt run.

```bash
curl http://localhost:8000/analyze/failures
```

### GET /analyze/status

Pipeline health summary.

```bash
curl http://localhost:8000/analyze/status
# {"total_models": 127, "passing": 124, "failing": 2, "warnings": 1, "health_pct": 97.6}
```

---

## Example diagnosis

**Upload:**
```bash
curl -X POST http://localhost:8000/analyze \
  -F "manifest=@target/manifest.json" \
  -F "run_results=@target/run_results.json"
```

**Ask:**
```bash
curl -X POST http://localhost:8000/query/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Why did mart_customer_ltv fail?"}'
```

**Response:**

> **`mart_customer_ltv` — Division by zero at line 34**
>
> The model failed with `ERROR: division by zero` at line 34. The culprit is `customer_lifetime_days` — for customers acquired today, `DATEDIFF(CURRENT_DATE, first_purchase_date)` returns 0, and the downstream division in the LTV calculation crashes.
>
> **Root cause:** This is a data issue, not a logic error. `int_customer_transactions` does not filter out same-day customers before computing the ratio. Any customer whose `first_purchase_date` equals today will produce a zero denominator.
>
> **Fix:**
> ```sql
> -- Replace the denominator in mart_customer_ltv line 34:
> -- Before:
> total_revenue / customer_lifetime_days AS daily_ltv
>
> -- After:
> total_revenue / NULLIF(customer_lifetime_days, 0) AS daily_ltv
> ```
>
> **Affected downstream:** `exposure.revenue_dashboard` is blocked until this is fixed. The dashboard has been reading stale data since the last successful run.

---

## How it actually works (for engineers)

### Manifest parsing

`ManifestParser` reads `manifest.json` and `run_results.json` into typed Pydantic models, then returns a clean `ParsedManifest` dataclass. Only `resource_type: "model"` nodes from the manifest's `nodes` key are extracted — tests, seeds, and snapshots are skipped for now. Individual malformed nodes are skipped with a warning rather than crashing the whole parse, which matters for partial manifests produced by `dbt ls --select`.

`merge()` is non-mutating — it creates a new `ParsedManifest` with run results attached, so you can safely call it multiple times with different run result files.

### Lineage graph

`LineageGraph` wraps a NetworkX `DiGraph`. Edge direction is parent → child (data flow direction), so `stg_transactions → int_customer_transactions → mart_customer_ltv`. Source nodes (external tables) and exposure nodes (dashboards, BI tools) are included so blast-radius calculations propagate all the way from a raw data source to the dashboards that will break.

The `get_failure_blast_radius()` method counts downstream affected nodes and weights exposures at 2x (a broken dashboard is immediate user-facing impact). The `to_cytoscape_format()` method serializes the graph for the React Flow frontend, with x/y positions computed from topological layer (x = layer * 280px) and node index within the layer (y = index * 120px).

### RAG retrieval

`RAGEngine` uses [LlamaIndex](https://www.llamaindex.ai/) with a pgvector backend. Each dbt model becomes one document — not chunked further — because splitting a 50-line SQL file loses the relationship between the SQL logic and the column definitions. The document text packs name, description, materialization type, tags, upstream dependencies, column names/types, and full SQL into a single string. Order matters for embedding quality: name and SQL appear first.

Embedding model selection is automatic: if `OPENAI_API_KEY` is set, it uses `text-embedding-ada-002` (1536-dim). Otherwise it downloads `BAAI/bge-small-en-v1.5` from HuggingFace — a 33M parameter model that runs on CPU and produces 384-dim embeddings. For a 500-model project, full re-indexing takes ~30–60 seconds locally, ~5 seconds with OpenAI.

When pgvector is unavailable (no database, or extension not installed), the engine falls back to keyword matching on model names, descriptions, and tags. This keeps the tool functional without a database, just less precise.

### Claude prompting

`ClaudeService` sends two types of prompts:

1. **Failure diagnosis** (`explain_failure`): error message appears first, before the context. This is intentional — leading with the context causes Claude to anchor on it and produce less targeted diagnoses. The prompt includes the raw SQL, error message, column definitions, upstream chain, and downstream blast radius.

2. **Natural language questions** (`stream_response`): question appears first, followed by retrieved context and a one-line manifest summary (total models, how many are failing). This handles questions like "what models use the orders table?" that are not tied to a specific failure.

The system prompt is the most important string in the codebase. Every rule in it was added because without it, Claude would do something unhelpful: generically saying "the model" instead of naming it, diagnosing the symptom when the root cause is upstream, or hallucinating column names not present in the context.

### Streaming

The WebSocket `/query/stream` endpoint uses the Anthropic async streaming API (`client.messages.stream()`). Text chunks arrive as Claude generates them and are forwarded immediately to the WebSocket client as `{"chunk": "..."}` messages. When streaming finishes, the server sends `{"done": true}`. Client disconnects mid-stream are caught and logged but do not raise — it is normal for a user to navigate away before the response finishes.

The synchronous `POST /query/ask` endpoint calls the same `stream_response()` method and collects all chunks into a single string before returning, so the two endpoints share the same code path.

---

## Development setup (without Docker)

If you want to contribute or run without Docker:

**Prerequisites:** Python 3.11+, PostgreSQL 14+ with pgvector installed, Node.js 18+.

**Install pgvector:**
```bash
# macOS with Homebrew
brew install pgvector

# Ubuntu/Debian
apt install postgresql-16-pgvector

# Or follow: https://github.com/pgvector/pgvector#installation
```

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create the database
createdb pipeline_doctor
psql pipeline_doctor -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Set environment
cp ../.env.example .env
# Edit .env with your ANTHROPIC_API_KEY and DATABASE_URL

# Run
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

**Run the tests:**
```bash
cd backend
pytest tests/ -v
```

---

## AWS deployment

The `infra/` directory contains Terraform that deploys two Lambda functions:

- **Analyzer Lambda** — triggered by S3 object creation (new `manifest.json` uploaded to the manifests bucket). Runs the same parse + RAG index pipeline as the local version.
- **Notifier Lambda** — triggered by EventBridge on a daily schedule and by SNS. Calls Claude to generate a Slack Block Kit summary of any failing models and posts it to your `#data-alerts` channel.

The event flow: dbt CI uploads `manifest.json` to S3 → EventBridge fires → Analyzer Lambda parses and indexes → if failures found, publishes to SNS → Notifier Lambda generates a Slack alert.

**Deploy:**
```bash
cd infra
terraform init
terraform plan \
  -var="anthropic_api_key=sk-ant-..." \
  -var="database_url=postgresql://..." \
  -var="slack_webhook_url=https://hooks.slack.com/..."

terraform apply
```

**Required Terraform variables:**

| Variable | Description |
|----------|-------------|
| `anthropic_api_key` | Your Anthropic API key |
| `database_url` | PostgreSQL connection string (RDS recommended) |
| `slack_webhook_url` | Slack incoming webhook URL (optional — omit to skip Slack) |
| `openai_api_key` | Optional, for ada-002 embeddings in Lambda |

**Notes:**
- Lambda has a 15-minute timeout. For very large projects (1000+ models), the embedding step may exceed this. In that case, run indexing as a separate ECS task and point the Lambda at the pre-indexed pgvector table.
- The Lambda Function URL has `authorization_type = "NONE"` — add IAM auth or a custom authorizer before exposing it publicly.
- Remote Terraform state (S3 backend) is commented out in `main.tf`. Uncomment and configure it before running in a shared environment.

---

## Contributing

Fork, branch, PR. Keep changes focused — one feature or fix per PR.

```bash
git checkout -b feat/your-feature
# make changes
git push origin feat/your-feature
# open a PR against main
```

If you are adding a new endpoint or changing an existing one, include a test in `backend/tests/`. If you are changing the system prompt or RAG context assembly, test it against at least two different failure scenarios before PRing — prompt changes have a way of fixing one case while breaking another.

Open an issue first for anything substantial. No point building something that is already in progress.

---

## License

MIT — see [LICENSE](LICENSE).

---

*If pipeline-doctor saves you a 2am debugging session, give it a star. If it doesn't, open an issue and tell me why.*
