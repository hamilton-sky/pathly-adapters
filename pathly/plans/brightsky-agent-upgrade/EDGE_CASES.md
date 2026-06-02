---
name: Edge Cases
---
# BrightSky Agent Upgrade — Edge Cases

## Category 1: Tool call failures

### EC-1.1: `studio.list_plans` — plans directory doesn't exist
- **Trigger**: User has a project path set but has never run a Pathly plan (no `pathly/plans/` folder)
- **Current behavior**: `window.pathly.fs.listDirs` throws or returns error
- **Expected behavior**: Returns `{ plans: [], success: true }` — agent handles gracefully with "no plans yet" message
- **Handled in**: Phase 1 — wrap in try/catch, return empty array on error

### EC-1.2: `studio.create_plan` — write fails (no mkdir on fs.write)
- **Trigger**: `window.pathly.fs.write` doesn't create parent directories; plan folder doesn't exist yet
- **Current behavior**: Write silently fails or throws file-not-found
- **Expected behavior**: Creates parent directories before writing
- **Handled in**: Phase 4 — verify `fs.ts` IPC handler uses `{ recursive: true }` mkdir; fix if absent

### EC-1.3: Tool response timeout (30s)
- **Trigger**: Studio is slow (heavy I/O, large plan file), backend's 30s tool wait expires
- **Current behavior**: Backend logs timeout, agent gets no result
- **Expected behavior**: Backend receives `{ success: false, error: 'timeout' }` and agent says "couldn't read plan files right now"
- **Handled in**: Existing timeout logic in `StudioBridgeTool` (30s already implemented) — no change needed; just document

---

## Category 2: Reasoning box edge cases

### EC-2.1: `<think>` block spans multiple stream_chunks
- **Trigger**: Backend splits the `<think>...</think>` content across several stream_chunk messages
- **Current behavior (after fix)**: `splitThinkingContent` is called only at stream_end on the full accumulated string — handles correctly regardless of how chunks are split
- **Expected behavior**: Works correctly — the entire content is accumulated before parsing
- **Handled in**: Phase 8 — splitThinkingContent called on final accumulated content only

### EC-2.2: Message has no `<think>` content
- **Trigger**: BrightSky responds without extended thinking (e.g., simple "yes/no" answer, or extended thinking budget exceeded)
- **Current behavior (after fix)**: `splitThinkingContent` returns `{ thinking: undefined, content: fullText }`
- **Expected behavior**: `msg.thinking` remains undefined; ThinkingBlock is not rendered; message shows normally
- **Handled in**: Phase 8 — the `thinking: undefined` case is already handled by ThinkingBlock (it only renders when `thinking` prop has content)

### EC-2.3: Extended thinking not available (model doesn't support it)
- **Trigger**: Backend sends Pathly message to a model that doesn't support `thinking` param (e.g., non-claude model)
- **Current behavior**: Claude API throws validation error
- **Expected behavior**: Backend catches error, falls back to non-extended call, no thinking content sent — reasoning box simply stays hidden
- **Handled in**: Phase 11 — add try/catch around the extended_thinking API call; log and fall back to standard call on error

---

## Category 3: run_skill edge cases

### EC-3.1: FSM server is not running
- **Trigger**: User triggers `studio.run_skill` but the FSM HTTP server is down
- **Current behavior**: `fetch()` in `fsm:runSkill` throws "connection refused"
- **Expected behavior**: Returns `{ success: false, error: 'FSM server not available' }` — agent tells user to restart Pathly Studio
- **Handled in**: Phase 6 — wrap fetch in try/catch, return structured error

### EC-3.2: Feature already running
- **Trigger**: `/runner/start` called while a run is already in progress for that feature
- **Current behavior**: FSM returns 409 or similar conflict
- **Expected behavior**: Returns `{ success: false, error: 'Run already in progress' }` — agent notifies user
- **Handled in**: Phase 6 — check HTTP response status; map non-2xx to `{ success: false, error: statusText }`

---

## Category 4: Cross-repo build failures

### EC-4.1: Type mismatch in new tool classes
- **Trigger**: New `StudioBridgeTool` subclass is missing required abstract method or has wrong parameter type
- **Current behavior**: TypeScript build fails in `brightsky-ai/backend/`
- **Expected behavior**: Builder catches this in `npx tsc --noEmit` at end of Conv 3
- **Handled in**: Phase 9 verify step

---

## Known Limitations
- `studio.run_skill` launches a pipeline run but does not stream the run output back through BrightSky chat — the user must watch the Monitor panel. This is intentional for this iteration.
- Extended thinking budget is fixed at 8000 tokens — not configurable per-message. A future iteration could make this dynamic based on query complexity.
- `studio.navigate_to` only works when `window.__pathlyNavigate` is bound (i.e., the HQ panel is mounted). Calling it before the panel mounts returns `{ success: false }` gracefully.
