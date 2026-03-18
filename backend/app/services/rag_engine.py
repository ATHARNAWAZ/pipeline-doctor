"""
RAG engine — the semantic retrieval layer that feeds Claude relevant context.

Design decisions:
- pgvector as the vector store so embeddings survive restarts and can be
  shared across multiple API worker processes without re-indexing.
- Dual embedding strategy: OpenAI ada-002 when an API key is present,
  BAAI/bge-small-en-v1.5 via HuggingFace otherwise. The HuggingFace model is
  small enough to run comfortably on CPU and produces competitive embeddings
  for technical text (SQL, model names, column descriptions).
- One document per dbt model — not per-chunk. dbt models are already small
  enough that splitting them loses the SQL→column relationship. A single
  dense document lets the retriever understand the whole model at once.
- The context string passed to Claude is purpose-built: it's not raw retrieved
  text, it's a structured summary that highlights the failure path and relevant
  SQL. Claude reads this, not the raw embeddings.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import Settings
from app.models.manifest import DbtManifestNode, DbtRunResult
from app.services.lineage_graph import LineageGraph
from app.services.manifest_parser import ParsedManifest

logger = structlog.get_logger(__name__)

# How many semantically similar models to pull per query.
# 5 is enough context for a focused failure explanation without overwhelming Claude.
_DEFAULT_TOP_K = 5

# LlamaIndex imports are deferred to initialization time so the module can be
# imported without crashing if llama-index isn't installed yet (e.g. in tests).
_llama_index_available = False


@dataclass
class IndexingResult:
    models_indexed: int = 0
    sources_indexed: int = 0
    total_chunks: int = 0
    embedding_model: str = ""


@dataclass
class RetrievedContext:
    relevant_nodes: list[str] = field(default_factory=list)
    context_string: str = ""
    # Average similarity score from the vector store (0–1 cosine similarity).
    # Useful for the confidence field in the /ask response.
    retrieval_score: float = 0.0


class RAGEngine:
    """Semantic retrieval engine backed by pgvector.

    Initialize once at startup via `await engine.initialize(db_url)`, then call
    `index_manifest()` after each manifest upload to keep embeddings current.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._initialized = False
        self._embedding_model_name = ""
        self._vector_store = None
        self._index = None
        self._embed_model = None
        self._engine: Optional[AsyncEngine] = None

    async def initialize(self, db_url: str) -> None:
        """Bootstrap pgvector extension and the embedding model.

        Converts a standard postgres:// URL to the asyncpg variant expected by
        SQLAlchemy's async engine. Called once at application startup.
        """
        log = logger.bind(action="rag_initialize")

        # Convert sync postgres:// URL to async postgresql+asyncpg://
        async_url = db_url.replace("postgresql://", "postgresql+asyncpg://").replace(
            "postgres://", "postgresql+asyncpg://"
        )

        self._engine = create_async_engine(async_url, echo=False)

        # Ensure the pgvector extension exists — harmless if already present.
        # We do this here so the rest of the code can assume vector ops work.
        try:
            async with self._engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            log.info("pgvector_extension_ready")
        except Exception as exc:
            # If pgvector isn't installed on the DB server, log loudly but
            # don't crash — the app still works without RAG (degraded mode).
            log.error(
                "pgvector_extension_failed",
                error=str(exc),
                note="RAG features will be unavailable",
            )
            return

        # Pick the embedding model based on available credentials.
        # OpenAI ada-002 is slightly better for English text but costs money and
        # requires a network call. The HuggingFace fallback works fully offline.
        self._embed_model = await asyncio.get_event_loop().run_in_executor(
            None, self._load_embedding_model
        )

        await self._setup_vector_store(db_url)
        self._initialized = True
        log.info("rag_engine_ready", embedding_model=self._embedding_model_name)

    def _load_embedding_model(self):
        """Load the appropriate embedding model synchronously.

        Runs in a thread executor to avoid blocking the event loop during
        model download or warm-up (HuggingFace can take a few seconds first time).
        """
        if self._settings.openai_api_key:
            try:
                from llama_index.embeddings.openai import OpenAIEmbedding

                model = OpenAIEmbedding(
                    api_key=self._settings.openai_api_key,
                    model="text-embedding-ada-002",
                )
                self._embedding_model_name = "openai/text-embedding-ada-002"
                logger.info("embedding_model_loaded", model=self._embedding_model_name)
                return model
            except Exception as exc:
                logger.warning(
                    "openai_embedding_load_failed",
                    error=str(exc),
                    fallback="huggingface",
                )

        # Fall back to a local model that runs entirely on CPU.
        # BAAI/bge-small-en-v1.5 is 33M parameters, ~130MB on disk,
        # and produces 384-dim embeddings. Fast enough for 500-model manifests.
        try:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding

            model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
            self._embedding_model_name = "huggingface/BAAI/bge-small-en-v1.5"
            logger.info("embedding_model_loaded", model=self._embedding_model_name)
            return model
        except Exception as exc:
            logger.error(
                "huggingface_embedding_load_failed",
                error=str(exc),
                note="all embedding options exhausted",
            )
            raise

    async def _setup_vector_store(self, db_url: str) -> None:
        """Create the LlamaIndex pgvector store and wire it to the index.

        Uses a synchronous psycopg2-compatible URL for the LlamaIndex PGVectorStore
        since that library hasn't fully migrated to asyncpg yet.
        """
        from llama_index.core import Settings as LlamaSettings, VectorStoreIndex
        from llama_index.vector_stores.postgres import PGVectorStore

        # LlamaIndex's PGVectorStore needs a sync connection URL
        sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

        try:
            self._vector_store = PGVectorStore.from_params(
                connection_string=sync_url,
                table_name="dbt_model_chunks",
                # Dimension must match the chosen embedding model:
                # ada-002 → 1536, bge-small-en-v1.5 → 384
                embed_dim=1536 if "openai" in self._embedding_model_name else 384,
                hybrid_search=False,
            )
            LlamaSettings.embed_model = self._embed_model
            self._index = VectorStoreIndex.from_vector_store(
                vector_store=self._vector_store
            )
            logger.info("vector_store_ready", table="dbt_model_chunks")
        except Exception as exc:
            logger.error("vector_store_setup_failed", error=str(exc))
            raise

    async def index_manifest(self, parsed_manifest: ParsedManifest) -> IndexingResult:
        """Embed all dbt model nodes and upsert them into pgvector.

        Called after every manifest upload so the index stays current.
        This is a full re-index — we delete existing docs for this project
        and re-insert. For large projects (500+ models) this takes ~30–60s
        with a local embedding model; ~5s with OpenAI.
        """
        if not self._initialized or self._index is None:
            logger.warning(
                "index_manifest_skipped",
                reason="RAG engine not initialized — running without semantic search",
            )
            return IndexingResult(embedding_model="none")

        log = logger.bind(
            action="index_manifest",
            model_count=len(parsed_manifest.models),
        )

        from llama_index.core import Document

        documents: list[Document] = []
        for node_id, node in parsed_manifest.models.items():
            doc = self._node_to_document(node_id, node)
            documents.append(doc)

        # Source nodes get lighter-weight documents (no SQL, just name + schema)
        for source_id, source in parsed_manifest.sources.items():
            doc = Document(
                doc_id=source_id,
                text=(
                    f"SOURCE: {source.source_name}.{source.name}\n"
                    f"Description: {source.description or 'No description'}\n"
                    f"Schema: {source.schema_ or 'unknown'}\n"
                    f"Columns: {', '.join(source.columns.keys()) or 'unknown'}\n"
                    f"Tags: {', '.join(source.tags) or 'none'}"
                ),
                metadata={
                    "node_id": source_id,
                    "name": source.name,
                    "resource_type": "source",
                    "source_name": source.source_name,
                },
            )
            documents.append(doc)

        # Run embedding in a thread executor — it's CPU/network bound
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._embed_and_store_documents, documents
            )
        except Exception as exc:
            log.error("indexing_failed", error=str(exc))
            raise

        result = IndexingResult(
            models_indexed=len(parsed_manifest.models),
            sources_indexed=len(parsed_manifest.sources),
            total_chunks=len(documents),
            embedding_model=self._embedding_model_name,
        )
        log.info(
            "indexing_complete",
            models=result.models_indexed,
            sources=result.sources_indexed,
            embedding_model=result.embedding_model,
        )
        return result

    def _embed_and_store_documents(self, documents) -> None:
        """Synchronous document insertion — called from a thread executor."""
        from llama_index.core import VectorStoreIndex, Settings as LlamaSettings

        # Rebuild index with all documents. LlamaIndex's PGVectorStore handles
        # upserts by doc_id so re-running this is safe.
        VectorStoreIndex.from_documents(
            documents,
            vector_store=self._vector_store,
            embed_model=LlamaSettings.embed_model,
            show_progress=False,
        )

    async def query(
        self,
        question: str,
        parsed_manifest: ParsedManifest,
        failing_context: Optional[list[str]] = None,
    ) -> RetrievedContext:
        """Semantic search: find the dbt models most relevant to this question.

        Returns a RetrievedContext with the raw node IDs and a pre-formatted
        context string ready to drop into a Claude prompt.

        If the RAG engine isn't initialized (no pgvector), falls back to
        keyword matching on model names — degraded but functional.
        """
        if not self._initialized or self._index is None:
            return self._fallback_keyword_query(question, parsed_manifest, failing_context)

        log = logger.bind(action="rag_query", question=question[:80])

        try:
            relevant_docs = await asyncio.get_event_loop().run_in_executor(
                None, self._sync_vector_search, question, _DEFAULT_TOP_K
            )
        except Exception as exc:
            log.warning(
                "vector_search_failed",
                error=str(exc),
                fallback="keyword_search",
            )
            return self._fallback_keyword_query(question, parsed_manifest, failing_context)

        # Always include failing models in context regardless of similarity score —
        # the question is usually about them even if the text doesn't match well
        relevant_node_ids: list[str] = []
        scores: list[float] = []

        for scored_source in relevant_docs:
            node_id = scored_source.node.metadata.get("node_id", "")
            if node_id:
                relevant_node_ids.append(node_id)
                scores.append(scored_source.score or 0.0)

        # Inject failing models that weren't picked up by similarity search
        if failing_context:
            for failing_id in failing_context:
                if failing_id not in relevant_node_ids:
                    relevant_node_ids.append(failing_id)

        # Resolve node IDs to actual model objects
        lineage_graph = LineageGraph.build_from_manifest(parsed_manifest)
        relevant_nodes: list[DbtManifestNode] = []
        for node_id in relevant_node_ids:
            node = parsed_manifest.models.get(node_id)
            if node:
                relevant_nodes.append(node)

        context_str = self._build_context_string(
            relevant_nodes=relevant_nodes,
            run_results=parsed_manifest.run_results,
            lineage_graph=lineage_graph,
        )

        avg_score = sum(scores) / len(scores) if scores else 0.5
        log.info(
            "rag_query_complete",
            relevant_models=len(relevant_node_ids),
            avg_score=round(avg_score, 3),
        )

        return RetrievedContext(
            relevant_nodes=relevant_node_ids,
            context_string=context_str,
            retrieval_score=avg_score,
        )

    def _sync_vector_search(self, question: str, top_k: int):
        """Synchronous vector similarity search — called from a thread executor."""
        retriever = self._index.as_retriever(similarity_top_k=top_k)
        return retriever.retrieve(question)

    def _fallback_keyword_query(
        self,
        question: str,
        parsed_manifest: ParsedManifest,
        failing_context: Optional[list[str]] = None,
    ) -> RetrievedContext:
        """Keyword fallback when pgvector is unavailable.

        Matches model names and descriptions against words in the question.
        Not as good as vector search but keeps the tool usable without a DB.
        """
        question_lower = question.lower()
        question_words = set(question_lower.split())

        scored: list[tuple[float, str, DbtManifestNode]] = []
        for node_id, node in parsed_manifest.models.items():
            score = 0.0
            # Direct name match is a strong signal
            if node.name.lower() in question_lower:
                score += 3.0
            # Tag matches help narrow down domain
            for tag in node.tags:
                if tag.lower() in question_lower:
                    score += 1.0
            # Word overlap on description
            desc_words = set(node.description.lower().split())
            overlap = len(desc_words & question_words)
            score += overlap * 0.5
            if score > 0:
                scored.append((score, node_id, node))

        # Failing models are always relevant
        if failing_context:
            for failing_id in failing_context:
                node = parsed_manifest.models.get(failing_id)
                if node:
                    scored.append((10.0, failing_id, node))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:_DEFAULT_TOP_K]

        relevant_nodes = [t[2] for t in top]
        relevant_ids = [t[1] for t in top]

        lineage_graph = LineageGraph.build_from_manifest(parsed_manifest)
        context_str = self._build_context_string(
            relevant_nodes=relevant_nodes,
            run_results=parsed_manifest.run_results,
            lineage_graph=lineage_graph,
        )

        return RetrievedContext(
            relevant_nodes=relevant_ids,
            context_string=context_str,
            retrieval_score=0.0,  # Keyword search doesn't produce meaningful scores
        )

    def _node_to_document(self, node_id: str, node: DbtManifestNode):
        """Convert a dbt model node to a LlamaIndex Document.

        Packs everything the embedding model needs to produce a useful vector:
        name, SQL, column names/descriptions, tags, and materialization type.
        The format is intentionally verbose — embedding models benefit from
        repeated signal (the model name appears multiple times).
        """
        from llama_index.core import Document

        # Build a dense text representation. Order matters for embedding models:
        # most important information (name, SQL) goes first.
        sql = node.compiled_code or node.raw_code or "-- SQL not available"
        columns_text = ""
        if node.columns:
            col_lines = []
            for col_name, col in node.columns.items():
                line = f"  - {col_name}"
                if col.data_type:
                    line += f" ({col.data_type})"
                if col.description:
                    line += f": {col.description}"
                col_lines.append(line)
            columns_text = "\n".join(col_lines)

        materialization = node.config.materialized or "unknown"
        tags_str = ", ".join(node.tags + node.config.tags) or "none"
        upstream_ids = node.depends_on.nodes

        text_parts = [
            f"MODEL: {node.name}",
            f"Unique ID: {node_id}",
            f"Description: {node.description or 'No description provided'}",
            f"Materialization: {materialization}",
            f"Tags: {tags_str}",
            f"Upstream dependencies: {', '.join(upstream_ids) or 'none (source model)'}",
        ]

        if columns_text:
            text_parts.append(f"Columns:\n{columns_text}")

        text_parts.append(f"SQL:\n{sql}")

        return Document(
            doc_id=node_id,
            text="\n\n".join(text_parts),
            metadata={
                "node_id": node_id,
                "name": node.name,
                "resource_type": node.resource_type,
                "materialized": materialization,
                "tags": tags_str,
            },
        )

    def _build_context_string(
        self,
        relevant_nodes: list[DbtManifestNode],
        run_results: dict[str, DbtRunResult],
        lineage_graph: LineageGraph,
    ) -> str:
        """Build the context block that Claude reads.

        This is the single most important formatting decision in the RAG pipeline.
        Claude reads this text and uses it to reason about the failure. It needs
        to be:
        - Dense: include SQL, columns, errors in one place
        - Structured: consistent format so Claude doesn't have to hunt for info
        - Prioritized: failure context comes before non-failing models

        We deliberately cap SQL at 80 lines to stay within context windows while
        still providing enough for Claude to identify the offending clause.
        """
        sections: list[str] = []

        # Sort: failing models first so they appear at the top of context
        failing_ids = {uid for uid in run_results if run_results[uid].message}
        ordered_nodes = sorted(
            relevant_nodes,
            key=lambda n: (0 if n.unique_id in failing_ids else 1, n.name),
        )

        for node in ordered_nodes:
            run_result = run_results.get(node.unique_id)
            status_line = ""
            error_block = ""

            if run_result:
                status_line = f"Status: {run_result.status.value.upper()}"
                if run_result.message:
                    error_block = f"\n**ERROR MESSAGE:**\n```\n{run_result.message}\n```"

            # Upstream lineage — helps Claude trace the failure chain
            upstream = lineage_graph.get_upstream(node.unique_id, depth=2)
            upstream_names = []
            for uid in upstream[:5]:  # cap at 5 to avoid giant context blocks
                attrs = lineage_graph.get_node_metadata(uid)
                if attrs:
                    upstream_names.append(attrs.get("name", uid))

            downstream = lineage_graph.get_downstream(node.unique_id, depth=1)
            downstream_names = []
            for uid in downstream[:5]:
                attrs = lineage_graph.get_node_metadata(uid)
                if attrs:
                    downstream_names.append(attrs.get("name", uid))

            # Truncate SQL to keep context manageable
            sql = node.compiled_code or node.raw_code or ""
            sql_lines = sql.splitlines()
            if len(sql_lines) > 80:
                sql = "\n".join(sql_lines[:80]) + "\n... (truncated)"

            col_summary = ""
            if node.columns:
                col_parts = []
                for col_name, col in list(node.columns.items())[:20]:  # cap columns too
                    part = col_name
                    if col.data_type:
                        part += f":{col.data_type}"
                    col_parts.append(part)
                col_summary = f"\nColumns: {', '.join(col_parts)}"

            section_parts = [
                f"### {node.name}",
                f"ID: {node.unique_id}",
            ]
            if status_line:
                section_parts.append(status_line)
            if node.description:
                section_parts.append(f"Description: {node.description}")
            if upstream_names:
                section_parts.append(f"Upstream (feeds this): {' → '.join(upstream_names)} → {node.name}")
            if downstream_names:
                section_parts.append(f"Downstream (depends on this): {node.name} → {' → '.join(downstream_names)}")
            if col_summary:
                section_parts.append(col_summary)
            if error_block:
                section_parts.append(error_block)
            if sql:
                section_parts.append(f"\nSQL:\n```sql\n{sql}\n```")

            sections.append("\n".join(section_parts))

        if not sections:
            return "No relevant model context found."

        header = f"## dbt Project Context\n{len(sections)} relevant model(s) retrieved:\n"
        return header + "\n\n---\n\n".join(sections)
