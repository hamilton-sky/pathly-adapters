---
name: Architecture Proposal
---
# HQ Panel — Architecture Proposal

## Problem Statement

The existing `ChatPanel` component is a passive renderer: it shows FSM menu cards and relays user picks to the terminal. As the Pathly runner gains the ability to execute multi-adapter pipelines autonomously, Studio needs a control surface that (a) drives the runner via REST, (b) receives live state from an SSE stream, and (c) lets users confirm or steer mid-run decisions — all from a single panel.

## Proposed Solution

Rename `ChatPanel` → `HQ`. Introduce three new structural concerns in the HQ component tree:

1. **`runnerStore`** — a Zustand slice that is the single source of truth for all runner-related state (status, stage, adapter, cost, session, decision menu, error).
2. **`FlowControlBar`** — a toolbar wired to `POST /runner/*` endpoints with correct disabled logic per status.
3. **SSE client in `useHQ.ts`** — an `EventSource` to `/events/runner` that dispatches typed events into `runnerStore`.

`PathlyMenuCard` gains a "decision mode" driven by `runnerStore.decisionMenu`, keeping the component's original FSM-menu behavior when the runner is not active.

## Layer Breakdown

```
Studio panel (React)
     │
     ├── HQ/index.tsx               (renamed ChatPanel — layout, composes sub-components)
     │      │
     │      ├── ChatHeader.tsx      (existing — subtitle/tooltip added)
     │      ├── FlowControlBar/     (NEW — Start/Pause/Resume/Advance/Reroute/Retry/Abort)
     │      │      ├── AbortConfirmStrip.tsx    (inline confirm — not a modal)
     │      │      └── ReroutePopover.tsx       (adapter picker)
     │      ├── StageStatusStrip/   (NEW — stage, adapter chip, cost, session, errors)
     │      └── PathlyMenuCard.tsx  (MODIFIED — decision mode when decisionMenu != null)
     │
     ├── useHQ.ts                   (MODIFIED — SSE lifecycle, event dispatch → runnerStore)
     │
     └── store/runnerStore.ts       (NEW Zustand slice)
            │
            ├── status, stage, adapter, cost, sessionKind
            ├── decisionMenu: DecisionMenuItem[] | null
            └── errorMessage: string | null

HTTP layer
     │
     ├── POST http://127.0.0.1:8765/runner/{start,pause,resume,advance,reroute,retry,abort}
     ├── POST http://127.0.0.1:8765/runner/decision
     └── GET  http://127.0.0.1:8765/events/runner   (SSE)

Backend dependency (multi-adapter-runner — NOT in scope here)
```

## Key Design Decisions

### Decision 1: Zustand store as SSE sink (not React Context)
- **Options considered:**
  - A — React Context holding a value object updated on every SSE event
  - B — Zustand slice updated by `useHQ.ts`; components subscribe individually
  - C — Local state in `useHQ.ts` passed as props down the tree
- **Chosen:** B
- **Rationale:** The existing codebase already uses Zustand for `projectStore`, `chatStore`, `terminalStore`, etc. Zustand's selective subscriptions (`store((s) => s.cost)`) prevent over-rendering on high-frequency `COST_UPDATE` events. Option A causes full context subtree re-renders. Option C forces prop drilling through `HQ → StageStatusStrip` and `HQ → PathlyMenuCard`.

### Decision 2: SSE in `useHQ.ts`, not a top-level Context
- **Options considered:**
  - A — Move SSE client to a new `RunnerContext` at App root, mirror `pathlyContext.ts`
  - B — Keep SSE client inside `useHQ.ts` as a local `useEffect`
- **Chosen:** B
- **Rationale:** Runner state is only consumed by HQ panel components. A top-level context would survive HQ unmounts and accumulate stale state. The hook approach ties SSE lifetime directly to the panel's mount/unmount lifecycle. If a future feature needs runner state outside HQ, promote to context then.

### Decision 3: PathlyMenuCard reads store directly (not props)
- **Options considered:**
  - A — Pass `decisionMenu` and `onDecisionClick` as props from `HQ/index.tsx`
  - B — `PathlyMenuCard` reads `runnerStore.decisionMenu` directly
- **Chosen:** B
- **Rationale:** The component already lives inside HQ and does not need to be reused outside it. Direct store reads avoid adding new props to a component that other parts of the codebase import. The switch between decision mode and FSM mode is encapsulated inside the component.

### Decision 4: Inline confirm strip (no modal) for Abort
- **Options considered:**
  - A — Browser `confirm()` dialog
  - B — A modal overlay
  - C — An inline strip that appears below the control bar (per DESIGN.md)
- **Chosen:** C
- **Rationale:** DESIGN.md explicitly calls out "inline confirm, not modal" for destructive actions. Browser `confirm()` blocks the event loop and is inaccessible. The inline strip keeps the user in context, has `role="alert"` for screen readers, and requires no modal portal infrastructure.

## Key Components

| Component | File | Description |
|---|---|---|
| `HQ` | `HQ/index.tsx` | Root panel — composes all sub-components; was `ChatPanel` |
| `useHQ` | `HQ/useHQ.ts` | Hook — SSE lifecycle, original chat panel logic |
| `FlowControlBar` | `HQ/FlowControlBar/FlowControlBar.tsx` | Seven control buttons; POSTs to `/runner/*` |
| `AbortConfirmStrip` | `HQ/FlowControlBar/AbortConfirmStrip.tsx` | Inline destructive-action confirm |
| `ReroutePopover` | `HQ/FlowControlBar/ReroutePopover.tsx` | Adapter picker for reroute action |
| `StageStatusStrip` | `HQ/StageStatusStrip/StageStatusStrip.tsx` | Live stage/adapter/cost/session display |
| `PathlyMenuCard` | `HQ/PathlyMenuCard.tsx` | Dual-mode: FSM menu or decision menu |
| `runnerStore` | `store/runnerStore.ts` | Zustand slice — all runner state |

## Interface Design

```ts
// runnerStore public interface (consumers import via store/index.ts)
type RunnerStatus = 'idle' | 'running' | 'paused' | 'blocked' | 'error'
type SessionKind  = 'opened' | 'continued' | 'degraded' | null

interface DecisionMenuItem {
  id:    string
  label: string
}

interface RunnerState {
  status:       RunnerStatus
  stage:        string | null
  adapter:      string | null
  cost:         number
  sessionKind:  SessionKind
  decisionMenu: DecisionMenuItem[] | null
  errorMessage: string | null

  // Actions
  setRunnerState:  (partial: Partial<RunnerState>) => void
  resetRunner:     () => void
  setDecisionMenu: (items: DecisionMenuItem[] | null) => void
}
```

## Risks

- **`adapters.gen.ts` path unknown:** The backend feature generates this file but its exact path in the Studio source tree is unconfirmed. Phase 0 pre-flight globs for it; if absent the plan halts. Mitigation: coordinate with `multi-adapter-runner` plan to confirm the output path before Conv 1.
- **SSE event schema drift:** If the backend changes SSE event type names or payload shapes after Conv 2 ships, `useHQ.ts` will silently receive unrecognized events. Mitigation: define event type constants in `runnerStore.ts` as an exported enum/union so a TypeScript mismatch surfaces at compile time once `adapters.gen.ts` exports the event contract.
- **Component line-limit pressure:** `FlowControlBar` with seven buttons + inline `AbortConfirmStrip` + `ReroutePopover` may approach 150 lines. Extract sub-components aggressively. The three sub-components are already planned as separate files.
