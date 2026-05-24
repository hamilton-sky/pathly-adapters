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

## ✅ Key finding RESOLVED — Storage-path drift fixed (2026-05-24)

The Monitor probes **only** these three roots for `STATE.json`
(`Monitor/index.tsx`):

```
pathly/plans/<topic>
pathly/debugs/<topic>
pathly/explorations/<topic>
```

~~It **never** looks at bare `plans/`.~~ **This is now consistent:** all 39
affected core skill/agent files were updated to use the `pathly/` prefix. The
Studio Monitor, event log, and cost board will find STATE.json for all flows.

A1 is resolved. The canonical root is `pathly/` throughout.

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

## Revised status of the roadmap (updated 2026-05-24)

| ID | Status | Note |
|----|--------|------|
| A1 | ✅ **Done** | 39 files unified to `pathly/` prefix; monitor unblocked |
| A2 | ✅ **Done** | All `team-flow` refs replaced with `team` |
| A3 | ✅ **Done** | `go.md` is single source; director + pathly delegated |
| A4 | ✅ **Done** | `director.md` moved to `agents/director.md` |
| A5 | ✅ **Done** | `pathly-controlls/` deleted |
| D2 | ✅ **Done (conv-level)** | Studio Monitor + PlanBoard already cover this |
| B1 | ★★★ (partial) | Flow YAML covered by `validateFlow`; skill/agent contract check still open |
| D3 | ★★ (partial) | Flow-building onboarding exists; feature-run guidance does not |
| B2 | ★★ | No protocol schema yet; UI parses defensively |
| B3, D1, D4, C1, C2 | ❌ Open | No UI coverage; see `PATHLY_SUGGESTIONS.md` |

---

## Recommended next actions (updated 2026-05-24)

1. ~~**Fix A1 immediately**~~ ✅ Done.
2. **Add the consistency checker (B1)** scoped to the contract layer
   (path prefix, dangling skill refs, adapter parity) — Studio already proves the
   value of validation for the flow layer; extend the same idea to skills/agents.
3. ~~**Treat D2 as done**~~ ✅ Already confirmed done.
4. **D1 and D4 are the highest-value new surfaces** — auto lessons loop and
   self-doctor view are genuine product gaps with clear implementation paths.
