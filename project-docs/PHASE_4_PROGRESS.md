# Phase 4 — Frontend Complete

**Status: COMPLETE**
**Date: 2026-03-18**
**Framework: React 18 + TypeScript (strict) + Vite 5**

## What was built

### Architecture
- Zustand stores for pipeline state and chat state — single source of truth
- Custom hooks encapsulate all async logic (upload, WebSocket streaming)
- All API calls route through Vite proxy `/api/*` → backend `/*`
- WebSocket connects to `ws://localhost:8000/query/stream` with exponential backoff reconnection

### Files created

| File | Purpose |
|------|---------|
| `src/types/index.ts` | All TypeScript types (zero `any`) |
| `src/stores/pipelineStore.ts` | Zustand store: graph, selectedModel, status, analysisId |
| `src/stores/chatStore.ts` | Zustand store: messages, streaming state |
| `src/hooks/useAnalysis.ts` | Upload manifest + run_results, fetch graph, annotate statuses |
| `src/hooks/useStreamingChat.ts` | WebSocket chat with reconnection + streaming accumulation |
| `src/components/DAGViewer/ModelNode.tsx` | Custom React Flow node with status colors and glow |
| `src/components/DAGViewer/DAGViewer.tsx` | Full DAG with minimap, controls, dot background |
| `src/components/ChatPanel/ChatMessage.tsx` | Markdown + syntax highlighting, streaming cursor |
| `src/components/ChatPanel/ChatPanel.tsx` | Chat UI with auto-scroll, disabled-during-stream input |
| `src/components/ModelDetail/ModelDetail.tsx` | Model detail panel with SQL highlighting |
| `src/components/TopBar.tsx` | Upload button, status badges, two-file picker flow |
| `src/App.tsx` | Layout, error boundaries, model-selected split view |
| `src/main.tsx` | React 18 `createRoot` entry |
| `src/index.css` | Dark scrollbars, React Flow overrides, JetBrains Mono |

### Design system
- Dark theme only — `#0d1117` base, GitHub dark palette throughout
- JetBrains Mono for all code/terminal/label elements
- Status colors: success `#3fb950`, error `#f85149`, warn `#d29922`, accent `#58a6ff`
- Node glows on error/warn states via CSS box-shadow

### DAG visualization
- React Flow v12 (`@xyflow/react`) with custom `modelNode` type
- Node positions consumed from backend cytoscape format (topological layout)
- Node status annotated client-side from analysis result failing_models list
- Minimap color-coded by model status
- Click node → updates selectedModel → triggers split-panel view

### Chat
- WebSocket to `/query/stream` with JSON protocol `{chunk, done, error}`
- Streaming accumulates chunks into the last assistant message
- Blinking cursor during stream via `animate-pulse`
- Markdown + GFM via `react-markdown` + `remark-gfm`
- Code blocks syntax-highlighted with `oneDark` theme
- Auto-scroll to bottom on new content

### Upload flow
1. Click "Upload Manifest" → opens file picker for `manifest.json`
2. On selection → immediately opens second picker for `run_results.json` (optional)
3. If user cancels run_results dialog → window focus event triggers manifest-only upload
4. POST to `/api/analyze` (multipart) → GET `/api/lineage` → GET `/api/analyze/status`
5. Graph data annotated with status from analysis result → rendered in DAG

### Layout
```
┌─────────────── TopBar (h-12) ────────────────┐
├──────── 60% ──────┬────────── 40% ───────────┤
│                   │  (no model selected)      │
│   DAGViewer       │  ChatPanel (full)         │
│                   │                           │
│                   │  (model selected)         │
│                   │  ModelDetail (flex-[2])   │
│                   ├───────────────────────────┤
│                   │  ChatPanel (flex-1)        │
└───────────────────┴───────────────────────────┘
```

### Error handling
- Error boundaries at App level, DAGViewer, and each right-panel component
- `useAnalysis` surfaces upload errors in the TopBar
- WebSocket errors shown as inline message in the chat stream
- All async operations have loading states

### Accessibility
- `role="banner"`, `role="main"`, `role="complementary"`, `role="log"`, `role="status"`, `role="article"` throughout
- `aria-label` on all interactive elements
- `aria-live="polite"` on chat log
- Keyboard navigation with `:focus-visible` ring (`#58a6ff`)
- Screen reader announcements for streaming state

## Build verification
- `tsc --noEmit`: zero errors
- `npm run build`: succeeds, 1191 kB bundle (expected for ReactFlow + SyntaxHighlighter)
- Zero TypeScript `any` types

## Backend API contract
| Frontend call | Backend route | Notes |
|--------------|---------------|-------|
| `POST /api/analyze` | `POST /analyze` | multipart: `manifest` + optional `run_results` |
| `GET /api/lineage` | `GET /lineage` | returns cytoscape format |
| `GET /api/analyze/status` | `GET /analyze/status` | pipeline health metrics |
| `WS ws://localhost:8000/query/stream` | `WS /query/stream` | streaming chat (bypasses proxy) |
