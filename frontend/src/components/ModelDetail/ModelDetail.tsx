import { useCallback, type CSSProperties, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import clsx from 'clsx';
import { usePipelineStore } from '../../stores/pipelineStore';
import type { ModelStatus } from '../../types';

function getStatusBadgeClass(status: ModelStatus): string {
  switch (status) {
    case 'success':
      return 'text-success-fg border-success-fg/40 bg-success-fg/10';
    case 'error':
      return 'text-danger-fg border-danger-fg/40 bg-danger-fg/10';
    case 'warn':
      return 'text-attention-fg border-attention-fg/40 bg-attention-fg/10';
    case 'skipped':
      return 'text-fg-subtle border-border-default bg-canvas-inset';
    default:
      return 'text-fg-muted border-border-default bg-canvas-inset';
  }
}

function getStatusDot(status: ModelStatus): string {
  switch (status) {
    case 'success':
      return 'text-success-fg';
    case 'error':
      return 'text-danger-fg';
    case 'warn':
      return 'text-attention-fg';
    default:
      return 'text-fg-subtle';
  }
}

function extractLayer(filePath: string): string {
  const parts = filePath.split('/');
  if (parts.length >= 2) {
    return parts[parts.length - 2];
  }
  return '';
}

/** Section header: small caps style, muted, with a bottom rule */
function SectionHeader({ children }: { children: ReactNode }) {
  return (
    <h4 className="mb-2 border-b border-border-muted pb-1 font-mono text-[10px] font-semibold uppercase tracking-widest text-fg-subtle">
      {children}
    </h4>
  );
}

export function ModelDetail() {
  const { selectedModel, setSelectedModel, graphData } = usePipelineStore();

  const handleClose = useCallback(() => {
    setSelectedModel(null);
  }, [setSelectedModel]);

  /**
   * Navigate to a node by unique_id. Looks up the model in the graph data
   * and selects it, allowing upstream/downstream items to act as nav links.
   */
  const handleNavigateTo = useCallback(
    (uniqueId: string) => {
      if (!graphData) return;
      const node = graphData.nodes.find((n) => n.id === uniqueId);
      if (node) {
        // node.data is the DbtModel
        setSelectedModel(node.data as Parameters<typeof setSelectedModel>[0]);
      }
    },
    [graphData, setSelectedModel]
  );

  if (!selectedModel) return null;

  const layer = extractLayer(selectedModel.original_file_path);
  const statusDotClass = getStatusDot(selectedModel.status);
  const statusBadgeClass = getStatusBadgeClass(selectedModel.status);

  return (
    <div
      className="flex h-full flex-col overflow-hidden bg-canvas-default"
      role="complementary"
      aria-label={`Model details for ${selectedModel.name}`}
    >
      {/* Header */}
      <div className="shrink-0 border-b border-border-default bg-canvas-subtle px-4 py-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3
              className="font-mono text-sm font-semibold text-fg-default truncate"
              title={selectedModel.name}
            >
              {selectedModel.name}
            </h3>
            <p
              className="mt-0.5 font-mono text-[10px] text-fg-subtle truncate"
              title={selectedModel.original_file_path}
            >
              {layer && <span className="text-fg-muted">{layer}</span>}
              {layer && ' · '}
              {selectedModel.original_file_path || selectedModel.resource_type}
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="shrink-0 p-1 text-fg-muted hover:bg-canvas-inset hover:text-fg-default transition-colors"
            aria-label="Close model detail panel"
          >
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto">
        {/* Status block */}
        <section className="border-b border-border-default px-4 py-3">
          <div
            className={clsx(
              'inline-flex items-center gap-1.5 border px-2 py-1 font-mono text-xs font-semibold uppercase tracking-wide',
              statusBadgeClass
            )}
          >
            <span className={statusDotClass} aria-hidden="true">●</span>
            {selectedModel.status}
            {selectedModel.execution_time !== undefined &&
              selectedModel.execution_time > 0 && (
                <span className="font-normal opacity-75">
                  {selectedModel.execution_time.toFixed(1)}s
                </span>
              )}
          </div>

          {selectedModel.error_message && (
            <p className="mt-2 font-mono text-xs text-danger-fg bg-danger-fg/5 border border-danger-fg/20 px-2 py-1.5 break-words leading-relaxed">
              {selectedModel.error_message}
            </p>
          )}

          {selectedModel.description && (
            <p className="mt-2 text-xs text-fg-muted leading-relaxed">
              {selectedModel.description}
            </p>
          )}
        </section>

        {/* Tags */}
        {selectedModel.tags.length > 0 && (
          <section className="border-b border-border-default px-4 py-3">
            <SectionHeader>Tags</SectionHeader>
            <div className="flex flex-wrap gap-1">
              {selectedModel.tags.map((tag) => (
                <span
                  key={tag}
                  className="bg-canvas-inset px-1.5 py-0.5 font-mono text-[10px] text-fg-subtle border border-border-muted"
                >
                  {tag}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Upstream */}
        {selectedModel.upstream.length > 0 && (
          <section className="border-b border-border-default px-4 py-3">
            <SectionHeader>
              Upstream ({selectedModel.upstream.length})
            </SectionHeader>
            <ul className="space-y-0.5" aria-label="Upstream dependencies">
              {selectedModel.upstream.map((uid) => {
                const shortName = uid.split('.').pop() ?? uid;
                const canNavigate = graphData?.nodes.some((n) => n.id === uid);
                return (
                  <li key={uid} title={uid}>
                    <button
                      type="button"
                      onClick={() => canNavigate && handleNavigateTo(uid)}
                      disabled={!canNavigate}
                      className={clsx(
                        'flex w-full items-center gap-1.5 px-1 py-0.5 font-mono text-xs text-left transition-colors',
                        canNavigate
                          ? 'text-fg-muted hover:text-accent-fg hover:bg-canvas-subtle cursor-pointer'
                          : 'text-fg-subtle cursor-default'
                      )}
                      aria-label={`Navigate to upstream model ${shortName}`}
                    >
                      <span className="text-fg-subtle shrink-0" aria-hidden="true">
                        →
                      </span>
                      <span className="truncate">{shortName}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {/* Downstream */}
        {selectedModel.downstream.length > 0 && (
          <section className="border-b border-border-default px-4 py-3">
            <SectionHeader>
              Downstream ({selectedModel.downstream.length})
            </SectionHeader>
            <ul className="space-y-0.5" aria-label="Downstream dependents">
              {selectedModel.downstream.map((uid) => {
                const shortName = uid.split('.').pop() ?? uid;
                const isExposure = uid.startsWith('exposure.');
                const canNavigate = graphData?.nodes.some((n) => n.id === uid);
                return (
                  <li key={uid} title={uid}>
                    <button
                      type="button"
                      onClick={() => canNavigate && handleNavigateTo(uid)}
                      disabled={!canNavigate}
                      className={clsx(
                        'flex w-full items-center gap-1.5 px-1 py-0.5 font-mono text-xs text-left transition-colors',
                        canNavigate
                          ? 'text-fg-muted hover:text-accent-fg hover:bg-canvas-subtle cursor-pointer'
                          : 'text-fg-subtle cursor-default'
                      )}
                      aria-label={`Navigate to downstream ${isExposure ? 'exposure' : 'model'} ${shortName}`}
                    >
                      <span className="text-fg-subtle shrink-0" aria-hidden="true">
                        →
                      </span>
                      <span className="truncate">
                        {isExposure && (
                          <span className="text-accent-fg mr-1">exposure:</span>
                        )}
                        {shortName}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {/* Columns — two-column grid */}
        {Object.keys(selectedModel.columns).length > 0 && (
          <section className="border-b border-border-default px-4 py-3">
            <SectionHeader>
              Columns ({Object.keys(selectedModel.columns).length})
            </SectionHeader>
            <ul
              className="grid grid-cols-2 gap-x-4 gap-y-0.5"
              aria-label="Model columns"
            >
              {Object.entries(selectedModel.columns).map(([key, col]) => (
                <li key={key} className="flex items-baseline justify-between gap-1 min-w-0">
                  <span className="font-mono text-[11px] text-fg-default truncate">
                    {col.name}
                  </span>
                  {col.data_type && (
                    <span className="shrink-0 font-mono text-[9px] text-fg-subtle">
                      {col.data_type}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* SQL with line numbers */}
        {selectedModel.raw_code && (
          <section className="px-4 py-3" aria-label="SQL source code">
            <SectionHeader>SQL</SectionHeader>
            <SyntaxHighlighter
              language="sql"
              style={atomDark as Record<string, CSSProperties>}
              showLineNumbers
              lineNumberStyle={{
                fontSize: '9px',
                color: '#6e7681',
                minWidth: '2.5em',
                paddingRight: '1em',
                userSelect: 'none',
              }}
              customStyle={{
                fontSize: '11px',
                borderRadius: '0',
                border: '1px solid #30363d',
                background: '#010409',
                margin: 0,
                maxHeight: '320px',
                overflow: 'auto',
              }}
              wrapLongLines={false}
            >
              {selectedModel.raw_code}
            </SyntaxHighlighter>
          </section>
        )}

        {/* No content fallback */}
        {selectedModel.upstream.length === 0 &&
          selectedModel.downstream.length === 0 &&
          Object.keys(selectedModel.columns).length === 0 &&
          !selectedModel.raw_code && (
            <div className="px-4 py-6 text-center">
              <p className="font-mono text-xs text-fg-subtle">
                No additional metadata available for this node.
              </p>
            </div>
          )}
      </div>
    </div>
  );
}
