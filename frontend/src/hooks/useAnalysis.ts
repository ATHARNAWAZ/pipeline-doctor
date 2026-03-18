import { useState, useCallback } from 'react';
import axios from 'axios';
import { usePipelineStore } from '../stores/pipelineStore';
import type {
  AnalysisResult,
  CytoscapeGraph,
  GraphData,
  GraphNode,
  GraphEdge,
  DbtModel,
  ModelStatus,
} from '../types';

function resourceTypeToNodeType(
  resourceType: string
): 'model' | 'source' | 'exposure' {
  if (resourceType === 'source') return 'source';
  if (resourceType === 'exposure') return 'exposure';
  return 'model';
}

function buildGraphData(cytoscape: CytoscapeGraph): GraphData {
  // The backend now embeds full DbtModel-equivalent fields directly in each
  // node's data object (name, description, status, tags, columns, raw_code,
  // original_file_path, upstream, downstream).  We map them directly rather
  // than reconstructing from edges, which was the previous fallback approach.
  const nodes: GraphNode[] = cytoscape.nodes.map((cyNode) => {
    const resourceType = resourceTypeToNodeType(cyNode.data.resource_type);
    const model: DbtModel = {
      unique_id: cyNode.data.id,
      // Prefer the explicit name field; fall back to label for older backends
      name: cyNode.data.name ?? cyNode.data.label,
      resource_type: resourceType,
      description: cyNode.data.description ?? '',
      original_file_path: cyNode.data.original_file_path ?? '',
      raw_code: cyNode.data.raw_code ?? '',
      columns: cyNode.data.columns ?? {},
      tags: cyNode.data.tags ?? [],
      // Status from run results is now embedded in node data by the backend
      status: (cyNode.data.status as ModelStatus) ?? 'unknown',
      error_message: cyNode.data.error_message ?? undefined,
      execution_time: cyNode.data.execution_time ?? undefined,
      // upstream/downstream are pre-computed by the backend from the graph
      upstream: cyNode.data.upstream ?? [],
      downstream: cyNode.data.downstream ?? [],
    };

    return {
      id: cyNode.data.id,
      type: resourceType,
      position: { x: cyNode.position.x, y: cyNode.position.y },
      data: model,
    };
  });

  const edges: GraphEdge[] = cytoscape.edges.map((cyEdge) => ({
    id: cyEdge.data.id,
    source: cyEdge.data.source,
    target: cyEdge.data.target,
    type: cyEdge.data.dependency_type,
  }));

  return { nodes, edges };
}

export function useAnalysis() {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    setGraphData,
    setPipelineStatus,
    setAnalysisResult,
    setAnalysisId,
    setAnalyzing,
  } = usePipelineStore();

  const uploadManifest = useCallback(
    async (manifestFile: File, runResultsFile?: File): Promise<void> => {
      setIsUploading(true);
      setAnalyzing(true);
      setError(null);

      try {
        const formData = new FormData();
        formData.append('manifest', manifestFile);
        if (runResultsFile) {
          formData.append('run_results', runResultsFile);
        }

        const analysisResponse = await axios.post<AnalysisResult>(
          '/api/analyze',
          formData,
          {
            headers: { 'Content-Type': 'multipart/form-data' },
          }
        );

        const result = analysisResponse.data;
        setAnalysisResult(result);
        setAnalysisId(result.analysis_id);

        // Fetch the full graph for visualization
        const graphResponse = await axios.get<CytoscapeGraph>('/api/lineage');
        const graphData = buildGraphData(graphResponse.data);

        // Node status and error_message are embedded in node data by the backend
        // (from run results annotated onto the lineage graph).  We do a second pass
        // here using the AnalysisResult's failing_models list as an authoritative
        // override so that status is always consistent with what the analysis
        // reported, even if the graph endpoint was served from a different replica.
        const failingIds = new Set(result.failing_models.map((m) => m.unique_id));
        const statusMap: Record<string, ModelStatus> = {};
        for (const fm of result.failing_models) {
          const st = fm.status as string;
          if (st === 'warn') {
            statusMap[fm.unique_id] = 'warn';
          } else if (st === 'skipped') {
            statusMap[fm.unique_id] = 'skipped';
          } else {
            statusMap[fm.unique_id] = 'error';
          }
        }

        const errorMessageMap: Record<string, string> = {};
        for (const fm of result.failing_models) {
          if (fm.error_message) {
            errorMessageMap[fm.unique_id] = fm.error_message;
          }
        }

        const annotatedNodes = graphData.nodes.map((node) => {
          // If the node is in the failing list, the AnalysisResult is authoritative.
          // Otherwise, keep the status already embedded in node.data by buildGraphData.
          const isFailing = failingIds.has(node.id);
          if (!isFailing) return node;

          return {
            ...node,
            data: {
              ...node.data,
              status: statusMap[node.id] ?? 'error',
              error_message: errorMessageMap[node.id] ?? node.data.error_message,
            },
          };
        });

        setGraphData({ nodes: annotatedNodes, edges: graphData.edges });

        // Fetch pipeline status
        const statusResponse = await axios.get('/api/analyze/status');
        setPipelineStatus(statusResponse.data);
      } catch (err: unknown) {
        if (axios.isAxiosError(err)) {
          const detail =
            (err.response?.data as { detail?: string } | undefined)?.detail ??
            err.message;
          setError(`Upload failed: ${detail}`);
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('An unknown error occurred during upload.');
        }
      } finally {
        setIsUploading(false);
        setAnalyzing(false);
      }
    },
    [setGraphData, setPipelineStatus, setAnalysisResult, setAnalysisId, setAnalyzing]
  );

  return { uploadManifest, isUploading, error };
}
