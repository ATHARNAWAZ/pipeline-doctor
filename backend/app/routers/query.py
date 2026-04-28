"""
Query routes — Claude + RAG endpoints for natural language pipeline analysis.

Two interaction modes:
1. POST /ask — synchronous, returns the full answer. Good for API clients,
   Slack slash commands, and any caller that just wants the complete response.
2. WebSocket /stream — server-sent text chunks as Claude generates them.
   Good for the web UI where users want to see the answer appearing in real time.

Both endpoints rely on the same RAG + Claude pipeline. The only difference
is delivery mechanism.

Important: WebSocket /stream must handle disconnects gracefully. A dropped
connection during streaming is normal (user navigated away, timeout, etc.)
and should not crash the server or leave dangling tasks.
"""

from __future__ import annotations

import json
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.services.claude_service import ClaudeService
from app.services.rag_engine import RAGEngine, RetrievedContext
from app.state import state

logger = structlog.get_logger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Module-level service singletons
# ---------------------------------------------------------------------------

# These are initialized lazily on first request so startup doesn't fail if
# pgvector isn't available yet (e.g. when running tests locally).
_rag_engine: Optional[RAGEngine] = None
_claude_service: Optional[ClaudeService] = None


def _get_rag_engine(settings: Settings = Depends(get_settings)) -> RAGEngine:
    """Dependency: return or lazily initialize the RAG engine."""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine(settings)
    return _rag_engine


def _get_claude_service(settings: Settings = Depends(get_settings)) -> ClaudeService:
    """Dependency: return or lazily initialize the Claude service."""
    global _claude_service
    if _claude_service is None:
        _claude_service = ClaudeService(settings)
    return _claude_service


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str
    # analysis_id allows callers to ask about a specific uploaded manifest.
    # If None, the most recent analysis is used — good for the common case
    # where a user uploads once and then asks several follow-up questions.
    analysis_id: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    relevant_models: list[str]
    # Cosine similarity score from the vector store (0.0 if RAG fell back to
    # keyword search). Exposed so callers can show a confidence indicator.
    confidence: float


# ---------------------------------------------------------------------------
# POST /ask
# ---------------------------------------------------------------------------


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    rag_engine: RAGEngine = Depends(_get_rag_engine),
    claude_service: ClaudeService = Depends(_get_claude_service),
    settings: Settings = Depends(get_settings),
) -> AskResponse:
    """Answer a natural language question about the dbt pipeline.

    Retrieves relevant model context via RAG and sends it to Claude along with
    the question. Returns the full answer synchronously.
    """
    log = logger.bind(action="ask", question=request.question[:80])

    # Resolve which analysis to use
    analysis_id = request.analysis_id or state.latest_analysis_id
    if analysis_id is None or analysis_id not in state.analysis_store:
        raise HTTPException(
            status_code=404,
            detail=(
                "No analysis found. Upload a manifest.json via POST /analyze first, "
                "or provide a valid analysis_id."
            ),
        )

    parsed_manifest = state.analysis_store[analysis_id]
    lineage_graph = state.lineage_store.get(analysis_id)

    # Initialize RAG engine if this is the first request.
    # We defer initialization here rather than at startup so the endpoint
    # still works (with keyword fallback) when pgvector isn't reachable.
    if not rag_engine._initialized:
        try:
            await rag_engine.initialize(str(settings.database_url))
            # Index this manifest so the vector store is populated
            await rag_engine.index_manifest(parsed_manifest)
        except Exception as exc:
            log.warning(
                "rag_init_failed_using_fallback",
                error=str(exc),
            )
            # Don't raise — the fallback keyword search in query() will kick in

    # Retrieve relevant context
    context: RetrievedContext = await rag_engine.query(
        question=request.question,
        parsed_manifest=parsed_manifest,
        failing_context=parsed_manifest.failing_models if parsed_manifest.failing_models else None,
    )

    # Build manifest summary for the Claude prompt
    manifest_summary = {
        "total_models": parsed_manifest.node_count,
        "failing_count": len(parsed_manifest.failing_models),
        "project_name": _extract_project_name(parsed_manifest),
    }

    try:
        # stream_response is an async generator — iterate it directly (no await)
        chunks = []
        async for chunk in claude_service.stream_response(
            question=request.question,
            context=context,
            manifest_summary=manifest_summary,
        ):
            chunks.append(chunk)
        full_answer = "".join(chunks)
    except RuntimeError as exc:
        # AuthenticationError surfaces as RuntimeError from claude_service
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    log.info(
        "ask_complete",
        relevant_models=len(context.relevant_nodes),
        retrieval_score=round(context.retrieval_score, 3),
    )

    return AskResponse(
        answer=full_answer,
        relevant_models=context.relevant_nodes,
        confidence=round(context.retrieval_score, 3),
    )


# ---------------------------------------------------------------------------
# WebSocket /stream
# ---------------------------------------------------------------------------


@router.websocket("/stream")
async def stream_question(
    websocket: WebSocket,
    settings: Settings = Depends(get_settings),
) -> None:
    """Stream Claude's response over a WebSocket connection.

    Protocol:
    - Client sends: {"question": "...", "analysis_id": "..." | null}
    - Server sends: multiple {"chunk": "..."} messages as Claude generates text
    - Server sends: {"done": true} when complete
    - Server sends: {"error": "..."} if something goes wrong before closing

    The client should concatenate all "chunk" values to reconstruct the full answer.
    """
    await websocket.accept()
    log = logger.bind(action="stream_ws")

    # Re-use module-level singletons (WebSocket endpoints can't use Depends)
    global _rag_engine, _claude_service
    if _rag_engine is None:
        _rag_engine = RAGEngine(settings)
    if _claude_service is None:
        _claude_service = ClaudeService(settings)

    try:
        # Step 1: receive the question message
        raw_message = await websocket.receive_text()
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            await websocket.send_json({"error": "Invalid JSON in request message"})
            await websocket.close(code=1003)
            return

        question = payload.get("question", "").strip()
        if not question:
            await websocket.send_json({"error": "question field is required"})
            await websocket.close(code=1003)
            return

        analysis_id = payload.get("analysis_id") or state.latest_analysis_id
        log = log.bind(question=question[:80], analysis_id=analysis_id)

        if analysis_id is None or analysis_id not in state.analysis_store:
            await websocket.send_json(
                {
                    "error": (
                        "No analysis found. Upload a manifest.json via POST /analyze "
                        "first, or provide a valid analysis_id."
                    )
                }
            )
            await websocket.close(code=1011)
            return

        parsed_manifest = state.analysis_store[analysis_id]

        # Step 2: initialize RAG engine if needed
        if not _rag_engine._initialized:
            try:
                await _rag_engine.initialize(str(settings.database_url))
                await _rag_engine.index_manifest(parsed_manifest)
            except Exception as exc:
                log.warning("rag_init_failed_streaming_fallback", error=str(exc))
                # Continue — keyword fallback will handle retrieval

        # Step 3: retrieve context
        context: RetrievedContext = await _rag_engine.query(
            question=question,
            parsed_manifest=parsed_manifest,
            failing_context=parsed_manifest.failing_models or None,
        )

        manifest_summary = {
            "total_models": parsed_manifest.node_count,
            "failing_count": len(parsed_manifest.failing_models),
            "project_name": _extract_project_name(parsed_manifest),
        }

        # Step 4: stream Claude's response chunk by chunk
        async for chunk in _claude_service.stream_response(
            question=question,
            context=context,
            manifest_summary=manifest_summary,
        ):
            try:
                await websocket.send_json({"chunk": chunk})
            except WebSocketDisconnect:
                # Client disconnected mid-stream — common, not an error
                log.info("websocket_client_disconnected_during_stream")
                return

        # Step 5: signal completion
        try:
            await websocket.send_json({"done": True})
        except WebSocketDisconnect:
            # Client already gone by the time we finish — that's fine
            pass

        log.info(
            "stream_complete",
            relevant_models=len(context.relevant_nodes),
        )

    except WebSocketDisconnect:
        # Client disconnected before or during question handling — normal behavior
        log.info("websocket_disconnected")

    except RuntimeError as exc:
        # AuthenticationError from ClaudeService
        log.error("stream_auth_error", error=str(exc))
        try:
            await websocket.send_json({"error": str(exc)})
            await websocket.close(code=1011)
        except Exception:
            pass

    except Exception as exc:
        log.error("stream_unexpected_error", error=str(exc), exc_info=True)
        try:
            await websocket.send_json(
                {"error": f"Unexpected error: {type(exc).__name__}"}
            )
            await websocket.close(code=1011)
        except Exception:
            # If we can't even send the error, just let the connection drop
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_project_name(parsed_manifest) -> str:
    """Best-effort project name extraction from manifest metadata.

    The project name lives in different places depending on the dbt version
    and how the manifest was generated. We try the most common locations.
    """
    # ParsedManifest doesn't carry raw metadata, so we fall back to
    # inferring from model unique_ids (format: "model.{project}.{name}")
    for unique_id in parsed_manifest.models:
        parts = unique_id.split(".")
        if len(parts) >= 2:
            return parts[1]
    return "dbt_project"
