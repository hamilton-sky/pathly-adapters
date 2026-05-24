# Pathly Studio — UI Gap Analysis

_What the Studio desktop app (`pathly-studio` v2.10.0) already implements versus
the suggestions in `PATHLY_SUGGESTIONS.md`. Companion to `PATHLY_ASSESSMENT.md`._

---

## What Studio is

`pathly-studio` is an Electron desktop app for **configuring and monitoring** the
Pathly pipeline. Main panels:

- **Sidebar** — workspace + plan/library navigation.
- **Editor** — Markdown skill/agent editor with preview.
- **FlowEditor** — visual (ReactFlow) + YAML editor for `*.flow.yaml`, with
  validation and a 5-step creation wizard.
- **Monitor** — live FSM view: pipeline stepper + event log, SSE-driven.
- **PlanBoard** — per-conversation board with **token + cost** rollups.
- **Terminal** — embedded `node-pty` terminals.
- **Setup / Home** — install + onboarding screens.

---

## Suggestion-by-suggestion mapping

| # | Suggestion | Status in Studio | Evidence |
|---|------------|------------------|----------|
| **D2** | FSM observability (timeline + cost) | ✅ **Already there** | `Monitor/FsmView.tsx` (vertical pipeline stepper, done/remaining counts), `Monitor/EventLog.tsx` (live SSE stream + live/polling badge), `PlanBoard.tsx` (per-conversation token in/out + `$` cost, per-event cost) |
| **B1** | Consistency checker | 🟡 **Partial** | `FlowEditor/utils/validateFlow.ts` + `useFlowValidation` validate flow YAML (states, transitions, transition_rules, transition_actions, agent_map behaviors). Scope = **flow definitions only** — not skill/agent path drift or doc cross-references |
| **D3** | Guided first-run / progressive disclosure | 🟡 **Partial** | `SetupScreen`, `HomeScreen`, 5-step `FlowWizard` (Name → States → Transitions → Agents → Review). Onboarding is for **building flows**, not for hiding machinery during a first feature run |
| **B2** | Schema for feedback/state protocol | 🟡 **Weak** | `types/index.ts` defines `FsmEvent` / `FlowSession` / `FlowYaml`, but `STATE.json` / `EVENTS.jsonl` / feedback files are parsed defensively (try/catch), not schema-validated |
| **B3** | Generated skill map | ❌ Not there | A behavior/skill *library* exists (`useKnownBehaviors`, `useBehaviorList`), but no generated skill-map document |
| **D1** | Auto lessons loop | ❌ Not there | No `lesson` / `retro` references anywhere in the renderer — not surfaced in Studio |
| **D4** | Self-doctor (drift / stale / health) | ❌ Not there | No `doctor` / `verify-state` / `drift` / `orphan` UI. The "● live / ○ polling" badge is connection health only |
| **A1–A5** | Core correctness fixes | ❌ N/A in UI | These live in `core/` Markdown, not the app — but see Key Finding below |
| **C1–C2** | Transcript / adapter-parity tests | ❌ Not there | Testing concerns, outside the UI |

---

## Key finding — Studio proves ISSUE-1 (storage-path drift) is a live bug

The Monitor probes **only** these three roots for `STATE.json`
(`Monitor/index.tsx`):

```
pathly/plans/<topic>
pathly/debugs/<topic>
pathly/explorations/<topic>
```

It **never** looks at bare `plans/`. Therefore:

> The canonical storage root is unambiguously **`pathly/`**. Any flow whose
> skills write to bare `plans/` (the majority — ~25 skill files) is **invisible
> to the Studio monitor**: the live FSM view, the event log, and the cost board
> all silently show nothing.

This promotes **A1** from "documentation tidy-up" to **"the desktop app is
already broken for the most common path."** It also resolves the fix direction:
unify everything onto `pathly/`, not bare `plans/`.

---

## Two smaller confirmations from the UI

1. **Naming (ISSUE-2):** Studio uses flow names `team` / `debug` / `explore`
   (`team.flow.yaml`, etc.). This supports **Option A** — keep the directory
   `team/` and fix the `team-flow/` doc references, rather than renaming.
2. **Cost telemetry already exists:** Events carry `cost_usd`, `tokens_in`,
   `tokens_out`, `wall_seconds`. D2's "per-stage token cost" is effectively
   **done at the conversation level** — no new instrumentation needed, only
   aggregation/rollup if a flow-level summary is wanted.

---

## Revised status of the roadmap (post-UI review)

| ID | Was | Now | Note |
|----|-----|-----|------|
| A1 | P0 ★★★ | **P0 ★★★ (urgent)** | UI confirms it breaks the monitor today |
| A2 | P1 ★★ | P1 ★★ | UI confirms "keep `team`" direction |
| D2 | Enhancement ★★★ | ✅ **Done (conv-level)** | Optional: add a flow-level cost summary |
| B1 | ★★★ | ★★★ (partial) | Flow YAML covered; extend to skill/agent contracts |
| D3 | ★★ | ★★ (partial) | Flow-building onboarding exists; feature-run guidance does not |
| B2 | ★★ | ★★ | No protocol schema yet; UI parses defensively |
| B3, D1, D4, C1, C2 | — | ❌ Still open | No UI coverage |

---

## Recommended next actions

1. **Fix A1 immediately** — unify all `core/skills/` and `core/agents/` paths to
   `pathly/`. This restores Studio monitoring for the majority of flows.
2. **Add the consistency checker (B1)** scoped to the contract layer
   (path prefix, dangling skill refs, doc drift) — Studio already proves the
   value of validation for the flow layer; extend the same idea to skills/agents.
3. **Treat D2 as done** at the conversation level; only build a flow-level cost
   summary if a single-number "what did this feature cost" view is wanted.
4. **Leave D1 / D4 as genuine product gaps** — an auto lessons loop and a
   self-doctor view are the highest-value *new* surfaces Studio doesn't have yet.
