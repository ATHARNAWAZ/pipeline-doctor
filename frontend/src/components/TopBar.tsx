import { useRef, useCallback, useEffect, type ChangeEvent } from 'react';
import { Upload, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { usePipelineStore } from '../stores/pipelineStore';
import { useAnalysis } from '../hooks/useAnalysis';

export function TopBar() {
  const manifestInputRef = useRef<HTMLInputElement>(null);
  const runResultsInputRef = useRef<HTMLInputElement>(null);
  const selectedManifestRef = useRef<File | null>(null);
  // Track whether the run_results dialog has been opened and we're waiting
  const waitingForRunResultsRef = useRef(false);

  const { pipelineStatus } = usePipelineStore();
  const { uploadManifest, isUploading, error } = useAnalysis();

  const handleUploadClick = useCallback(() => {
    manifestInputRef.current?.click();
  }, []);

  const handleManifestChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      selectedManifestRef.current = file;
      waitingForRunResultsRef.current = true;

      // Prompt for optional run_results
      runResultsInputRef.current?.click();

      // Reset so same file can be re-selected
      e.target.value = '';
    },
    []
  );

  const handleRunResultsChange = useCallback(
    async (e: ChangeEvent<HTMLInputElement>) => {
      waitingForRunResultsRef.current = false;
      const runResultsFile = e.target.files?.[0] ?? undefined;
      const manifestFile = selectedManifestRef.current;

      if (!manifestFile) return;
      selectedManifestRef.current = null;

      await uploadManifest(manifestFile, runResultsFile);

      // Reset input
      e.target.value = '';
    },
    [uploadManifest]
  );

  // Detect when window regains focus after run_results dialog was opened.
  // If the user dismissed the dialog without selecting a file, we still
  // proceed with manifest-only upload.
  useEffect(() => {
    const handleWindowFocus = async () => {
      if (!waitingForRunResultsRef.current) return;

      // Give the input's onChange a chance to fire first
      setTimeout(async () => {
        if (!waitingForRunResultsRef.current) return; // onChange already handled it
        waitingForRunResultsRef.current = false;

        const manifestFile = selectedManifestRef.current;
        if (!manifestFile) return;
        selectedManifestRef.current = null;

        await uploadManifest(manifestFile, undefined);
      }, 300);
    };

    window.addEventListener('focus', handleWindowFocus);
    return () => {
      window.removeEventListener('focus', handleWindowFocus);
    };
  }, [uploadManifest]);

  return (
    <header
      className="flex h-12 shrink-0 items-center justify-between border-b border-border-default bg-canvas-subtle px-4"
      role="banner"
    >
      {/* Logo: green dot + app name in monospace */}
      <div className="flex items-center gap-2">
        <span
          className="text-success-fg text-base leading-none"
          aria-hidden="true"
        >
          ●
        </span>
        <span className="font-mono text-sm font-semibold text-fg-default tracking-tight">
          pipeline-doctor
        </span>
      </div>

      {/* Center: upload controls */}
      <div className="flex items-center gap-3">
        {error && (
          <span
            className="max-w-xs truncate font-mono text-[10px] text-danger-fg"
            role="alert"
            title={error}
          >
            {error}
          </span>
        )}

        {/* Ghost upload button: border-default, hover → border-accent */}
        <button
          type="button"
          onClick={handleUploadClick}
          disabled={isUploading}
          className={clsx(
            'flex items-center gap-1.5 border px-3 py-1 font-mono text-xs font-medium transition-colors',
            isUploading
              ? 'border-border-default text-fg-subtle cursor-not-allowed opacity-60'
              : 'border-border-default text-fg-muted hover:border-accent-fg hover:text-accent-fg'
          )}
          aria-label={isUploading ? 'Analyzing pipeline...' : 'Upload dbt manifest files'}
        >
          {isUploading ? (
            <Loader2 size={12} className="animate-spin" aria-hidden="true" />
          ) : (
            <Upload size={12} aria-hidden="true" />
          )}
          {isUploading ? 'analyzing...' : 'upload manifest'}
        </button>

        {/* Hidden file inputs */}
        <input
          ref={manifestInputRef}
          type="file"
          accept=".json,application/json"
          onChange={handleManifestChange}
          className="sr-only"
          aria-label="Select manifest.json file"
          tabIndex={-1}
        />
        <input
          ref={runResultsInputRef}
          type="file"
          accept=".json,application/json"
          onChange={handleRunResultsChange}
          className="sr-only"
          aria-label="Select run_results.json file (optional)"
          tabIndex={-1}
        />
      </div>

      {/* Right: status summary pills */}
      <div
        className="flex items-center gap-2"
        aria-label="Pipeline status summary"
        role="status"
      >
        {pipelineStatus ? (
          <>
            {/* Passing pill */}
            <div
              className="flex items-center gap-1 font-mono text-[10px] font-medium text-success-fg bg-success-emphasis/20 px-2 py-0.5"
              title={`${pipelineStatus.passing} passing models`}
              aria-label={`${pipelineStatus.passing} passing`}
            >
              <span aria-hidden="true">✓</span>
              <span aria-hidden="true">{pipelineStatus.passing}</span>
            </div>

            {/* Failing pill */}
            <div
              className="flex items-center gap-1 font-mono text-[10px] font-medium text-danger-fg bg-danger-emphasis/20 px-2 py-0.5"
              title={`${pipelineStatus.failing} failing models`}
              aria-label={`${pipelineStatus.failing} failing`}
            >
              <span aria-hidden="true">✗</span>
              <span aria-hidden="true">{pipelineStatus.failing}</span>
            </div>

            {/* Warnings pill — only when > 0 */}
            {pipelineStatus.warnings > 0 && (
              <div
                className="flex items-center gap-1 font-mono text-[10px] font-medium text-attention-fg bg-attention-emphasis/20 px-2 py-0.5"
                title={`${pipelineStatus.warnings} warnings`}
                aria-label={`${pipelineStatus.warnings} warnings`}
              >
                <span aria-hidden="true">⚠</span>
                <span aria-hidden="true">{pipelineStatus.warnings}</span>
              </div>
            )}

            <span className="font-mono text-[10px] text-fg-subtle pl-1 border-l border-border-default">
              {pipelineStatus.total_models} models
            </span>
          </>
        ) : (
          <span className="font-mono text-[10px] text-fg-subtle">
            no analysis loaded
          </span>
        )}
      </div>
    </header>
  );
}
