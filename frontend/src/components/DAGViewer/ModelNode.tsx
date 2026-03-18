import { memo, type KeyboardEvent } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import clsx from 'clsx';
import type { DbtModel, ModelStatus } from '../../types';

function getStatusLabel(status: ModelStatus): string {
  switch (status) {
    case 'success':
      return 'success';
    case 'error':
      return 'error';
    case 'warn':
      return 'warn';
    case 'skipped':
      return 'skipped';
    default:
      return 'unknown';
  }
}

function getStatusDotColor(status: ModelStatus): string {
  switch (status) {
    case 'success':
      return 'text-success-fg';
    case 'error':
      return 'text-danger-fg';
    case 'warn':
      return 'text-attention-fg';
    case 'skipped':
      return 'text-fg-subtle';
    default:
      return 'text-fg-subtle';
  }
}

/**
 * Returns border class + optional glow for the node outer wrapper.
 * Error nodes also get a left-border accent via inline style.
 */
function getNodeBorderClass(status: ModelStatus, selected: boolean): string {
  if (selected) {
    return 'border-accent-fg';
  }
  switch (status) {
    case 'success':
      return 'border-success-fg/50';
    case 'error':
      return 'border-danger-fg';
    case 'warn':
      return 'border-attention-fg';
    case 'skipped':
      return 'border-border-default';
    default:
      return 'border-border-default';
  }
}

function getNodeBoxShadow(status: ModelStatus, selected: boolean): string {
  if (selected) return '0 0 0 2px #58a6ff';
  if (status === 'error') return '0 0 8px rgba(248, 81, 73, 0.3)';
  if (status === 'warn') return '0 0 6px rgba(210, 153, 34, 0.25)';
  return 'none';
}

function getResourceTypeBadge(
  resourceType: 'model' | 'source' | 'exposure'
): { label: string; className: string } {
  switch (resourceType) {
    case 'source':
      return {
        label: 'source',
        // purple tint
        className: 'bg-[#2d1f3d] text-[#d2a8ff]',
      };
    case 'exposure':
      return {
        label: 'exposure',
        // amber tint
        className: 'bg-[#3d2d1f] text-[#d29922]',
      };
    default:
      return {
        label: 'model',
        // blue tint
        className: 'bg-[#1f2d3d] text-[#79c0ff]',
      };
  }
}

export interface ModelNodeData extends DbtModel {
  [key: string]: unknown;
}

export const ModelNode = memo(function ModelNode({
  data,
  selected,
}: NodeProps) {
  const model = data as ModelNodeData;
  const badge = getResourceTypeBadge(model.resource_type);
  const borderClass = getNodeBorderClass(model.status, selected ?? false);
  const dotColorClass = getStatusDotColor(model.status);
  const statusLabel = getStatusLabel(model.status);
  const boxShadow = getNodeBoxShadow(model.status, selected ?? false);

  // Error nodes get a 4px left accent border
  const leftAccent =
    model.status === 'error'
      ? { borderLeftWidth: '4px', borderLeftColor: '#f85149' }
      : {};

  // Keyboard activation: React Flow handles click events on the node wrapper,
  // but does not synthesize click from Enter/Space on keyboard focus.
  // We dispatch a click event so the onNodeClick handler in DAGViewer fires.
  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      e.currentTarget.click();
    }
  };

  return (
    <div
      className={clsx(
        'relative border bg-canvas-subtle transition-all duration-150',
        'w-[200px]',
        borderClass
      )}
      style={{
        boxShadow,
        fontSize: '11px',
        ...leftAccent,
      }}
      role="button"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      aria-label={`${model.resource_type} ${model.name}: ${statusLabel}`}
      aria-pressed={selected ?? false}
    >
      {/* React Flow connection handles — hidden via CSS, kept for graph logic */}
      <Handle
        type="target"
        position={Position.Left}
        style={{ opacity: 0, pointerEvents: 'none', width: 4, height: 4 }}
      />

      <div className="px-2.5 py-2">
        {/* Row 1: resource type badge (right-aligned) */}
        <div className="mb-1 flex items-center justify-between gap-1">
          <span className="truncate font-mono text-[10px] text-fg-subtle uppercase tracking-widest opacity-60">
            {/* intentionally empty left — badge is right side */}
          </span>
          <span
            className={clsx(
              'shrink-0 px-1.5 py-0.5 font-mono text-[9px] font-medium uppercase tracking-wide',
              badge.className
            )}
          >
            {badge.label}
          </span>
        </div>

        {/* Row 2: model name */}
        <div
          className="font-mono font-semibold text-fg-default leading-snug break-all"
          style={{ fontSize: '11px' }}
          title={model.name}
        >
          {model.name}
        </div>

        {/* Row 3: status dot + execution time */}
        <div
          className={clsx(
            'mt-1.5 flex items-center gap-1 font-mono',
            dotColorClass
          )}
          style={{ fontSize: '10px' }}
        >
          <span aria-hidden="true">●</span>
          <span>
            {statusLabel}
            {model.execution_time !== undefined &&
              model.execution_time > 0 &&
              `  ${model.execution_time.toFixed(1)}s`}
          </span>
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        style={{ opacity: 0, pointerEvents: 'none', width: 4, height: 4 }}
      />
    </div>
  );
});
