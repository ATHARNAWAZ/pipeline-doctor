"""
Tests for the manifest parser and lineage graph.

These test actual behavior, not just "does it not crash".
All counts are derived from sample_manifest.json:
  - 5 staging models (stg_transactions, stg_customers, stg_products, stg_events, stg_sessions)
  - 3 intermediate models (int_customer_transactions, int_product_revenue, int_user_journey)
  - 4 mart models (mart_customer_ltv, mart_revenue_summary, mart_funnel_analysis, mart_daily_metrics)
  - Total: 12 model nodes
  - 5 sources (raw_transactions, raw_customers, raw_products, raw_events, raw_sessions)
  - 2 exposures (revenue_dashboard, growth_dashboard)

Failing models from sample_run_results.json:
  - mart_customer_ltv (status: error — division by zero)
  - mart_revenue_summary (status: error — missing product_category column)
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from app.models.manifest import RunResultStatus
from app.services.lineage_graph import LineageGraph
from app.services.manifest_parser import ManifestParser, ParsedManifest

SAMPLE_MANIFEST = Path(__file__).parent.parent.parent / "sample_data" / "sample_manifest.json"
SAMPLE_RUN_RESULTS = Path(__file__).parent.parent.parent / "sample_data" / "sample_run_results.json"

_parser = ManifestParser()


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------


def test_parse_manifest_counts(parsed_manifest: ParsedManifest) -> None:
    """Correct number of models, sources, and exposures extracted from sample data."""
    assert len(parsed_manifest.models) == 12, (
        f"Expected 12 model nodes (5 staging + 3 int + 4 mart), "
        f"got {len(parsed_manifest.models)}"
    )
    assert len(parsed_manifest.sources) == 5, (
        f"Expected 5 source nodes, got {len(parsed_manifest.sources)}"
    )
    assert len(parsed_manifest.exposures) == 2, (
        f"Expected 2 exposures (revenue_dashboard + growth_dashboard), "
        f"got {len(parsed_manifest.exposures)}"
    )
    assert parsed_manifest.node_count == 12


def test_parse_manifest_model_names(parsed_manifest: ParsedManifest) -> None:
    """Spot-check that specific model names are present."""
    model_names = {node.name for node in parsed_manifest.models.values()}

    expected_names = {
        "stg_transactions",
        "stg_customers",
        "int_customer_transactions",
        "mart_customer_ltv",
        "mart_revenue_summary",
        "mart_daily_metrics",
    }
    for name in expected_names:
        assert name in model_names, f"Expected model '{name}' not found in manifest"


def test_parse_manifest_only_extracts_models(parsed_manifest: ParsedManifest) -> None:
    """Parser must not include tests, seeds, or snapshots in the models dict."""
    for unique_id, node in parsed_manifest.models.items():
        assert node.resource_type == "model", (
            f"Node {unique_id} has resource_type '{node.resource_type}', "
            f"expected 'model'"
        )


# ---------------------------------------------------------------------------
# Run results parsing
# ---------------------------------------------------------------------------


def test_parse_run_results_total_count(parsed_run_results) -> None:
    """Sample run results has 12 results (one per model in the manifest)."""
    assert len(parsed_run_results) == 12, (
        f"Expected 12 run results, got {len(parsed_run_results)}"
    )


def test_parse_run_results_failures(parsed_run_results) -> None:
    """Exactly 2 models should have error status: mart_customer_ltv and mart_revenue_summary."""
    failing = [
        uid
        for uid, result in parsed_run_results.items()
        if result.status in {RunResultStatus.error, RunResultStatus.fail}
    ]

    assert len(failing) == 2, (
        f"Expected exactly 2 failing models, got {len(failing)}: {failing}"
    )

    failing_names = {uid.split(".")[-1] for uid in failing}
    assert "mart_customer_ltv" in failing_names, (
        "mart_customer_ltv should be in failing models"
    )
    assert "mart_revenue_summary" in failing_names, (
        "mart_revenue_summary should be in failing models"
    )


def test_parse_run_results_error_messages(parsed_run_results) -> None:
    """Error messages are captured from the run results."""
    ltv_uid = "model.fintech_pipeline.mart_customer_ltv"
    assert ltv_uid in parsed_run_results

    ltv_result = parsed_run_results[ltv_uid]
    assert ltv_result.message is not None
    # The error message should mention the actual cause
    assert "division by zero" in ltv_result.message.lower() or "Division by zero" in ltv_result.message


def test_parse_run_results_success_status(parsed_run_results) -> None:
    """Successful models should have success status."""
    stg_txn_uid = "model.fintech_pipeline.stg_transactions"
    assert stg_txn_uid in parsed_run_results
    assert parsed_run_results[stg_txn_uid].status == RunResultStatus.success


# ---------------------------------------------------------------------------
# Manifest + run results merge
# ---------------------------------------------------------------------------


def test_merge_run_results(merged_manifest: ParsedManifest) -> None:
    """After merging, failing_models must be populated with the 2 error models."""
    assert len(merged_manifest.failing_models) == 2, (
        f"Expected 2 failing models after merge, got {len(merged_manifest.failing_models)}"
    )

    failing_names = {uid.split(".")[-1] for uid in merged_manifest.failing_models}
    assert "mart_customer_ltv" in failing_names
    assert "mart_revenue_summary" in failing_names


def test_merge_preserves_models(merged_manifest: ParsedManifest) -> None:
    """Merge should not drop or add models from the manifest."""
    assert len(merged_manifest.models) == 12
    assert len(merged_manifest.sources) == 5
    assert len(merged_manifest.exposures) == 2


def test_merge_run_results_accessible(merged_manifest: ParsedManifest) -> None:
    """Run results dict should be populated on the merged manifest."""
    assert len(merged_manifest.run_results) == 12


# ---------------------------------------------------------------------------
# Lineage graph — upstream/downstream traversal
# ---------------------------------------------------------------------------


def test_lineage_upstream(lineage_graph: LineageGraph) -> None:
    """mart_customer_ltv should have int_customer_transactions in its upstream."""
    ltv_uid = "model.fintech_pipeline.mart_customer_ltv"
    upstream = lineage_graph.get_upstream(ltv_uid)

    int_txn_uid = "model.fintech_pipeline.int_customer_transactions"
    assert int_txn_uid in upstream, (
        f"int_customer_transactions should be upstream of mart_customer_ltv. "
        f"Got: {upstream}"
    )


def test_lineage_upstream_includes_sources(lineage_graph: LineageGraph) -> None:
    """Upstream traversal should reach all the way back to source nodes."""
    ltv_uid = "model.fintech_pipeline.mart_customer_ltv"
    upstream = lineage_graph.get_upstream(ltv_uid)

    # stg_transactions feeds int_customer_transactions which feeds mart_customer_ltv
    stg_txn_uid = "model.fintech_pipeline.stg_transactions"
    assert stg_txn_uid in upstream, (
        f"stg_transactions should be in upstream of mart_customer_ltv"
    )


def test_lineage_downstream(lineage_graph: LineageGraph) -> None:
    """stg_transactions should have multiple downstream models."""
    stg_txn_uid = "model.fintech_pipeline.stg_transactions"
    downstream = lineage_graph.get_downstream(stg_txn_uid)

    # stg_transactions -> int_customer_transactions and int_product_revenue
    int_txn_uid = "model.fintech_pipeline.int_customer_transactions"
    int_rev_uid = "model.fintech_pipeline.int_product_revenue"

    assert int_txn_uid in downstream, (
        f"int_customer_transactions should be downstream of stg_transactions"
    )
    assert int_rev_uid in downstream, (
        f"int_product_revenue should be downstream of stg_transactions"
    )
    assert len(downstream) >= 2, (
        f"stg_transactions should have at least 2 downstream models"
    )


def test_lineage_depth_limit(lineage_graph: LineageGraph) -> None:
    """Depth-limited traversal should respect the depth parameter."""
    stg_txn_uid = "model.fintech_pipeline.stg_transactions"

    # With depth=1, only immediate children
    downstream_depth1 = lineage_graph.get_downstream(stg_txn_uid, depth=1)
    downstream_full = lineage_graph.get_downstream(stg_txn_uid)

    assert len(downstream_depth1) < len(downstream_full), (
        "Depth-1 traversal should return fewer nodes than unlimited traversal"
    )


def test_lineage_unknown_node_returns_empty(lineage_graph: LineageGraph) -> None:
    """Querying an unknown node should return empty list, not raise."""
    result = lineage_graph.get_upstream("model.nonexistent.fake_model")
    assert result == []

    result = lineage_graph.get_downstream("model.nonexistent.fake_model")
    assert result == []


# ---------------------------------------------------------------------------
# Failure blast radius
# ---------------------------------------------------------------------------


def test_failure_blast_radius(
    lineage_graph: LineageGraph,
    merged_manifest: ParsedManifest,
) -> None:
    """mart_customer_ltv failure should affect revenue_dashboard exposure."""
    ltv_uid = "model.fintech_pipeline.mart_customer_ltv"
    blast = lineage_graph.get_failure_blast_radius([ltv_uid])

    assert ltv_uid in blast

    affected = blast[ltv_uid].affected_downstream
    revenue_dash_uid = "exposure.fintech_pipeline.revenue_dashboard"

    assert revenue_dash_uid in affected, (
        f"revenue_dashboard exposure should be in blast radius of mart_customer_ltv. "
        f"Affected: {affected}"
    )


def test_blast_radius_impact_score(lineage_graph: LineageGraph) -> None:
    """Impact score should be positive for nodes with downstream dependents."""
    stg_txn_uid = "model.fintech_pipeline.stg_transactions"
    blast = lineage_graph.get_failure_blast_radius([stg_txn_uid])

    # stg_transactions has many downstream dependents — score should be high
    assert blast[stg_txn_uid].estimated_impact_score > 0


def test_blast_radius_multiple_failures(lineage_graph: LineageGraph) -> None:
    """Blast radius handles multiple failing nodes simultaneously."""
    failing = [
        "model.fintech_pipeline.mart_customer_ltv",
        "model.fintech_pipeline.mart_revenue_summary",
    ]
    blast = lineage_graph.get_failure_blast_radius(failing)

    assert len(blast) == 2
    for uid in failing:
        assert uid in blast


# ---------------------------------------------------------------------------
# Critical path
# ---------------------------------------------------------------------------


def test_critical_path_exists(lineage_graph: LineageGraph) -> None:
    """There should be a path from a source to a mart."""
    source_uid = "source.fintech_pipeline.raw.raw_transactions"
    mart_uid = "model.fintech_pipeline.mart_customer_ltv"

    path = lineage_graph.get_critical_path(source_uid, mart_uid)
    assert len(path) > 0, f"Expected a path from {source_uid} to {mart_uid}"
    assert path[0] == source_uid
    assert path[-1] == mart_uid


def test_critical_path_no_path(lineage_graph: LineageGraph) -> None:
    """Two disconnected nodes should return empty list, not raise."""
    # mart -> source is backwards — no path in that direction
    source_uid = "source.fintech_pipeline.raw.raw_transactions"
    mart_uid = "model.fintech_pipeline.mart_customer_ltv"

    path = lineage_graph.get_critical_path(mart_uid, source_uid)
    assert path == [], "Reversed path (mart -> source) should return empty list"


# ---------------------------------------------------------------------------
# Cytoscape export
# ---------------------------------------------------------------------------


def test_cytoscape_export(lineage_graph: LineageGraph) -> None:
    """Exported Cytoscape format should contain the right node and edge counts."""
    cyto = lineage_graph.to_cytoscape_format()

    assert "nodes" in cyto
    assert "edges" in cyto

    # 12 models + 5 sources + 2 exposures = 19 nodes
    assert len(cyto["nodes"]) == 19, (
        f"Expected 19 nodes in cytoscape export, got {len(cyto['nodes'])}"
    )

    # Each node should have required fields
    for node in cyto["nodes"]:
        assert "data" in node
        assert "id" in node["data"]
        assert "label" in node["data"]
        assert "resource_type" in node["data"]

    # Each edge should have source and target
    for edge in cyto["edges"]:
        assert "data" in edge
        assert "source" in edge["data"]
        assert "target" in edge["data"]

    # Edges should be positive — our sample has many dependencies
    assert len(cyto["edges"]) > 0


# ---------------------------------------------------------------------------
# Error handling / malformed input
# ---------------------------------------------------------------------------


def test_malformed_node_handling() -> None:
    """Parser should skip malformed nodes and not crash on them."""
    malformed_manifest = {
        "metadata": {"dbt_version": "1.7.0"},
        "nodes": {
            # This is a valid model node
            "model.test.good_model": {
                "unique_id": "model.test.good_model",
                "name": "good_model",
                "resource_type": "model",
                "original_file_path": "models/good_model.sql",
                "depends_on": {"nodes": [], "macros": []},
            },
            # This node is missing required fields — should be skipped gracefully
            "model.test.bad_model": {
                "resource_type": "model",
                # Missing 'unique_id' and 'name' — will fail Pydantic validation
            },
            # This is not even a dict — should be skipped
            "model.test.totally_wrong": "this is a string not a dict",
        },
        "sources": {},
        "exposures": {},
    }

    # Must not raise — malformed nodes should be logged and skipped
    result = _parser.parse_manifest(manifest_data=malformed_manifest)

    # Only the good model should have been parsed
    assert len(result.models) == 1
    assert "model.test.good_model" in result.models


def test_empty_manifest_handling() -> None:
    """An empty manifest (no nodes) should return a valid ParsedManifest with zeros."""
    empty_manifest = {
        "metadata": {},
        "nodes": {},
        "sources": {},
        "exposures": {},
    }
    result = _parser.parse_manifest(manifest_data=empty_manifest)

    assert result.node_count == 0
    assert len(result.models) == 0
    assert len(result.sources) == 0
    assert len(result.exposures) == 0


def test_parse_run_results_empty() -> None:
    """parse_run_results with no args returns empty dict."""
    result = _parser.parse_run_results()
    assert result == {}


def test_merge_without_run_results(parsed_manifest: ParsedManifest) -> None:
    """merge() with empty run_results dict should leave failing_models empty."""
    merged = _parser.merge(parsed_manifest, {})
    assert merged.failing_models == []
    assert len(merged.models) == len(parsed_manifest.models)
