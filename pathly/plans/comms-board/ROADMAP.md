# comms-board / Goals-DAG — Roadmap

Live tracker for the **Board → Goals → Task-DAG → pluggable-executors** build.
Model: [GOALS-DAG-EXECUTORS.md](GOALS-DAG-EXECUTORS.md). Shipped-phase specs are in
[`_archive/phases/`](_archive/phases/).

## Shipped to `master` ✅

The end-to-end self-driving system for one goal works **and is visible/controllable in
Studio** (Goals & Tasks view, executor selector, Decompose / Run / Stop):

| Phase | What | Spec |
|---|---|---|
| 0a | goals + executor schema (`goal_id`/`executor` cols; goal = `type='goal'`) | [`_archive/phases/PHASE-0-goals-schema.md`](_archive/phases/PHASE-0-goals-schema.md) |
| 0b | planner → task DAG (emit `type=task`; accept `goal_id`/`executor`) | [`_archive/phases/PHASE-0b-planner-dag-wiring.md`](_archive/phases/PHASE-0b-planner-dag-wiring.md) |
| two-flow split | consultation flow (PO→arch→research→design→planner) + trimmed `team-build` | `core/flows/{consultation,team-build}.flow.yaml` |
| P1 | **dispatcher** — route task/goal → `single`\|`loop`\|`team` (serial) + `/comms/goals/stop` | [`_archive/phases/PHASE-1-dispatcher.md`](_archive/phases/PHASE-1-dispatcher.md) |
| P2 | board UI — goals as groupings, executor + engine selectors, Decompose/Run/Stop | [`_archive/phases/PHASE-2-ui-ux-spec.md`](_archive/phases/PHASE-2-ui-ux-spec.md) |

Plus three shipped sub-features (specs in `_archive/`):
- **context-retrieval** — `context_refs` manifest + `/section` hydration + Board Catalog + opt-in summarizer (incl. §3a: uploaded `.md` summary feeds the 💡 semantic channel)
- **summarizer controls** — global default + per-upload backend (Off/Local/Haiku) + start/done/fail observability
- **memory-consolidation** — [MEMORY-CONSOLIDATION.md](MEMORY-CONSOLIDATION.md) (`/comms/consolidate`)

The full chain is verified (2026-06-22): start feature → create/drag artifacts →
evaluator / planner / consultation seed a goal + DAG → single / loop / team execute it.

## Remaining work

### P3 — parallel  🔭 (the only unbuilt phase)
Across-goal lanes → within-goal worktree fan-in + **consolidation**. Flip `k>1` by lane;
the data model is already parallel-ready. Design lives in `../parallel-fleet-part-1/` and
`../parallel-fleet-part-2/` (the latter overlaps [HQ-COMMAND-CENTER.md](HQ-COMMAND-CENTER.md)
— consolidate the fleet-dashboard framing when P3 starts).

### Deferred polish (small, non-blocking — none gate the chain above)
- **per-task ad-hoc Run** button — no backend route yet (goal-level Run already covers it)
- artifact **edit-hooks + versioning** — `last_edit_*`/`version` columns exist, unpopulated
- **multi-adapter routing** — primitive is wired (Claude+Codex spawn done; per-goal engine
  selector ships). Left: populate `adapter_map` in flow YAMLs (a few lines) + finish
  Copilot/Antigravity spawn argv.

## At a glance
Everything except **P3** is shipped. P3 makes it parallel (k>1 by lane → worktree fan-in);
the HQ dashboard is the last surface after that.
