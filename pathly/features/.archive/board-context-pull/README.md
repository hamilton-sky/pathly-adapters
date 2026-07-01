# board-context-pull — plan folder

Near-term, lower-risk quality wins for the comms-board / Goals-DAG system, to land
**before P3 (parallel)**. Three independently-shippable solutions plus housekeeping.

| Doc | What it covers |
|---|---|
| [SPEC.md](SPEC.md) | **The spec** — problem, solutions A/B/C, files touched, tests, sequencing |

## At a glance

- **A — catalog-pull affordance** (lead): tell agents they may browse + hydrate the
  artifact catalog scoped to their board permissions (`exposed_boards`). Turns today's
  push-only, k-capped context into push + pull. Mostly prompt-side; backend exists.
- **B — DAG task-duration & context-access trail**: `claimed_at`/`completed_at` columns →
  per-task duration + context-pull trail on the Goals & Tasks view.
- **C — context preview / "simulation" endpoint**: render what an agent *would* see for a
  task, read-only, with per-channel counts — review governance + scope before dispatch.
- **Housekeeping**: clear the stale `comms-board/STATE.json` `BUILDING` mirror.

Relates to [../comms-board/ROADMAP.md](../comms-board/ROADMAP.md) (everything shipped
except P3) and the parallel-fleet plans.
