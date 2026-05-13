# Pipeline Walkthrough — docs-sync

_Generated: 2026-05-11 | Rigor: lite | Conversations: 1_

This folder is the metrics record for the **docs-sync** team-flow pipeline run.
It documents every agent spawn, feedback loop, token cost, and artifact produced.

---

## Files in this folder

| File | What it answers |
|---|---|
| [01-PIPELINE-FLOW.md](01-PIPELINE-FLOW.md) | Every agent spawn and feedback loop, in execution order |
| [02-TOKEN-USAGE.md](02-TOKEN-USAGE.md) | Token counts per agent, totals, and cost drivers |
| [03-ARTIFACT-MAP.md](03-ARTIFACT-MAP.md) | Every file produced or consumed, its role, and who owns it |

---

## Live artifacts (primary evidence)

| Artifact | Stage | Role |
|---|---|---|
| [plans/docs-sync/USER_STORIES.md](../../plans/docs-sync/USER_STORIES.md) | Planning | Acceptance criteria |
| [plans/docs-sync/IMPLEMENTATION_PLAN.md](../../plans/docs-sync/IMPLEMENTATION_PLAN.md) | Planning | Exact code changes |
| [plans/docs-sync/CONVERSATION_PROMPTS.md](../../plans/docs-sync/CONVERSATION_PROMPTS.md) | Planning | Verbatim builder prompts |
| [plans/docs-sync/PROGRESS.md](../../plans/docs-sync/PROGRESS.md) | Pipeline | Conversation status |
| [plans/docs-sync/RETRO.md](../../plans/docs-sync/RETRO.md) | Retro | Human retrospective |
| [lessons/LESSONS_CANDIDATE.md](../../lessons/LESSONS_CANDIDATE.md) | Lessons | Candidate patterns for next planner |

---

## Pipeline shape

```
/pathly go docs-sync
    └─► director → team-flow (lite rigor)
            ├─ discovery     skipped (user chose path 2)
            ├─ planning      1 planner spawn, 4 plan files
            ├─ build/review  1 conversation, 2 review loops (REVIEW_FAILURES.md ×2)
            ├─ test          1 tester spawn, 1 inline fix (path label)
            └─ retro         → this folder scaffolded
```
