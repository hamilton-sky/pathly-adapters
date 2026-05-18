## Review Failures — Conv 2 (studio-v2)

Reviewed file: `studio/src/renderer/src/components/Monitor/index.tsx`

---

### VIOLATION 1 — Wrong store reference in SSE onmessage handler
**File:** `studio/src/renderer/src/components/Monitor/index.tsx:196-197`
**Rule:** Store contract — all reads and writes must go through the declared merge layer (`useStore`), not bypass it via direct store access.
**Description:** `es.onmessage` calls `useProjectStore.getState().events` and `useProjectStore.getState().setEvents(...)` instead of using the `setEvents` already destructured from `useStore()` at line 122. This creates a second divergent write path that bypasses the merge layer and any middleware that may be added to it.

---

### VIOLATION 2 — `getFlowYamlName` default branch produces `undefined.flow.yaml`
**File:** `studio/src/renderer/src/components/Monitor/index.tsx:31`
**Rule:** S2 acceptance criterion — correct `.flow.yaml` loaded per flow type; unknown/undefined input must not silently produce a bad filename.
**Description:** The `default` branch returns `` `${flow}.flow.yaml` ``. When `flow` is `undefined` (e.g., before STATE.json is loaded), this produces the string `"undefined.flow.yaml"` rather than a safe fallback. Contrast with `getBasePath`, which explicitly handles `undefined` and warns. The parallel logic is missing here.

---

### VIOLATION 3 — `agent` field not modeled on `FsmEvent`; cast is load-bearing and unverifiable
**File:** `studio/src/renderer/src/components/Monitor/index.tsx:97`
**Rule:** Type contract — `FsmEvent` in `types/index.ts` does not declare an `agent` field and has no index signature, so accessing `.agent` requires an unsafe cast.
**Description:** `(lastAgentEvent as FsmEvent & { agent?: string }).agent` is the only mechanism that exposes the agent name. Because `FsmEvent` is a closed interface with no index signature, the TypeScript compiler cannot verify the field exists at runtime. The `agent` field on `AGENT_SPAWNED` events must be added to `FsmEvent` (or a discriminated subtype) to make this type-safe.

---

### WARNING 1 — Bootstrap race: `fsmState` not in `useEffect` dependency array
**File:** `studio/src/renderer/src/components/Monitor/index.tsx:135-136`
**Severity:** Non-blocking
**Description:** `initialFlow` is read from `fsmState?.flow` at effect-entry. When `fsmState` is null on first mount (common case), `getBasePath(undefined)` silently falls back to `pathly/plans/`. For a `debug` or `explore` topic this means the initial STATE.json read targets the wrong directory. The effect dependency array (line 210) does not include `fsmState`, so there is no retry after the state is populated. This can cause the monitor to silently show nothing for non-team flows on first open.

---

### WARNING 2 — Unnecessary full array copy on every `HeaderBar` render
**File:** `studio/src/renderer/src/components/Monitor/index.tsx:94`
**Severity:** Non-blocking
**Description:** `[...events].reverse().find(...)` copies the entire events array on every render. `Array.prototype.findLast` or manual reverse-iteration would avoid the allocation.

---

### WARNING 3 — `FlowType` declared but provides no exhaustiveness guarantee
**File:** `studio/src/renderer/src/components/Monitor/index.tsx:11`
**Severity:** Non-blocking
**Description:** `FlowType = 'team' | 'debug' | 'explore'` is defined but `getFlowYamlName` casts to it with `flow as FlowType` while keeping a `default` branch, so no exhaustiveness check fires. The type is unused in any meaningful way.
