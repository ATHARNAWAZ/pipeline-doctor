export type ModelStatus = 'success' | 'error' | 'warn' | 'skipped' | 'unknown';

export interface DbtColumn {
  name: string;
  description?: string;
  data_type?: string;
}

export interface DbtModel {
  unique_id: string;
  name: string;
  resource_type: 'model' | 'source' | 'exposure';
  description: string;
  original_file_path: string;
  raw_code?: string;
  columns: Record<string, DbtColumn>;
  tags: string[];
  status: ModelStatus;
  error_message?: string;
  execution_time?: number;
  upstream: string[];
  downstream: string[];
}

export interface GraphNode {
  id: string;
  type: 'model' | 'source' | 'exposure';
  position: { x: number; y: number };
  data: DbtModel;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface FailingModelSummary {
  unique_id: string;
  name: string;
  error_message?: string | null;
  status: string;
}

export interface AnalysisResult {
  analysis_id: string;
  node_count: number;
  source_count: number;
  exposure_count: number;
  failing_models: FailingModelSummary[];
  lineage_summary: {
    total_nodes: number;
    total_edges: number;
  };
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  relevant_models?: string[];
  isStreaming?: boolean;
}

export interface PipelineStatus {
  total_models: number;
  passing: number;
  failing: number;
  warnings: number;
  health_pct?: number;
  last_run?: string;
  analysis_id?: string;
}

// Cytoscape-style graph format returned by GET /lineage
// The backend now emits richer node data that maps directly to DbtModel fields,
// plus a layer number used for column-based layout.
export interface CytoscapeNodeData {
  id: string;
  // label is the short model name — kept for backward compat
  label: string;
  resource_type: string;
  // Enriched fields added in Phase 7
  name: string;
  description: string;
  status: ModelStatus;
  error_message?: string | null;
  execution_time?: number | null;
  tags: string[];
  columns: Record<string, DbtColumn>;
  raw_code: string;
  original_file_path: string;
  layer: number;
  upstream: string[];
  downstream: string[];
}

export interface CytoscapeNode {
  data: CytoscapeNodeData;
  position: { x: number; y: number };
}

export interface CytoscapeEdgeData {
  id: string;
  source: string;
  target: string;
  dependency_type?: string;
}

export interface CytoscapeEdge {
  data: CytoscapeEdgeData;
}

export interface CytoscapeGraph {
  nodes: CytoscapeNode[];
  edges: CytoscapeEdge[];
}
