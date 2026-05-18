# studio-ui-fixes — Architecture Proposal

## Decision 1: pipelineStates lives in the project store, not component state

**Options considered:**
- A) Local state in FsmView (read flow YAML directly in the component)
- B) Local state in Monitor/index.tsx, passed as a prop to FsmView
- C) Project store slice, populated by Monitor/index.tsx

**Chosen:** C

**Rationale:** Monitor/index.tsx already owns the lifecycle (useEffect on activeTopic, reads STATE.json). It naturally knows when to load/clear the flow YAML. FsmView is a pure display component — giving it a readFile side-effect would break the rendering-only boundary established by the studio-arch-refactor plan. The store is the correct channel between the data-fetching layer and display layer.

**Tradeoff:** `pipelineStates` is transient (not persisted), so it resets on reload — this is correct behaviour since STATE.json is always re-read on mount.

---

## Decision 2: eventDetail is a file-level helper, not a component method

**Rationale:** The function is pure (no hooks, no side effects). A top-level function is easier to test and avoids coupling the logic to the component lifecycle. Consistent with how `formatTime` is already written.

---

## Decision 3: PROGRESS.md parser scopes to Conversation Breakdown section only

**Options considered:**
- A) Fix the column index so Verify isn't read as Status
- B) Only parse rows after the `## Conversation Breakdown` heading

**Chosen:** B

**Rationale:** Option A is fragile — it depends on column count being stable. Option B is semantically correct: the sidebar only needs conversation-level rows, not phase detail rows. Using the section heading as a fence is robust to future table additions in PROGRESS.md.

---

## Decision 4: Debugs and Explorations reuse the template subdir rendering

**Rationale:** The pattern already exists and is tested. Adding `type === 'debug' || type === 'explore'` to the template branch condition adds zero new rendering code. The only new code is in `useProjectFiles` (loading) and `types/index.ts` (type union).

**Tradeoff:** Debug and explore items open in the same editor as skills/agents. This is intentional — they are markdown files. A future "read-only" mode could be added to the editor without changing this architecture.

---

## What is explicitly NOT in scope

- MCP event subscription (`mcp:ping` always returns false; requires `mcp-fsm-driver`)
- Agent / conv info in the Monitor pipeline bar (UX diagram section 11 shows this; deferred)
- `● MCP live` badge driving actual event stream (cosmetic until MCP is live)
- Plan conversation representation redesign beyond parser fix (the sidebar shows phase ranges from PROGRESS.md as titles; a richer timeline view is a separate feature)
