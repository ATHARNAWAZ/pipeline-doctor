import { Component, type ReactNode, type ErrorInfo } from 'react';
import { TopBar } from './components/TopBar';
import { DAGViewer } from './components/DAGViewer/DAGViewer';
import { ChatPanel } from './components/ChatPanel/ChatPanel';
import { ModelDetail } from './components/ModelDetail/ModelDetail';
import { usePipelineStore } from './stores/pipelineStore';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(_error: Error, _info: ErrorInfo): void {
    // In production, ship to an error reporting service (e.g. Sentry)
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

function MainLayout() {
  const { selectedModel } = usePipelineStore();

  return (
    // Full-viewport column: TopBar + main area
    <div
      className="bg-canvas-default text-fg-default"
      style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
    >
      {/* TopBar: 48px fixed height, never grows/shrinks */}
      <div style={{ flexShrink: 0, height: '48px' }}>
        <TopBar />
      </div>

      {/* Main row: DAGViewer (60%) + right panel (40%) */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'row' }}>
        {/* Left: DAG viewer — exactly 60% */}
        <main
          style={{ flex: '0 0 60%', overflow: 'hidden', position: 'relative' }}
          aria-label="Pipeline DAG"
        >
          <ErrorBoundary
            fallback={
              <div className="flex h-full items-center justify-center">
                <p className="font-mono text-sm text-danger-fg">
                  DAG visualization failed to load.
                </p>
              </div>
            }
          >
            <DAGViewer />
          </ErrorBoundary>
        </main>

        {/* Right panel — exactly 40%, column */}
        <aside
          style={{
            flex: '0 0 40%',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            borderLeft: '1px solid #30363d',
          }}
          aria-label="Analysis panel"
        >
          {selectedModel ? (
            // Model selected: ModelDetail takes 60% of right panel, Chat takes 40%
            <>
              <div style={{ flex: '0 0 60%', overflow: 'hidden' }}>
                <ErrorBoundary
                  fallback={
                    <div className="flex h-full items-center justify-center p-4">
                      <p className="font-mono text-xs text-danger-fg">
                        Model detail panel error.
                      </p>
                    </div>
                  }
                >
                  <ModelDetail />
                </ErrorBoundary>
              </div>
              <div
                style={{ flex: 1, overflow: 'hidden', borderTop: '1px solid #30363d' }}
              >
                <ErrorBoundary
                  fallback={
                    <div className="flex h-full items-center justify-center p-4">
                      <p className="font-mono text-xs text-danger-fg">
                        Chat panel error.
                      </p>
                    </div>
                  }
                >
                  <ChatPanel />
                </ErrorBoundary>
              </div>
            </>
          ) : (
            // No model selected: full chat panel
            <ErrorBoundary
              fallback={
                <div className="flex h-full items-center justify-center p-4">
                  <p className="font-mono text-xs text-danger-fg">
                    Chat panel error.
                  </p>
                </div>
              }
            >
              <ChatPanel />
            </ErrorBoundary>
          )}
        </aside>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary
      fallback={
        <div className="flex h-screen items-center justify-center bg-canvas-default">
          <div className="text-center">
            <p className="font-mono text-sm text-danger-fg">
              Pipeline Doctor encountered a fatal error.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-4 font-mono text-xs text-accent-fg underline"
            >
              Reload application
            </button>
          </div>
        </div>
      }
    >
      <MainLayout />
    </ErrorBoundary>
  );
}
