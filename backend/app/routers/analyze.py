"""
Analysis routes — the primary entry point for uploading dbt artifacts.

In-memory state is fine for MVP. When we add multi-user support or
persistence, replace the stores in app.state with a PostgreSQL-backed repo.
"""

from __future__ import annotations

import json
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.models.manifest import RunResultStatus
from app.services.lineage_graph import LineageGraph
from app.services.manifest_parser import ManifestParser, ParsedManifest
from app.state import state

logger = structlog.get_logger(__name__)

router = APIRouter()

_parser = ManifestParser()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


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


class PipelineStatus(BaseModel):
    total_models: int
    passing: int
    failing: int
    warnings: int
    health_pct: float  # 0-100


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", response_model=AnalysisResult)
async def analyze_pipeline(
    manifest: UploadFile = File(..., description="dbt manifest.json"),
    run_results: Optional[UploadFile] = File(
        None, description="dbt run_results.json (optional)"
    ),
) -> AnalysisResult:
    """Upload manifest.json and optional run_results.json for pipeline analysis.

    Returns a summary of failing models, lineage stats, and an analysis_id
    that can be used to query subsequent endpoints.
    """
    log = logger.bind(manifest_filename=manifest.filename)

    # Read manifest bytes and parse
    manifest_bytes = await manifest.read()
    if not manifest_bytes:
        raise HTTPException(status_code=400, detail="manifest.json file is empty")

    try:
        manifest_data = json.loads(manifest_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON in manifest.json: {exc}"
        ) from exc

    log.info("manifest_upload_received", size_bytes=len(manifest_bytes))

    try:
        parsed = _parser.parse_manifest(manifest_data=manifest_data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Parse run results if provided
    run_results_map = {}
    if run_results is not None:
        run_results_bytes = await run_results.read()
        if run_results_bytes:
            try:
                rr_data = json.loads(run_results_bytes)
                run_results_map = _parser.parse_run_results(run_results_data=rr_data)
            except Exception as exc:
                log.warning(
                    "run_results_parse_failed",
                    error=str(exc),
                    note="continuing without run results",
                )

    merged = _parser.merge(parsed, run_results_map)

    # Build lineage graph
    lineage_graph = LineageGraph.build_from_manifest(merged)
    nx_graph = lineage_graph.to_networkx_graph()

    # Store for subsequent queries
    analysis_id = str(uuid.uuid4())
    state.analysis_store[analysis_id] = merged
    state.lineage_store[analysis_id] = lineage_graph
    state.latest_analysis_id = analysis_id

    # Build failing model summaries
    failing_summaries: list[FailingModelSummary] = []
    for unique_id in merged.failing_models:
        node = merged.models.get(unique_id)
        run_result = merged.run_results.get(unique_id)

        name = node.name if node else unique_id.split(".")[-1]
        error_msg = run_result.message if run_result else None
        status = run_result.status.value if run_result else "unknown"

        failing_summaries.append(
            FailingModelSummary(
                unique_id=unique_id,
                name=name,
                error_message=error_msg,
                status=status,
            )
        )

    log.info(
        "analysis_complete",
        analysis_id=analysis_id,
        models=merged.node_count,
        failing=len(merged.failing_models),
    )

    return AnalysisResult(
        analysis_id=analysis_id,
        node_count=merged.node_count,
        source_count=len(merged.sources),
        exposure_count=len(merged.exposures),
        failing_models=failing_summaries,
        lineage_summary=LineageSummary(
            total_nodes=nx_graph.number_of_nodes(),
            total_edges=nx_graph.number_of_edges(),
        ),
    )


@router.get("/failures", response_model=list[FailingModelSummary])
async def get_failures() -> list[FailingModelSummary]:
    """Return failing models from the most recent analysis."""
    if state.latest_analysis_id is None or state.latest_analysis_id not in state.analysis_store:
        return []

    merged = state.analysis_store[state.latest_analysis_id]
    failing_summaries: list[FailingModelSummary] = []

    for unique_id in merged.failing_models:
        node = merged.models.get(unique_id)
        run_result = merged.run_results.get(unique_id)

        name = node.name if node else unique_id.split(".")[-1]
        error_msg = run_result.message if run_result else None
        status = run_result.status.value if run_result else "unknown"

        failing_summaries.append(
            FailingModelSummary(
                unique_id=unique_id,
                name=name,
                error_message=error_msg,
                status=status,
            )
        )

    return failing_summaries


@router.get("/status", response_model=PipelineStatus)
async def get_pipeline_status() -> PipelineStatus:
    """Return overall pipeline health metrics from the most recent analysis."""
    if state.latest_analysis_id is None or state.latest_analysis_id not in state.analysis_store:
        return PipelineStatus(
            total_models=0,
            passing=0,
            failing=0,
            warnings=0,
            health_pct=100.0,
        )

    merged = state.analysis_store[state.latest_analysis_id]

    total = merged.node_count
    failing_ids = set(merged.failing_models)

    # Count warnings separately — they're not hard failures but still worth flagging
    warnings = sum(
        1
        for uid, result in merged.run_results.items()
        if result.status == RunResultStatus.warn
    )
    hard_failures = sum(
        1
        for uid in failing_ids
        if merged.run_results.get(uid) and
        merged.run_results[uid].status in {RunResultStatus.error, RunResultStatus.fail}
    )
    passing = total - len(failing_ids)
    health_pct = (passing / total * 100) if total > 0 else 100.0

    return PipelineStatus(
        total_models=total,
        passing=passing,
        failing=hard_failures,
        warnings=warnings,
        health_pct=round(health_pct, 1),
    )
