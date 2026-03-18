import { useCallback, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  type NodeTypes,
  type Node,
  type Edge,
  type NodeMouseHandler,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { usePipelineStore } from '../../stores/pipelineStore';
import { ModelNode, type ModelNodeData } from './ModelNode';
import type { DbtModel, ModelStatus } from '../../types';

const nodeTypes: NodeTypes = {
  modelNode: ModelNode,
};

function statusToMinimapColor(status: ModelStatus): string {
  switch (status) {
    case 'success':
      return '#3fb950';
    case 'error':
      return '#f85149';
    case 'warn':
      return '#d29922';
    case 'skipped':
      return '#6e7681';
    default:
      return '#30363d';
  }
}

export function DAGViewer() {
  const { graphData, selectedModel, setSelectedModel } = usePipelineStore();

  const nodes: Node[] = useMemo(() => {
    if (!graphData) return [];
    return graphData.nodes.map((gNode) => ({
      id: gNode.id,
      type: 'modelNode',
      position: gNode.position,
      data: gNode.data as unknown as ModelNodeData & Record<string, unknown>,
      selected: selectedModel?.unique_id === gNode.id,
    }));
  }, [graphData, selectedModel]);

  const edges: Edge[] = useMemo(() => {
    if (!graphData) return [];
    return graphData.edges.map((gEdge) => ({
      id: gEdge.id,
      source: gEdge.source,
      target: gEdge.target,
      style: { stroke: '#30363d', strokeWidth: 1.5 },
      animated: false,
    }));
  }, [graphData]);

  const handleNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      const model = node.data as unknown as DbtModel;
      setSelectedModel(model);
    },
    [setSelectedModel]
  );

  const handlePaneClick = useCallback(() => {
    setSelectedModel(null);
  }, [setSelectedModel]);

  if (!graphData) {
    return (
      <div
        className="flex h-full w-full flex-col items-center justify-center gap-4 bg-canvas-default"
        role="status"
        aria-label="No pipeline loaded"
      >
        <div className="text-4xl" aria-hidden="true">
          ⬡
        </div>
        <p className="font-mono text-sm text-fg-muted">
          Upload your manifest.json to begin
        </p>
        <p className="max-w-xs text-center text-xs text-fg-subtle">
          Use the Upload Manifest button in the top bar to load your dbt
          artifacts and visualize the pipeline DAG.
        </p>
      </div>
    );
  }

  return (
    <div
      className="h-full w-full bg-canvas-default"
      role="region"
      aria-label="Pipeline DAG visualization"
      aria-description="Interactive node graph of your dbt pipeline. Use Tab to move between model nodes and Enter or Space to select a node and view its details."
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
        style={{ background: '#0d1117' }}
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="#21262d"
        />
        <Controls
          position="bottom-left"
          style={{
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '6px',
          }}
        />
        <MiniMap
          position="bottom-right"
          style={{
            background: '#010409',
            border: '1px solid #30363d',
            borderRadius: '6px',
          }}
          maskColor="rgba(1, 4, 9, 0.7)"
          nodeColor={(node) => {
            const model = node.data as unknown as DbtModel;
            return statusToMinimapColor(model.status ?? 'unknown');
          }}
        />
      </ReactFlow>
    </div>
  );
}
