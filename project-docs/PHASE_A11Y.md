# Accessibility Audit Report

## Audit Overview

**Product/Feature**: pipeline-doctor frontend — all UI components
**Standard**: WCAG 2.2 Level AA
**Date**: 2026-03-18
**Auditor**: AccessibilityAuditor
**Tools Used**: Manual code review, ARIA pattern analysis, keyboard navigation analysis, color contrast calculation

## Testing Methodology

**Automated Scanning**: Static code analysis of all TSX and CSS source files
**Screen Reader Testing**: Code-level analysis of ARIA roles, labels, live regions, and announcement patterns against VoiceOver/NVDA behavior models
**Keyboard Testing**: Interaction model review for all interactive elements
**Visual Testing**: Color contrast ratio calculations; `prefers-reduced-motion` coverage review
**Cognitive Review**: Label clarity, error announcement, and status communication patterns

## Summary

**Total Issues Found**: 9
- Critical: 1 — Blocks access entirely for some users
- Serious: 2 — Major barriers requiring workarounds
- Moderate: 4 — Causes difficulty but has workarounds
- Minor: 2 — Annoyances that reduce usability

**WCAG Conformance**: PARTIALLY CONFORMS (prior to fixes)
**Assistive Technology Compatibility**: PARTIAL (prior to fixes)

**Status after fixes**: All critical and serious issues resolved. All moderate issues resolved. One minor issue noted (MiniMap color-only encoding — not fixed, see notes).

---

## Issues Found and Fixed

### Issue 1: DAG model nodes not keyboard-operable

**WCAG Criterion**: 2.1.1 Keyboard (Level A)
**Severity**: Critical
**User Impact**: Keyboard-only users and screen reader users cannot select DAG nodes. The entire model inspection workflow is blocked — they cannot open the ModelDetail panel or use it as a starting point for chat queries.
**Location**: `frontend/src/components/DAGViewer/ModelNode.tsx`

**Current State (before fix)**:
The node `<div>` had `role="button"` and `aria-label` but no `tabIndex` and no `onKeyDown` handler. A `div[role="button"]` with no `tabIndex={0}` is not in the tab order. Even with `tabIndex` added, without an `onKeyDown` handler, pressing Enter or Space on a focused node does nothing — React Flow only processes mouse click events from its internal pointer handler.

**Fix Applied**:
- Added `tabIndex={0}` to place the node in the natural tab order.
- Added `onKeyDown` handler that calls `e.currentTarget.click()` on Enter or Space, which triggers React Flow's own click event pipeline and fires the `onNodeClick` callback in DAGViewer.
- Added `aria-pressed={selected ?? false}` to communicate selected state to screen readers (the `role="button"` + `aria-pressed` pattern correctly conveys a toggle button).

**File**: `frontend/src/components/DAGViewer/ModelNode.tsx`

**Testing Verification**: Tab into the DAG canvas, navigate between nodes with Tab, press Enter or Space — the ModelDetail panel should open for the focused node. VoiceOver should announce: "model stg_orders: success, button, not pressed".

---

### Issue 2: Upload button aria-label did not match required specification

**WCAG Criterion**: 4.1.2 Name, Role, Value (Level A)
**Severity**: Serious
**User Impact**: Screen reader users hear "Upload manifest.json" which describes one specific file rather than the full two-file upload workflow (manifest + optional run_results). The label is technically present but misleading about the component's behavior.
**Location**: `frontend/src/components/TopBar.tsx`

**Current State**: `aria-label="Upload manifest.json"`

**Fix Applied**: Changed to `aria-label="Upload dbt manifest files"` — accurate to the full workflow without over-specifying the file name.

**File**: `frontend/src/components/TopBar.tsx`

---

### Issue 3: Status pill counts announced without semantic context

**WCAG Criterion**: 1.3.1 Info and Relationships (Level A)
**Severity**: Serious
**User Impact**: The pipeline status area has `role="status"` and `aria-label="Pipeline status summary"` on the wrapper, which is correct. However, the three individual pill `<div>` elements each contain only a number (e.g. `3`) with an icon (`✓`, `✗`, `⚠`) marked `aria-hidden`. When a screen reader reads the children of the `role="status"` container, it reads "3 4 1" with no differentiation between passing, failing, and warning counts. The wrapper `aria-label` is not announced for each child — only the wrapper element's label is read when focus enters the region.
**Location**: `frontend/src/components/TopBar.tsx`

**Fix Applied**:
- Added `aria-label` to each pill `<div>` with descriptive text: `aria-label="${count} passing"`, `aria-label="${count} failing"`, `aria-label="${count} warnings"`.
- Set `aria-hidden="true"` on both the icon span and the number span inside each pill, because the `aria-label` on the pill `<div>` now provides the complete accessible name, and the visual number + icon are redundant for AT.

**File**: `frontend/src/components/TopBar.tsx`

---

### Issue 4: Chat input aria-label conflicted with associated label element

**WCAG Criterion**: 4.1.2 Name, Role, Value (Level A)
**Severity**: Moderate
**User Impact**: The textarea had both an associated `<label htmlFor="chat-input">Ask about your pipeline</label>` (visually hidden with `sr-only`) and `aria-label="Type your question about the pipeline"`. The ARIA specification states that `aria-label` overrides the associated `<label>` element when computing the accessible name. This means the `<label>` element — the more semantically correct mechanism — was being silently ignored. Screen readers announced the `aria-label` text, which was slightly different wording, and the programmatic label association provided no benefit.
**Location**: `frontend/src/components/ChatPanel/ChatPanel.tsx`

**Fix Applied**: Updated `aria-label` value to `"Ask about your pipeline"` to match the `<label>` text exactly. The `<label>` element remains in place (correct HTML form association practice). The `aria-label` and `<label>` now convey identical text.

**File**: `frontend/src/components/ChatPanel/ChatPanel.tsx`

---

### Issue 5: Streaming cursor span had aria-live causing potential double-announcement

**WCAG Criterion**: 4.1.3 Status Messages (Level AA)
**Severity**: Moderate
**User Impact**: The inline streaming cursor `<span>` inside ChatMessage had both `aria-label="Typing indicator"` and `aria-live="polite"`. The `aria-live` attribute on a blinking text cursor creates a redundant live region nested inside the `role="log"` parent in ChatPanel. While the DOM content of the `|` character does not change (it blinks via CSS only), the live region declaration is incorrect — it is not a status region and should not invite AT to monitor it. Additionally, the ChatPanel already announces streaming state via a dedicated `role="status"` paragraph ("responding..."), making the cursor's `aria-live` genuinely redundant and potentially causing double-announcement in some screen readers.
**Location**: `frontend/src/components/ChatPanel/ChatMessage.tsx`

**Fix Applied**: Removed `aria-label` and `aria-live` from the cursor span. Set `aria-hidden="true"` instead. The cursor is a visual affordance only; the streaming state is fully communicated by the `role="status"` region in ChatPanel.

**File**: `frontend/src/components/ChatPanel/ChatMessage.tsx`

---

### Issue 6: Streaming status indicator text not cleanly announced

**WCAG Criterion**: 4.1.3 Status Messages (Level AA)
**Severity**: Moderate
**User Impact**: The "responding..." indicator inside ChatPanel used `role="status"` (correct) but the visible content was `| responding...` — the `|` cursor character was not `aria-hidden`. Screen readers would announce "pipe responding" or "vertical bar responding" depending on punctuation verbosity settings.
**Location**: `frontend/src/components/ChatPanel/ChatPanel.tsx`

**Fix Applied**:
- Added `aria-hidden="true"` to the cursor `<span>`.
- Wrapped "responding..." text in a `<span aria-hidden="true">`.
- Added `aria-label="Analyzing, responding..."` directly to the `role="status"` paragraph so the accessible name is explicit and not derived from visually-mixed content.

**File**: `frontend/src/components/ChatPanel/ChatPanel.tsx`

---

### Issue 7: DAG empty state had no accessible role for AT notification

**WCAG Criterion**: 4.1.3 Status Messages (Level AA)
**Severity**: Moderate
**User Impact**: When no manifest is loaded, the DAGViewer renders an empty state prompt. This container had no ARIA role, so when the DAG content is replaced by the empty state (or vice versa after upload), screen readers would not announce the state change. A user relying on a screen reader who triggers an upload might not know the DAG has failed to load or is waiting for data.
**Location**: `frontend/src/components/DAGViewer/DAGViewer.tsx`

**Fix Applied**: Added `role="status"` and `aria-label="No pipeline loaded"` to the empty state container.

**File**: `frontend/src/components/DAGViewer/DAGViewer.tsx`

---

### Issue 8: React Flow DAG container lacked aria-description for keyboard/AT orientation

**WCAG Criterion**: 1.3.1 Info and Relationships (Level A) / 2.4.6 Headings and Labels (Level AA)
**Severity**: Minor
**User Impact**: A screen reader user encountering the DAG region for the first time (landmark navigation with VoiceOver rotor or NVDA headings list) would land in a region labelled "Pipeline DAG visualization" with no explanation of how to interact with it. The interactive pattern (Tab to nodes, Enter/Space to select) is non-standard and not self-evident.
**Location**: `frontend/src/components/DAGViewer/DAGViewer.tsx`

**Fix Applied**: Added `aria-description="Interactive node graph of your dbt pipeline. Use Tab to move between model nodes and Enter or Space to select a node and view its details."` to the region wrapper `<div>`. `aria-description` is announced by VoiceOver after the region label when entering the region, and is visible to JAWS users through the virtual buffer.

**File**: `frontend/src/components/DAGViewer/DAGViewer.tsx`

---

### Issue 9: Streaming cursor animation not suppressed under prefers-reduced-motion

**WCAG Criterion**: 2.3.3 Animation from Interactions (Level AAA) / inclusive design baseline
**Severity**: Minor
**User Impact**: Users with vestibular disorders who have enabled "Reduce motion" in their OS settings will still see the blinking cursor animation. At 1 second per cycle the animation is well below the photosensitive seizure threshold (< 3 Hz), so this is not a WCAG 2.3.1 (AA) violation. However, ignoring `prefers-reduced-motion` for any looping animation is a barrier for motion-sensitive users and is flagged as a best-practice fix.
**Location**: `frontend/src/index.css`

**Fix Applied**: Added a `@media (prefers-reduced-motion: reduce)` block that sets `animation: none` on `.cursor-blink`.

**File**: `frontend/src/index.css`

---

## What Was Already Well-Implemented

The following patterns were found to be correctly implemented and should be preserved:

- **Semantic landmark structure**: `<header role="banner">`, `<main aria-label="Pipeline DAG">`, `<aside aria-label="Analysis panel">` in App.tsx — clean, no redundancy.
- **Chat log region**: `role="log"` with `aria-live="polite"` and `aria-atomic="false"` on the messages container is the correct pattern for a chat interface. Individual messages use `role="article"` with descriptive `aria-label` — well done.
- **Form label pattern**: `<label htmlFor="chat-input">` with `className="sr-only"` paired with the textarea `id` is correct semantic HTML. This pattern should be used as the model for any future form fields.
- **Clear button**: Properly disabled with `disabled` attribute (not just visually styled) when no messages exist — ensures keyboard users cannot activate a no-op control.
- **Send button**: Correct `aria-label="Send message"` with `type="button"` and `disabled` attribute.
- **Error alerts**: Upload error uses `role="alert"` with `title` attribute for full text — correct.
- **Decorative elements**: Logo dot `●`, status icons (`✓`, `✗`, `⚠`), and decorative `⬡` all carry `aria-hidden="true"` — no false positives for screen readers.
- **Close button**: `aria-label="Close model detail panel"` is descriptive and present — correct.
- **Navigation links in ModelDetail**: Upstream/downstream buttons use `disabled` attribute and `aria-label` with destination name — correct.
- **Focus styles**: `:focus-visible` with `2px solid #58a6ff` and `outline-offset: 2px` is present globally and provides a clear, visible focus indicator against the dark background. The contrast of the focus ring color (#58a6ff on #0d1117) is approximately 5.9:1, which meets WCAG 1.4.11 Non-text Contrast (3:1 minimum).
- **Color contrast**: The primary text (#e6edf3 on #0d1117) is approximately 15:1. The muted text (#8b949e on #0d1117) is approximately 6.4:1. Both exceed WCAG AA minimums. No contrast failures were found.

---

## Issues Not Fixed (Acknowledged Limitations)

### MiniMap color-only node encoding
The MiniMap uses color alone to encode node status (green = success, red = error, yellow = warn, grey = skipped/unknown). This violates WCAG 1.4.1 Use of Color for users who cannot distinguish the status colors. However, the MiniMap is a supplementary orientation aid — all the same information is conveyed by the full node labels in the main canvas (which include text status labels). The MiniMap has no interactive function. Fixing this would require a React Flow MiniMap customization that adds pattern fills or text, which is a significant engineering effort relative to the low user impact. Flagged as a future improvement, not a blocker.

### React Flow internal focus management
React Flow's canvas panning and zooming controls (`<Controls>`) are rendered by the library and are keyboard-accessible via the library's own implementation. The focus management between the canvas pane and individual nodes is partially controlled by React Flow internals. The keyboard improvements made here (tabIndex, onKeyDown on ModelNode) work with React Flow's architecture rather than against it, but full keyboard traversal across a large DAG with Tab is impractical — screen reader users are better served by the ModelDetail panel and Chat interface. This is a known limitation of canvas-based visualizations.

---

## Remediation Priority

### Immediate (resolved in this audit — all complete)
1. DAG node keyboard operability — ModelNode tabIndex + onKeyDown
2. Upload button aria-label accuracy — TopBar
3. Status pill accessible names — TopBar
4. Chat input label conflict — ChatPanel
5. Streaming cursor live region removal — ChatMessage
6. Streaming status text clarity — ChatPanel
7. DAG empty state role — DAGViewer
8. DAG region aria-description — DAGViewer
9. Reduced motion for cursor blink — index.css

### Future / Ongoing
1. MiniMap status encoding — add non-color differentiation (pattern or shape) for node status
2. Consider adding a skip-link from the top of the page to the main chat input, since the DAG canvas is a large interactive region that keyboard users would otherwise have to Tab through entirely
3. Consider adding an accessible summary of loaded pipeline statistics (e.g. a visually-hidden `<dl>` listing total/passing/failing counts) that screen readers can navigate directly without relying on the live `role="status"` region in the TopBar

---

## Files Modified

- `frontend/src/components/TopBar.tsx` — Upload button aria-label; status pill accessible names
- `frontend/src/components/DAGViewer/ModelNode.tsx` — tabIndex, onKeyDown, aria-pressed
- `frontend/src/components/DAGViewer/DAGViewer.tsx` — Empty state role; region aria-description
- `frontend/src/components/ChatPanel/ChatPanel.tsx` — Input aria-label; streaming status clarity
- `frontend/src/components/ChatPanel/ChatMessage.tsx` — Cursor span aria-hidden
- `frontend/src/components/ModelDetail/ModelDetail.tsx` — SQL section aria-label
- `frontend/src/index.css` — prefers-reduced-motion guard; DAG node focus ring rule
