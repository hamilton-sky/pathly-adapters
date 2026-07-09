# 03 — Artifact Map: {{FEATURE}}

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading the
board task DAG and re-entering at the last incomplete task.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Planner | Exact code changes — the design |
| board task DAG (goal + tasks) | Planner | Builder agents | Per-task builder prompts + status — the work list and the checkpoint |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
{{FEEDBACK_FILE_ROWS}}

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
{{SOURCE_FILE_ROWS}}

---

## Artifact flow diagram

```
USER_STORIES.md          ←── what to build
       │
       ▼
IMPLEMENTATION_PLAN.md   ←── how to build it (one board task per phase)
       │
       ▼
board task DAG           ←── per-task builder prompts + status
       │
       ▼
RETRO.md                 ←── what we learned
       │
       ▼
lessons/LESSONS.md       ←── promoted patterns → next planner
pipeline-walkthrough/{{FEATURE}}/  ←── metrics record → this folder
```
