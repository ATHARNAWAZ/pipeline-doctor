"""
NetworkX-based DAG for dbt model lineage analysis.

The graph contains both model nodes and source/exposure nodes so that
blast-radius calculations can propagate all the way from a failing model
to the downstream dashboards that will break.

Node IDs are dbt unique_ids (e.g. "model.fintech_pipeline.mart_customer_ltv").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import networkx as nx
import structlog

from app.models.manifest import DbtManifestNode
from app.services.manifest_parser import ParsedManifest

logger = structlog.get_logger(__name__)


@dataclass
class FailureImpact:
    """How badly does a single failing node hurt the rest of the pipeline?"""

    failing_node: str
    affected_downstream: list[str] = field(default_factory=list)
    # Simple score: number of downstream models blocked by this failure.
    # In a real scoring model you'd weight by mart vs staging, exposure count, etc.
    estimated_impact_score: float = 0.0


class LineageGraph:
    """Immutable DAG built from a ParsedManifest.

    Build once, query many times. All methods are read-only after construction.
    """

    def __init__(self, graph: nx.DiGraph) -> None:
        self._graph = graph

    @classmethod
    def build_from_manifest(cls, parsed_manifest: ParsedManifest) -> "LineageGraph":
        """Build the directed graph from a parsed manifest.

        Edge direction: parent -> child (upstream -> downstream), matching
        the direction data flows. So stg_transactions -> int_customer_transactions.

        We include sources and exposures as nodes so the full picture is visible —
        a failure in stg_transactions should show exposure.revenue_dashboard as
        an affected downstream consumer.

        Run result data from parsed_manifest.run_results is annotated onto each
        node so the frontend can colour nodes by their execution status without
        needing a separate API call.
        """
        g = nx.DiGraph()

        # Add all model nodes with their full metadata as node attributes
        for unique_id, node in parsed_manifest.models.items():
            g.add_node(
                unique_id,
                name=node.name,
                resource_type=node.resource_type,
                description=node.description,
                original_file_path=node.original_file_path,
                tags=node.tags,
                columns={k: v.model_dump() for k, v in node.columns.items()},
                raw_code=node.raw_code or "",
                # Run result fields — populated below after graph is assembled
                status="unknown",
                error_message=None,
                execution_time=None,
                node_data=node,
            )

        # Add source nodes (they're upstream of models)
        for unique_id, source in parsed_manifest.sources.items():
            g.add_node(
                unique_id,
                name=source.name,
                resource_type="source",
                description=source.description,
                original_file_path="",
                tags=source.tags,
                columns={k: v.model_dump() for k, v in source.columns.items()},
                raw_code="",
                status="unknown",
                error_message=None,
                execution_time=None,
                node_data=source,
            )

        # Add exposure nodes (they're downstream consumers)
        for unique_id, exposure in parsed_manifest.exposures.items():
            g.add_node(
                unique_id,
                name=exposure.name,
                resource_type="exposure",
                description=exposure.description,
                original_file_path="",
                tags=exposure.tags,
                columns={},
                raw_code="",
                status="unknown",
                error_message=None,
                execution_time=None,
                node_data=exposure,
            )

        # Wire up edges from depends_on — each model declares its parents
        for unique_id, node in parsed_manifest.models.items():
            for parent_id in node.depends_on.nodes:
                if parent_id not in g:
                    # Orphaned reference — probably a cross-project ref or deleted node
                    logger.debug(
                        "lineage_parent_not_found",
                        child=unique_id,
                        missing_parent=parent_id,
                    )
                    g.add_node(
                        parent_id,
                        name=parent_id,
                        resource_type="unknown",
                        description="",
                        original_file_path="",
                        tags=[],
                        columns={},
                        raw_code="",
                        status="unknown",
                        error_message=None,
                        execution_time=None,
                    )

                g.add_edge(
                    parent_id,
                    unique_id,
                    dependency_type="ref",
                )

        # Wire up exposure -> their upstream models
        for unique_id, exposure in parsed_manifest.exposures.items():
            for parent_id in exposure.depends_on.nodes:
                if parent_id not in g:
                    g.add_node(
                        parent_id,
                        name=parent_id,
                        resource_type="unknown",
                        description="",
                        original_file_path="",
                        tags=[],
                        columns={},
                        raw_code="",
                        status="unknown",
                        error_message=None,
                        execution_time=None,
                    )
                g.add_edge(parent_id, unique_id, dependency_type="exposure_ref")

        # Annotate run result data onto each node that has a result.
        # Nodes with no run result keep status="unknown" (sources, exposures, skipped).
        for unique_id, run_result in parsed_manifest.run_results.items():
            if unique_id in g:
                g.nodes[unique_id]["status"] = run_result.status.value
                g.nodes[unique_id]["execution_time"] = run_result.execution_time
                # error_message is only meaningful on failures — keep it None on success
                if run_result.message and run_result.status.value not in ("success",):
                    g.nodes[unique_id]["error_message"] = run_result.message

        # Detect and log cycles — dbt shouldn't produce them but corrupt manifests can
        try:
            cycles = list(nx.simple_cycles(g))
            if cycles:
                logger.warning(
                    "lineage_cycles_detected",
                    cycle_count=len(cycles),
                    first_cycle=cycles[0],
                )
        except nx.NetworkXError as exc:
            logger.warning("cycle_detection_failed", error=str(exc))

        instance = cls(graph=g)
        logger.info(
            "lineage_graph_built",
            nodes=g.number_of_nodes(),
            edges=g.number_of_edges(),
        )
        return instance

    def get_upstream(self, node_id: str, depth: int = 999) -> list[str]:
        """Return all ancestor node IDs up to `depth` hops away.

        Uses BFS on the reversed graph so we walk toward sources.
        Returns an empty list for unknown nodes rather than raising.
        """
        if node_id not in self._graph:
            logger.warning("upstream_query_unknown_node", node_id=node_id)
            return []

        reversed_g = self._graph.reverse(copy=False)
        ancestors = list(
            nx.bfs_tree(reversed_g, node_id, depth_limit=depth).nodes()
        )
        # bfs_tree includes the root node itself — remove it
        ancestors = [n for n in ancestors if n != node_id]
        return ancestors

    def get_downstream(self, node_id: str, depth: int = 999) -> list[str]:
        """Return all descendant node IDs up to `depth` hops away."""
        if node_id not in self._graph:
            logger.warning("downstream_query_unknown_node", node_id=node_id)
            return []

        descendants = list(
            nx.bfs_tree(self._graph, node_id, depth_limit=depth).nodes()
        )
        descendants = [n for n in descendants if n != node_id]
        return descendants

    def get_failure_blast_radius(
        self, failing_node_ids: list[str]
    ) -> dict[str, FailureImpact]:
        """For each failing node, calculate which downstream nodes are blocked.

        The blast radius is the union of all downstream nodes. The impact score
        is a simple count of affected downstream model nodes (exposures count
        double since they represent real user-facing breakage).
        """
        blast_radius: dict[str, FailureImpact] = {}

        for failing_id in failing_node_ids:
            downstream = self.get_downstream(failing_id)

            # Weight by node type: exposures are user-facing so they hurt more
            score = 0.0
            for node_id in downstream:
                node_attrs = self._graph.nodes.get(node_id, {})
                resource_type = node_attrs.get("resource_type", "model")
                if resource_type == "exposure":
                    score += 2.0  # broken dashboard = immediate business impact
                else:
                    score += 1.0

            blast_radius[failing_id] = FailureImpact(
                failing_node=failing_id,
                affected_downstream=downstream,
                estimated_impact_score=score,
            )

        return blast_radius

    def get_layer(self, node_id: str) -> int:
        """Return the DAG layer number for a node (0 = source, higher = further downstream).

        The layer is the length of the longest path from any root node (in-degree 0)
        to this node.  Using the longest path rather than the shortest means that a
        node whose furthest upstream source is 3 hops away lands in layer 3, giving
        a layout that separates staging from intermediate from mart cleanly.

        Returns 0 for unknown nodes and for root nodes themselves.
        """
        if node_id not in self._graph:
            logger.warning("get_layer_unknown_node", node_id=node_id)
            return 0

        # DAG longest-path from any source to node_id.
        # nx.dag_longest_path_length works on the whole graph; we want the longest
        # incoming path only.  Build a subgraph of ancestors + node and measure.
        try:
            reversed_g = self._graph.reverse(copy=False)
            ancestor_ids = set(nx.bfs_tree(reversed_g, node_id).nodes())
            subgraph = self._graph.subgraph(ancestor_ids)
            # longest path length from any root to node_id in that subgraph
            layer = nx.dag_longest_path_length(subgraph)
        except (nx.NetworkXError, nx.NetworkXUnfeasible):
            # Cyclic subgraph (shouldn't happen for valid dbt manifest)
            layer = 0

        return layer

    def get_nodes_by_layer(self) -> dict[int, list[str]]:
        """Group all node IDs by their DAG layer number.

        Returns a dict mapping layer -> sorted list of node_ids.
        Layer 0 = source nodes (no upstream dependencies).
        Higher layers = nodes progressively further downstream.

        Used by the frontend for column-based layout — all nodes in the same
        layer are stacked in the same vertical column.
        """
        layers: dict[int, list[str]] = {}
        for node_id in self._graph.nodes():
            layer = self.get_layer(node_id)
            layers.setdefault(layer, []).append(node_id)

        # Sort each layer's node list for deterministic rendering order
        for layer in layers:
            layers[layer].sort()

        return layers

    def get_critical_path(self, source_id: str, target_id: str) -> list[str]:
        """Find the shortest path between two nodes.

        Returns an empty list if no path exists (disconnected graph or
        wrong direction — remember edges flow parent -> child).
        """
        if source_id not in self._graph:
            logger.warning("critical_path_source_not_found", source_id=source_id)
            return []
        if target_id not in self._graph:
            logger.warning("critical_path_target_not_found", target_id=target_id)
            return []

        try:
            path = nx.shortest_path(self._graph, source=source_id, target=target_id)
            return path
        except nx.NetworkXNoPath:
            logger.debug(
                "no_path_between_nodes",
                source_id=source_id,
                target_id=target_id,
            )
            return []
        except nx.NodeNotFound as exc:
            logger.warning("critical_path_node_not_found", error=str(exc))
            return []

    def to_cytoscape_format(self) -> dict:
        """Export the graph in the format consumed by the React Flow frontend.

        Node format:
        {
            "data": {
                "id": "model.fintech_pipeline.stg_transactions",
                "label": "stg_transactions",          # kept for legacy compat
                "resource_type": "model",
                "name": "stg_transactions",
                "description": "...",
                "status": "success",
                "error_message": null,
                "execution_time": 2.779,
                "tags": [...],
                "columns": {...},
                "raw_code": "...",
                "original_file_path": "...",
                "layer": 1,
                "upstream": [...],
                "downstream": [...],
            },
            "position": {"x": 280, "y": 120}
        }

        Edge format:
        {
            "data": {
                "id": "edge_src_tgt",
                "source": "source.fintech_pipeline.raw.raw_transactions",
                "target": "model.fintech_pipeline.stg_transactions",
                "dependency_type": "ref"
            }
        }

        Positions are computed from layer number (x = layer * 280) and the
        node's vertical index within its layer (y = layer_index * 120).
        The frontend may override positions with its own layout engine.
        """
        cyto_nodes = []
        cyto_edges = []

        # Group nodes by layer for position computation.
        # get_nodes_by_layer() already sorts each layer deterministically.
        nodes_by_layer = self.get_nodes_by_layer()

        x_spacing = 280
        y_spacing = 120

        # Build a node_id -> (layer, layer_index) lookup for O(1) position access
        node_layer_index: dict[str, tuple[int, int]] = {}
        for layer, node_ids in nodes_by_layer.items():
            for layer_idx, node_id in enumerate(node_ids):
                node_layer_index[node_id] = (layer, layer_idx)

        for node_id in self._graph.nodes():
            attrs = self._graph.nodes[node_id]
            layer, layer_idx = node_layer_index.get(node_id, (0, 0))

            resource_type = attrs.get("resource_type", "unknown")
            # Normalise resource_type to the three values the frontend understands.
            # Anything that isn't source or exposure is treated as a model node.
            if resource_type not in ("source", "exposure"):
                resource_type = "model"

            cyto_nodes.append({
                "data": {
                    "id": node_id,
                    # label kept for backward-compat with the CytoscapeNodeData type
                    "label": attrs.get("name", node_id.split(".")[-1]),
                    "resource_type": resource_type,
                    "name": attrs.get("name", node_id.split(".")[-1]),
                    "description": attrs.get("description", ""),
                    "status": attrs.get("status", "unknown"),
                    "error_message": attrs.get("error_message"),
                    "execution_time": attrs.get("execution_time"),
                    "tags": attrs.get("tags", []),
                    "columns": attrs.get("columns", {}),
                    "raw_code": attrs.get("raw_code", ""),
                    "original_file_path": attrs.get("original_file_path", ""),
                    "layer": layer,
                    "upstream": list(self._graph.predecessors(node_id)),
                    "downstream": list(self._graph.successors(node_id)),
                },
                "position": {
                    "x": layer * x_spacing,
                    "y": layer_idx * y_spacing,
                },
            })

        for edge_idx, (source, target, edge_data) in enumerate(
            self._graph.edges(data=True)
        ):
            cyto_edges.append({
                "data": {
                    "id": f"edge_{source.split('.')[-1]}_{target.split('.')[-1]}",
                    "source": source,
                    "target": target,
                    "dependency_type": edge_data.get("dependency_type", "ref"),
                }
            })

        return {"nodes": cyto_nodes, "edges": cyto_edges}

    def to_networkx_graph(self) -> nx.DiGraph:
        """Return the raw NetworkX graph for callers that need direct graph access."""
        return self._graph

    def get_node_metadata(self, node_id: str) -> Optional[dict]:
        """Return the stored attributes for a node, or None if not found."""
        if node_id not in self._graph:
            return None
        return dict(self._graph.nodes[node_id])
