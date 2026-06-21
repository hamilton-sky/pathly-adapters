# comms-board / Goals-DAG — Roadmap

Live phase tracker for the **Board → Goals → Task-DAG → pluggable-executors** build.
Model: [GOALS-DAG-EXECUTORS.md](GOALS-DAG-EXECUTORS.md). Per-phase specs: [phases/](phases/).

## Phases

| Phase | What | Status | Doc |
|---|---|---|---|
| 0a | goals + executor schema (`goal_id`/`executor` cols; goal = `type='goal'`) | ✅ done | [phases/PHASE-0-goals-schema.md](phases/PHASE-0-goals-schema.md) |
| 0b | planner → task DAG (emit `type=task`; accept `goal_id`/`executor`) | ✅ done | [phases/PHASE-0b-planner-dag-wiring.md](phases/PHASE-0b-planner-dag-wiring.md) |
| two-flow split | consultation flow (PO→arch→research→design→planner) + trimmed `team-build` flow (build→review→test→retro, feedback routes to specialists) | ✅ done | `core/flows/{consultation,team-build}.flow.yaml` |
| P1 | **dispatcher** — route task/goal → `single`\|`loop`\|`team` (serial) | ✅ done | [phases/PHASE-1-dispatcher.md](phases/PHASE-1-dispatcher.md) |
| P2 | board UI — goals as groupings, executor selector, Decompose/Run/Stop | ✅ done | [phases/PHASE-2-ui-ux-spec.md](phases/PHASE-2-ui-ux-spec.md) |
| P3 | parallel — across-goal → lanes → worktree fan-in + **consolidation** | 🔭 next (only remaining phase) | see `../parallel-fleet-part-1/`, `-part-2/` |

> **Status (2026-06-22):** 0a/0b/P1/P2 are **all shipped to `master`**, plus the separate
> **context-retrieval** sub-feature (manifest + `/section` hydration + Board Catalog + opt-in
> summarizer — see [BUILD_PROMPTS.md](BUILD_PROMPTS.md)). Recent follow-ups: `/comms/goals/stop`
> endpoint (real goal Stop), the `loop` executor now hydrates the 📎 context channel, and the
> evaluator now seeds a real goal+DAG. **P3 (parallel) is the only unbuilt phase.**

## Riders (cross-cutting — NOT separate end-phases)

### Multi-adapter routing — **rides P1**
Run different goals/stages on different CLIs (architect→Codex, builder→Claude, …).
**The routing PRIMITIVE is already wired — do NOT rebuild it** (verified 2026-06-16):

- flow `adapter_map` → `_resolve_adapter(state)` → `preferred_adapter` in `/next_action` ([fsm_ops.py:343](../../../src/pathly_orchestrator/fsm_ops.py))
- per-stage UI override via `stage_configs` injected into `adapter_map` at runtime ([fsm_ops.py:611](../../../src/pathly_orchestrator/fsm_ops.py))
- runner honors it: `TERMINAL_SPAWN` carries `adapter`; cross-adapter transition → new session
- board single-agent run already has the **engine selector** (claude/codex) we shipped

**What's left (small, rides P1):** populate `adapter_map` in flows (a few YAML lines);
finish Copilot/Antigravity spawn argv (Claude+Codex done); **per-goal/per-task adapter
chosen WITH the executor** in the dispatcher (one selector, two fields).

**History:** the old `multi-adapter-routing` / `multi-adapter-runner` / `hq-panel` plan
folders were **built into the comms-board/live-board work** — they no longer exist as
separate folders. Only the parallel-fleet plans remain (below).

### Deferred polish
- artifact **edit-hooks + versioning** (`last_edit_*`/`version` columns exist, unpopulated)
- **consolidation** (fan-in / synthesis when a goal's frontier drains)
- **per-task ad-hoc Run** button (no backend route yet — TaskCard escape hatch)
- ✅ ~~goal-stop endpoint~~ — **done** (`/comms/goals/stop`, 2026-06-22)

## Separate later plans
- **HQ command center / fleet dashboard** → [HQ-COMMAND-CENTER.md](HQ-COMMAND-CENTER.md)
  ⚠ overlaps the existing `../parallel-fleet-part-2/` "Studio HQ Fleet Dashboard" — consolidate.
- **Parallel fleet** (worktree-per-lane + conservative merge agent) → existing plans
  `../parallel-fleet-part-1/` and `../parallel-fleet-part-2/`.

## At a glance
**0b + two-flow split + P1 + P2 are shipped**, so the end-to-end self-driving system for one
goal (decompose → run → verify) works **and is visible/controllable in Studio** (Goals & Tasks
view, executor selector, Decompose/Run/Stop), with multi-adapter routing riding along. **P3**
makes it parallel (k>1 by lane → worktree fan-in); the **HQ dashboard** is the last surface.
