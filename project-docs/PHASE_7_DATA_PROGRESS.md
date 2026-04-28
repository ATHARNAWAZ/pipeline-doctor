# Phase 7 — Data Layer Verification and Enhancements

**Date:** 2026-03-18
**Scope:** dbt manifest parser, lineage graph, Pydantic models, frontend type contract

---

## Verification Results

### 1. sample_manifest.json — structure validity

- Valid JSON, parses without errors.
- Schema: `https://schemas.getdbt.com/dbt/manifest/v10/manifest.json` (dbt 1.7.0).
- Top-level keys present: `metadata`, `nodes`, `sources`, `exposures`, `metrics`, `groups`, `selectors`, `docs`, `parent_map`, `child_map`.
- 12 model nodes, 5 source nodes, 2 exposure nodes — all with `resource_type` set correctly.

### 2. Dependency reference validation

All `depends_on.nodes` values in the manifest resolve to known unique_ids.
No dangling cross-project or deleted-model references exist in the sample data.

Graph structure confirmed:
```
source layer (0): 5 raw source nodes
staging layer (1): stg_transactions, stg_customers, stg_products, stg_events, stg_sessions
intermediate layer (2): int_customer_transactions, int_product_revenue, int_user_journey
mart layer (3): mart_customer_ltv, mart_revenue_summary, mart_funnel_analysis, mart_daily_metrics
exposure layer (4): revenue_dashboard, growth_dashboard
```

### 3. run_results.json cross-reference

All 12 unique_ids in run_results.json are present in manifest.json.
Two models have `status=error` with realistic execution times:

| model | status | execution_time |
|---|---|---|
| mart_customer_ltv | error | 12.715s |
| mart_revenue_summary | error | 9.154s |

No execution time is 0.0 — all values are realistic wall-clock times.

### 4. ManifestParser correctness

- `_extract_nodes()`: correctly filters on `resource_type == "model"`, skips tests/seeds/snapshots.
- `_extract_sources()`: reads from `manifest["sources"]` key, not from `nodes`.
- `_extract_exposures()`: reads from `manifest["exposures"]` key.
- `depends_on.nodes`: correctly populated via `DbtNodeDependsOn.nodes` field.
- `failing_models`: populated in `merge()` for all unique_ids with a failing run result status. Both failing mart models are correctly identified.

### 5. LineageGraph correctness

Edge direction is parent -> child (upstream -> downstream). Verified:

- `get_upstream("mart_customer_ltv")` returns:
  - `int_customer_transactions`
  - `stg_customers`
  - `stg_transactions`
  - `source.raw.raw_customers`
  - `source.raw.raw_transactions`

- `get_downstream("stg_transactions")` returns all 7 downstream nodes including both exposures.

- `get_failure_blast_radius(["mart_customer_ltv", "mart_revenue_summary"])`:
  - `mart_customer_ltv` -> `[revenue_dashboard]`, score=2.0
  - `mart_revenue_summary` -> `[revenue_dashboard]`, score=2.0
  - Exposures are correctly included and weighted at 2.0 (user-facing impact).

### 6. Frontend format (cytoscape export vs React Flow)

**Issue found:** The original `to_cytoscape_format()` used the Cytoscape.js `{data: {id, label, resource_type}, position}` format. This matched the existing `CytoscapeNodeData` TypeScript type but was missing the rich fields needed by the frontend (`name`, `description`, `status`, `error_message`, `execution_time`, `tags`, `columns`, `raw_code`, `upstream`, `downstream`, `layer`). The frontend was reconstructing upstream/downstream from edges, and getting status only from the separate `AnalysisResult` response.

**Fix applied:** See enhancements below.

---

## Enhancements Applied

### Enhancement 1: `validate_dependencies()` in ManifestParser

Added to `backend/app/services/manifest_parser.py`.

Checks every `depends_on.nodes` reference in every model against the set of all known unique_ids (models + sources + exposures). Returns a list of warning strings for any unresolved reference. Emits structured log events `unresolved_dependency` and `dependency_validation_failed`/`dependency_validation_passed`.

Use case: partial manifest analysis (e.g. `dbt ls --select +mart_customer_ltv`), deleted model cleanup, cross-project ref debugging.

### Enhancement 2: `get_layer()` and `get_nodes_by_layer()` in LineageGraph

Added to `backend/app/services/lineage_graph.py`.

`get_layer(node_id)`:
- Returns the longest-path distance from any root node (in-degree=0) to the given node.
- Uses ancestor subgraph extraction + `nx.dag_longest_path_length()`.
- Layer 0 = source nodes. Layer 1 = staging. Layer 2 = intermediate. Layer 3 = mart. Layer 4 = exposure.
- Returns 0 gracefully for unknown nodes and cyclic subgraphs.

`get_nodes_by_layer()`:
- Groups all node IDs by layer number.
- Returns `dict[int, list[str]]` with each layer's list sorted alphabetically for deterministic rendering.
- Used by `to_cytoscape_format()` for position computation.

Verified layer assignments for the sample manifest:
- sources = 0, staging = 1, intermediate = 2, mart = 3, exposures = 4.

### Enhancement 3: Run result annotation in `build_from_manifest()`

Updated `build_from_manifest()` to store `status`, `error_message`, and `execution_time` as node attributes on every node in the graph. These come from `parsed_manifest.run_results`.

Rules:
- Nodes with no run result get `status="unknown"` (sources, exposures, models not in the run).
- `error_message` is only populated for non-success statuses to avoid storing verbose success messages.
- All other node attributes are now stored on graph nodes: `description`, `original_file_path`, `tags`, `columns` (serialized from Pydantic), `raw_code`.

This means a single call to `to_cytoscape_format()` now returns everything the frontend needs without requiring a separate join against the `AnalysisResult` response.

### Enhancement 4: `to_cytoscape_format()` rewrite

Rewrote `to_cytoscape_format()` in `backend/app/services/lineage_graph.py`.

The new output format for each node:
```json
{
  "data": {
    "id": "model.fintech_pipeline.stg_transactions",
    "label": "stg_transactions",
    "resource_type": "model",
    "name": "stg_transactions",
    "description": "Staged payment transactions...",
    "status": "success",
    "error_message": null,
    "execution_time": 2.779,
    "tags": [],
    "columns": {"transaction_id": {"name": "...", "description": "...", "data_type": "varchar"}},
    "raw_code": "...",
    "original_file_path": "models/staging/stg_transactions.sql",
    "layer": 1,
    "upstream": ["source.fintech_pipeline.raw.raw_transactions"],
    "downstream": ["model.fintech_pipeline.int_customer_transactions", "..."]
  },
  "position": {"x": 280, "y": 0}
}
```

Position computation: `x = layer * 280`, `y = layer_index * 120`. Deterministic because `get_nodes_by_layer()` sorts each layer alphabetically.

The `label` field is kept for backward compatibility. `resource_type` is normalised to `model | source | exposure` (anything unknown becomes `model`).

Edge IDs changed from `edge_0`, `edge_1` to `edge_{src_name}_{tgt_name}` for debuggability.

### Enhancement 5: Frontend types and hook updated

`frontend/src/types/index.ts` — `CytoscapeNodeData` extended with all new fields (`name`, `description`, `status`, `error_message`, `execution_time`, `tags`, `columns`, `raw_code`, `original_file_path`, `layer`, `upstream`, `downstream`).

`frontend/src/hooks/useAnalysis.ts` — `buildGraphData()` rewritten to consume the richer node data directly:
- Maps `cyNode.data.name` (with `label` as fallback) to `DbtModel.name`.
- Populates `description`, `original_file_path`, `raw_code`, `columns`, `tags`, `status`, `error_message`, `execution_time` from the node data.
- `upstream`/`downstream` now come from the backend-precomputed lists instead of being rebuilt from edges client-side.
- The edge-reconstruction loop is removed.

The `uploadManifest` annotation pass is preserved but simplified — it only overrides failing nodes using `AnalysisResult.failing_models` as the authoritative source, leaving already-correct non-failing nodes untouched.

---

## File Summary

| File | Change |
|---|---|
| `backend/app/services/manifest_parser.py` | Added `validate_dependencies()` method |
| `backend/app/services/lineage_graph.py` | Added `get_layer()`, `get_nodes_by_layer()`; rewrote `build_from_manifest()` to annotate run results; rewrote `to_cytoscape_format()` |
| `frontend/src/types/index.ts` | Extended `CytoscapeNodeData` with 10 new fields |
| `frontend/src/hooks/useAnalysis.ts` | Rewrote `buildGraphData()` to consume richer backend format; simplified annotation pass |

---

## Validation Script Output

All 7 test sections passed:
1. JSON validity — both sample files parse cleanly
2. Pydantic model validation — 12 nodes, 5 sources, 2 exposures, 12 run results
3. ManifestParser — correct extraction, merge, failing_models list
4. validate_dependencies — 0 unresolved references in sample data
5. LineageGraph — correct upstream/downstream/blast-radius traversal including exposures
6. get_layer / get_nodes_by_layer — correct layer assignments (source=0, stg=1, int=2, mart=3, exposure=4)
7. to_cytoscape_format — all required fields present, failing node has status=error and error_message, positions are layer-based
