"""
Lineage routes — graph traversal and visualization endpoints.

These depend on a prior call to POST /analyze to populate the in-memory store.
For a stateless API, pass analysis_id as a query param to identify which
analysis context to query.
"""

from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.lineage_graph import LineageGraph
from app.state import state

logger = structlog.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class NodeLineage(BaseModel):
    model_name: str
    unique_id: str
    upstream: list[str]
    downstream: list[str]
    upstream_count: int
    downstream_count: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/{model_name}", response_model=NodeLineage)
async def get_model_lineage(
    model_name: str,
    depth: int = Query(default=999, ge=1, le=50, description="Max traversal depth"),
    analysis_id: Optional[str] = Query(
        default=None,
        description="Analysis ID from POST /analyze. Defaults to the most recent analysis.",
    ),
) -> NodeLineage:
    """Return the upstream and downstream lineage for a specific model by name.

    Model name is the short name (e.g. 'mart_customer_ltv'), not the full unique_id.
    If multiple models share the same name (cross-project setups), the first match wins.
    """
    effective_id = analysis_id or state.latest_analysis_id
    if effective_id is None or effective_id not in state.analysis_store:
        raise HTTPException(
            status_code=404,
            detail="No analysis found. Run POST /analyze first.",
        )

    parsed = state.analysis_store[effective_id]
    lineage_graph = state.lineage_store[effective_id]

    # Find the unique_id for this model name
    unique_id: Optional[str] = None
    for uid, node in parsed.models.items():
        if node.name == model_name:
            unique_id = uid
            break

    if unique_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_name}' not found in analysis {effective_id}",
        )

    upstream = lineage_graph.get_upstream(unique_id, depth=depth)
    downstream = lineage_graph.get_downstream(unique_id, depth=depth)

    logger.info(
        "lineage_queried",
        model_name=model_name,
        upstream_count=len(upstream),
        downstream_count=len(downstream),
    )

    return NodeLineage(
        model_name=model_name,
        unique_id=unique_id,
        upstream=upstream,
        downstream=downstream,
        upstream_count=len(upstream),
        downstream_count=len(downstream),
    )


@router.get("", response_model=dict)
async def get_full_graph(
    analysis_id: Optional[str] = Query(
        default=None,
        description="Analysis ID from POST /analyze. Defaults to the most recent analysis.",
    ),
) -> dict:
    """Return the full lineage graph in Cytoscape.js format for frontend rendering.

    The React Flow frontend consumes this to render the interactive DAG visualization.
    Node positions are pre-computed using topological generation order (left-to-right).
    """
    effective_id = analysis_id or state.latest_analysis_id
    if effective_id is None or effective_id not in state.lineage_store:
        raise HTTPException(
            status_code=404,
            detail="No analysis found. Run POST /analyze first.",
        )

    lineage_graph = state.lineage_store[effective_id]
    cytoscape_data = lineage_graph.to_cytoscape_format()

    logger.info(
        "full_graph_exported",
        analysis_id=effective_id,
        node_count=len(cytoscape_data.get("nodes", [])),
        edge_count=len(cytoscape_data.get("edges", [])),
    )

    return cytoscape_data
