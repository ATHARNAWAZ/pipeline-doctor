# Reality Check Certification

**Date:** 2026-03-18
**Assessor:** TestingRealityChecker
**Project:** pipeline-doctor
**Working Directory:** c:/python_development/MY_PORTFOLIO_PROJECTS/pipeline-doctor/

---

## Verification Results

| # | Check | Evidence | Status |
|---|-------|----------|--------|
| 1 | Python syntax (5 files) | `python -m py_compile` run independently on main.py, claude_service.py, manifest_parser.py, lineage_graph.py, query.py — all returned exit 0 with no output | PASS |
| 2 | Sample data integrity | Script confirmed: 12 models, 5 sources, 2 exposures, 2 failures; both failing unique_ids (mart_customer_ltv, mart_revenue_summary) present in manifest nodes; "All dependencies resolve: OK" | PASS |
| 3 | Claude model ID | `grep` returned only two hits, both `claude-sonnet-4-6`: config.py default value and claude_service.py comment. No other model strings found anywhere in backend/ | PASS |
| 4 | No hardcoded secrets | `grep` for sk-ant-api, sk-ant-, AKIA, postgres://.*:.*@ in backend/*.py returned zero results. Same scan on frontend/*.ts/*.tsx returned zero results | PASS |
| 5 | No print() statements in app code | `grep -rn "^[[:space:]]*print("` on backend/app/ returned zero results | PASS |
| 6 | .gitignore coverage | Read .gitignore end-to-end: .env (line 49), node_modules/ (line 34), __pycache__/ (line 2), .terraform/ (line 40), *.tfstate (line 42), *.zip (line 64) — all 6 required patterns present | PASS |
| 7 | README length | `wc -l` returned 459 lines (requirement: >150) | PASS |
| 8 | rag_engine.py required methods | Read file end-to-end. RAGEngine class: line 62. initialize(): line 78 (async, sets up pgvector extension + embedding model). index_manifest(): line 192 (embeds all models and sources, upserts to pgvector). query(): line 275 (vector search with fallback). Embedding fallback: OpenAI ada-002 attempted first (lines 128-142), HuggingFace BAAI/bge-small-en-v1.5 on failure (lines 147-160) | PASS |
| 9 | lineage_graph.py required methods | Read file end-to-end. LineageGraph class: line 36. build_from_manifest() classmethod: line 46. get_upstream(): line 193. get_downstream(): line 211. get_failure_blast_radius(): line 223. to_cytoscape_format(): line 332 (returns {nodes, edges} with full node data structure including id, label, resource_type, name, description, status, error_message, execution_time, tags, columns, raw_code, original_file_path, layer, upstream, downstream). get_layer(): line 255. get_nodes_by_layer(): line 284 | PASS |
| 10 | TypeScript AnalysisResult matches backend response | Backend AnalysisResult (analyze.py lines 47-53): analysis_id, node_count, source_count, exposure_count, failing_models, lineage_summary{total_nodes, total_edges}. Frontend AnalysisResult (types/index.ts lines 51-61): identical field names and compatible types. Backend FailingModelSummary: unique_id, name, error_message (Optional[str]), status. Frontend FailingModelSummary: unique_id, name, error_message (string|null, optional), status. All fields align | PASS |

---

## Evidence Details

### Check 1: Python Syntax
Command executed independently (not trusting Evidence Collector):
```
python -m py_compile backend/app/main.py
python -m py_compile backend/app/services/claude_service.py
python -m py_compile backend/app/services/manifest_parser.py
python -m py_compile backend/app/services/lineage_graph.py
python -m py_compile backend/app/routers/query.py
```
All returned exit code 0, no stderr output.

### Check 2: Sample Data
Script output:
```
Models: 12 (need 12)
Sources: 5 (need 5)
Exposures: 2 (need 2)
Failures: 2 (need 2)
  model.fintech_pipeline.mart_customer_ltv: in_manifest=True
  model.fintech_pipeline.mart_revenue_summary: in_manifest=True
All dependencies resolve: OK
```

### Check 3: Claude Model ID
Grep output (complete, no other hits):
```
backend/app/config.py:    claude_model: str = "claude-sonnet-4-6"
backend/app/services/claude_service.py:        self._model = settings.claude_model  # "claude-sonnet-4-6"
```
The model value is read from `settings.claude_model` at runtime, not hardcoded again. The comment confirms the expected value. No other model version strings (claude-3, claude-2, claude-sonnet-4-5) appear anywhere.

### Check 8: RAGEngine Method Summary
- `initialize(db_url)`: Creates async SQLAlchemy engine, enables pgvector extension, loads embedding model (OpenAI or HuggingFace fallback), sets up LlamaIndex vector store.
- `index_manifest(parsed_manifest)`: Converts models and sources to LlamaIndex Documents with SQL/column/tag content, embeds them via thread executor, upserts to pgvector.
- `query(question, parsed_manifest, failing_context)`: Vector similarity search via pgvector; injects failing_context nodes; falls back to keyword matching if pgvector unavailable. Returns RetrievedContext with relevant node IDs and formatted context string.
- Embedding fallback: `_load_embedding_model()` tries `llama_index.embeddings.openai.OpenAIEmbedding` (ada-002) when `settings.openai_api_key` is set; catches exception and falls back to `llama_index.embeddings.huggingface.HuggingFaceEmbedding` (BAAI/bge-small-en-v1.5).

### Check 9: LineageGraph Method Summary
- `build_from_manifest(parsed_manifest)`: Classmethod. Adds model/source/exposure nodes with full metadata, wires edges from depends_on, annotates run result status, detects cycles.
- `get_upstream(node_id, depth)`: BFS on reversed graph up to `depth` hops.
- `get_downstream(node_id, depth)`: BFS on forward graph up to `depth` hops.
- `get_failure_blast_radius(failing_node_ids)`: Returns dict of FailureImpact per failing node; exposures weighted 2x in impact score.
- `to_cytoscape_format()`: Returns `{"nodes": [...], "edges": [...]}`. Each node has a `data` dict with id, label, resource_type, name, description, status, error_message, execution_time, tags, columns, raw_code, original_file_path, layer, upstream, downstream; and a `position` dict with x/y computed from layer and intra-layer index.
- `get_layer(node_id)`: Builds ancestor subgraph and measures longest-path length. Returns int.
- `get_nodes_by_layer()`: Iterates all nodes, calls `get_layer()`, groups by layer, sorts each layer. Returns dict[int, list[str]].

### Check 10: Type Alignment Detail

Backend `POST /analyze` returns `AnalysisResult`:
```python
class FailingModelSummary(BaseModel):
    unique_id: str
    name: str
    error_message: Optional[str] = None
    status: str

class LineageSummary(BaseModel):
    total_nodes: int
    total_edges: int

class AnalysisResult(BaseModel):
    analysis_id: str
    node_count: int
    source_count: int
    exposure_count: int
    failing_models: list[FailingModelSummary]
    lineage_summary: LineageSummary
```

Frontend `AnalysisResult` interface (types/index.ts):
```typescript
interface FailingModelSummary {
  unique_id: string;
  name: string;
  error_message?: string | null;
  status: string;
}

interface AnalysisResult {
  analysis_id: string;
  node_count: number;
  source_count: number;
  exposure_count: number;
  failing_models: FailingModelSummary[];
  lineage_summary: {
    total_nodes: number;
    total_edges: number;
  };
}
```

Field-by-field alignment: all 6 top-level fields match by name and type. `error_message: Optional[str]` serialises to `string | null` in JSON, matching `string | null` in TypeScript. No extra fields on either side that would cause silent data loss.

---

## Issues Found

None. All 10 verification checks passed with direct evidence. No fixes required.

---

## Certification Decision

**APPROVED**

All 11 criteria passed with direct evidence gathered by independent verification commands. The Evidence Collector's prior report was accurate — no discrepancies found between claimed status and actual state.

---

## Conditions

None. Certification is unconditional.

---

## Notes on Assessment Methodology

- Python syntax checks were run independently, not delegated to prior reports.
- Sample data validation script was executed fresh; output matched Evidence Collector claims exactly.
- Model ID grep searched the entire backend/ tree; only two legitimate references found, both resolving to the same `claude-sonnet-4-6` string via settings indirection.
- Secret scanning produced zero hits across both backend and frontend source trees.
- Print statement scan was clean; structlog is used throughout for structured logging.
- rag_engine.py and lineage_graph.py were read end-to-end; all required methods confirmed present at exact line numbers.
- Type alignment was verified by reading both files in full and comparing each field name and type explicitly.

---

**Integration Agent:** TestingRealityChecker
**Assessment Date:** 2026-03-18
**Evidence Location:** Verified directly from source files
**Re-assessment Required:** No — all criteria met
