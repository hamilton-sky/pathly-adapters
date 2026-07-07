# 03 — Artifact Map: planner-hierarchy (g1-feature-planner-decompose)

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| STATE.json | Orchestrator | Orchestrator | FSM checkpoint |
| EVENTS.jsonl | All agents | Studio, Retro | Event log (AGENT_DONE, PHASE_*) |
| ARTIFACTS.jsonl | All agents | Board, Studio | Artifact ledger |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| feedback/REVIEW_FAILURES.md | Reviewer (attempt 1) | Builder (interactive fix) | 4 doc-sync violations in src/pathly_data/CLAUDE.md — directory listing, no_defaults count, board-native exception list, manifest converted list |

---

## Source files changed

| File | What changed |
|---|---|
| `src/pathly_data/core/skills/planning/feature-decompose.md` | New skill (135 lines) — terminal emitter that reads a feature spec and posts 2-5 sibling goal cards to the feature board, with depends_on wiring and context_refs. Covers light/full/consultation tiers. |
| `src/pathly_data/core/skills/composition.yaml` | Registered feature-decompose with `no_defaults: true`, fragments: `comms-post` + `completion-report` |
| `src/pathly_data/CLAUDE.md` | 4 doc-sync updates: added feature-decompose to planning/ directory listing, incremented no_defaults count (8→9), added to board-native exception list, added to manifest converted list |

---

## Artifact flow diagram

```
feature spec (from board context)
       │
       ▼
planning/feature-decompose.md   ← new skill
       │
       ▼
composition.yaml                ← registered (no_defaults+comms-post+completion-report)
       │
       ▼
src/pathly_data/CLAUDE.md       ← doc-synced (4 locations)
       │
       ▼
RETRO.md                        ← what we learned
       │
       ▼
pathly/pipeline-walkthrough/planner-hierarchy/  ← metrics record → this folder
```
