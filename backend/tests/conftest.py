"""
Shared pytest fixtures for pipeline-doctor backend tests.

These fixtures are scoped to the session where possible since parsing the
manifest is the expensive operation — no need to re-parse it for every test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.lineage_graph import LineageGraph
from app.services.manifest_parser import ManifestParser, ParsedManifest
from app.models.manifest import DbtRunResult

SAMPLE_MANIFEST = Path(__file__).parent.parent.parent / "sample_data" / "sample_manifest.json"
SAMPLE_RUN_RESULTS = Path(__file__).parent.parent.parent / "sample_data" / "sample_run_results.json"

_parser = ManifestParser()


@pytest.fixture(scope="session")
def parsed_manifest() -> ParsedManifest:
    """Parse the sample manifest once for the whole test session."""
    assert SAMPLE_MANIFEST.exists(), f"Sample manifest not found at {SAMPLE_MANIFEST}"
    return _parser.parse_manifest(manifest_path=SAMPLE_MANIFEST)


@pytest.fixture(scope="session")
def parsed_run_results() -> dict[str, DbtRunResult]:
    """Parse the sample run results once for the whole test session."""
    assert SAMPLE_RUN_RESULTS.exists(), (
        f"Sample run results not found at {SAMPLE_RUN_RESULTS}"
    )
    return _parser.parse_run_results(run_results_path=SAMPLE_RUN_RESULTS)


@pytest.fixture(scope="session")
def merged_manifest(
    parsed_manifest: ParsedManifest,
    parsed_run_results: dict[str, DbtRunResult],
) -> ParsedManifest:
    """Manifest with run results merged in, including failing_models populated."""
    return _parser.merge(parsed_manifest, parsed_run_results)


@pytest.fixture(scope="session")
def lineage_graph(merged_manifest: ParsedManifest) -> LineageGraph:
    """LineageGraph built from the merged manifest."""
    return LineageGraph.build_from_manifest(merged_manifest)
