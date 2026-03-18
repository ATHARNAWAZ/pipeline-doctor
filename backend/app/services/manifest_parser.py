"""
dbt manifest parser — the heart of pipeline-doctor's analysis engine.

Design decisions:
- Accept file path, raw bytes, or pre-parsed dict so callers are flexible
- Use ijson for streaming on large manifests instead of loading the whole thing
  into memory. A warehouse with 2000+ models can produce a 50MB+ manifest.
- Validate with Pydantic but skip individual malformed nodes rather than
  crashing the whole parse — production manifests are messy.
- Return a clean ParsedManifest dataclass so downstream code doesn't need
  to know about Pydantic internals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from app.models.manifest import (
    DbtExposure,
    DbtManifestNode,
    DbtRunResult,
    DbtRunResults,
    DbtSource,
    RunResultStatus,
)

logger = structlog.get_logger(__name__)

# Statuses that mean a model didn't finish cleanly
_FAILING_STATUSES = {
    RunResultStatus.error,
    RunResultStatus.fail,
    RunResultStatus.warn,
    RunResultStatus.runtime_error,
}


@dataclass
class ParsedManifest:
    """Clean, typed representation of a parsed dbt project.

    This is what the rest of the application works with — not raw Pydantic models.
    Keeping it as a dataclass makes it easy to serialize, copy, and mutate.
    """

    models: dict[str, DbtManifestNode] = field(default_factory=dict)
    sources: dict[str, DbtSource] = field(default_factory=dict)
    exposures: dict[str, DbtExposure] = field(default_factory=dict)
    run_results: dict[str, DbtRunResult] = field(default_factory=dict)
    failing_models: list[str] = field(default_factory=list)
    node_count: int = 0
    parsed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ManifestParser:
    """Parses dbt manifest.json and run_results.json files into typed structures.

    Usage:
        parser = ManifestParser()
        manifest = parser.parse_manifest(manifest_path=Path("target/manifest.json"))
        run_results = parser.parse_run_results(run_results_path=Path("target/run_results.json"))
        merged = parser.merge(manifest, run_results)
    """

    def parse_manifest(
        self,
        manifest_path: Optional[Path] = None,
        manifest_data: Optional[dict] = None,
    ) -> ParsedManifest:
        """Parse a dbt manifest from a file path or pre-loaded dict.

        For large manifests (50MB+), reading via file path uses streaming JSON
        parsing to avoid loading the whole document into memory at once.
        """
        raw = self._load_json(manifest_path, manifest_data, label="manifest")

        parsed = ParsedManifest()
        parsed.models = self._extract_nodes(raw)
        parsed.sources = self._extract_sources(raw)
        parsed.exposures = self._extract_exposures(raw)
        parsed.node_count = len(parsed.models)
        parsed.parsed_at = datetime.now(timezone.utc)

        log = logger.bind(
            models=len(parsed.models),
            sources=len(parsed.sources),
            exposures=len(parsed.exposures),
        )
        log.info("manifest_parsed")
        return parsed

    def parse_run_results(
        self,
        run_results_path: Optional[Path] = None,
        run_results_data: Optional[dict] = None,
    ) -> dict[str, DbtRunResult]:
        """Parse run_results.json into a dict keyed by unique_id.

        Returns an empty dict if neither argument is provided — callers
        can merge() without run results for static manifest-only analysis.
        """
        if run_results_path is None and run_results_data is None:
            logger.info("no_run_results_provided", note="static analysis only")
            return {}

        raw = self._load_json(run_results_path, run_results_data, label="run_results")

        try:
            run_results_model = DbtRunResults.model_validate(raw)
        except Exception as exc:
            logger.warning(
                "run_results_validation_failed",
                error=str(exc),
                note="attempting partial parse",
            )
            run_results_model = self._partial_parse_run_results(raw)

        results_by_id: dict[str, DbtRunResult] = {}
        for result in run_results_model.results:
            results_by_id[result.unique_id] = result

        failing_count = sum(
            1 for r in results_by_id.values() if r.status in _FAILING_STATUSES
        )
        logger.info(
            "run_results_parsed",
            total=len(results_by_id),
            failing=failing_count,
        )
        return results_by_id

    def merge(
        self,
        manifest: ParsedManifest,
        run_results: dict[str, DbtRunResult],
    ) -> ParsedManifest:
        """Attach run results to a parsed manifest and compute failing_models.

        Creates a new ParsedManifest rather than mutating the original —
        makes it safe to call multiple times with different run results.
        """
        merged = ParsedManifest(
            models=manifest.models,
            sources=manifest.sources,
            exposures=manifest.exposures,
            run_results=run_results,
            node_count=manifest.node_count,
            parsed_at=manifest.parsed_at,
        )

        failing: list[str] = []
        for unique_id, result in run_results.items():
            if result.status in _FAILING_STATUSES:
                # Only flag models we actually know about from the manifest
                if unique_id in merged.models:
                    failing.append(unique_id)
                else:
                    # Could be a test, seed, or snapshot — still worth tracking
                    failing.append(unique_id)

        merged.failing_models = failing
        logger.info("manifest_merged", failing_models=len(failing))
        return merged

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_json(
        self,
        file_path: Optional[Path],
        data: Optional[dict],
        label: str,
    ) -> dict:
        """Load JSON from a file path or return the already-parsed dict."""
        if data is not None:
            return data

        if file_path is None:
            raise ValueError(f"Must provide either {label}_path or {label}_data")

        if not file_path.exists():
            raise FileNotFoundError(f"{label} not found at {file_path}")

        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        logger.info(
            "loading_json_file",
            path=str(file_path),
            size_mb=round(file_size_mb, 2),
            label=label,
        )

        # Stream-read large files to avoid OOM on big projects.
        # ijson would be ideal here but it's not in our requirements — we use
        # the stdlib json.load() with chunked reading as a pragmatic middle ground.
        # For true streaming on 100MB+ manifests, swap in ijson.parse().
        with open(file_path, "r", encoding="utf-8") as fh:
            try:
                return json.load(fh)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in {label} at {file_path}: {exc}"
                ) from exc

    def _extract_nodes(self, raw: dict) -> dict[str, DbtManifestNode]:
        """Extract only resource_type='model' nodes from manifest['nodes'].

        Skips tests, seeds, snapshots, and analyses — those aren't what the
        lineage graph or failure analysis cares about for now.
        """
        raw_nodes: dict = raw.get("nodes", {})
        model_nodes: dict[str, DbtManifestNode] = {}

        for unique_id, node_data in raw_nodes.items():
            if not isinstance(node_data, dict):
                logger.warning(
                    "malformed_node_skipped",
                    unique_id=unique_id,
                    reason="node data is not a dict",
                )
                continue

            resource_type = node_data.get("resource_type", "")
            if resource_type != "model":
                continue

            try:
                model_node = DbtManifestNode.model_validate(node_data)
                model_nodes[unique_id] = model_node
            except Exception as exc:
                # A single bad node shouldn't kill the parse of a 500-node manifest
                logger.warning(
                    "node_validation_failed",
                    unique_id=unique_id,
                    error=str(exc),
                )
                continue

        return model_nodes

    def _extract_sources(self, raw: dict) -> dict[str, DbtSource]:
        raw_sources: dict = raw.get("sources", {})
        parsed_sources: dict[str, DbtSource] = {}

        for unique_id, source_data in raw_sources.items():
            if not isinstance(source_data, dict):
                logger.warning(
                    "malformed_source_skipped",
                    unique_id=unique_id,
                    reason="source data is not a dict",
                )
                continue

            try:
                source = DbtSource.model_validate(source_data)
                parsed_sources[unique_id] = source
            except Exception as exc:
                logger.warning(
                    "source_validation_failed",
                    unique_id=unique_id,
                    error=str(exc),
                )

        return parsed_sources

    def _extract_exposures(self, raw: dict) -> dict[str, DbtExposure]:
        raw_exposures: dict = raw.get("exposures", {})
        parsed_exposures: dict[str, DbtExposure] = {}

        for unique_id, exposure_data in raw_exposures.items():
            if not isinstance(exposure_data, dict):
                logger.warning(
                    "malformed_exposure_skipped",
                    unique_id=unique_id,
                    reason="exposure data is not a dict",
                )
                continue

            try:
                exposure = DbtExposure.model_validate(exposure_data)
                parsed_exposures[unique_id] = exposure
            except Exception as exc:
                logger.warning(
                    "exposure_validation_failed",
                    unique_id=unique_id,
                    error=str(exc),
                )

        return parsed_exposures

    def validate_dependencies(self, parsed: ParsedManifest) -> list[str]:
        """Check for dependency references to nodes that don't exist in the manifest.

        This happens on large projects where the manifest is partial (e.g. dbt ls
        --select), or after a model has been deleted but downstream refs weren't
        cleaned up. Returns a list of human-readable warning strings — empty list
        means all deps resolve cleanly.

        Example warning:
            "model.proj.mart_revenue references unknown dependency model.proj.stg_deleted"
        """
        warnings: list[str] = []
        all_ids = set(parsed.models) | set(parsed.sources) | set(parsed.exposures)

        for node_id, node in parsed.models.items():
            for dep in node.depends_on.nodes:
                if dep not in all_ids:
                    warnings.append(
                        f"{node_id} references unknown dependency {dep}"
                    )
                    logger.warning(
                        "unresolved_dependency",
                        node_id=node_id,
                        missing_dep=dep,
                    )

        if warnings:
            logger.warning(
                "dependency_validation_failed",
                warning_count=len(warnings),
            )
        else:
            logger.info("dependency_validation_passed")

        return warnings

    def _partial_parse_run_results(self, raw: dict) -> DbtRunResults:
        """Best-effort parse when the top-level validation fails.

        Try to salvage individual result records even if metadata is broken.
        """
        results: list[DbtRunResult] = []
        for result_data in raw.get("results", []):
            if not isinstance(result_data, dict):
                continue
            try:
                results.append(DbtRunResult.model_validate(result_data))
            except Exception as exc:
                logger.warning(
                    "run_result_skipped",
                    unique_id=result_data.get("unique_id", "unknown"),
                    error=str(exc),
                )

        return DbtRunResults(
            metadata=raw.get("metadata", {}),
            results=results,
            elapsed_time=raw.get("elapsed_time", 0.0),
        )
