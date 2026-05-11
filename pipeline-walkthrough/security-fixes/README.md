# Pipeline Walkthrough — security-fixes

This folder documents a real team-flow pipeline run from start to finish,
using the `security-fixes` feature as a concrete example.

It covers:
- How the pipeline stages connect and what each agent does
- How agents communicate (they never talk to each other directly — files on disk are the medium)
- What each artifact file is for and where it lives
- Token usage per agent and total

---

## Files in this folder

| File | What it answers |
|---|---|
| [01-PIPELINE-FLOW.md](01-PIPELINE-FLOW.md) | What happened, in order — every agent spawn, every feedback loop, every gate |
| [02-TOKEN-USAGE.md](02-TOKEN-USAGE.md) | Token counts per agent, totals, and what drove the cost |
| [03-ARTIFACT-MAP.md](03-ARTIFACT-MAP.md) | Every file produced or consumed, its role, and who owns it |

---

## Live artifacts (the actual evidence)

These are the real files written during the run. They are not copies — they are the primary record.

| Artifact | Stage that produced it | Role |
|---|---|---|
| [plans/security-fixes/USER_STORIES.md](../security-fixes/USER_STORIES.md) | Planning | What to build — 6 stories with acceptance criteria |
| [plans/security-fixes/IMPLEMENTATION_PLAN.md](../security-fixes/IMPLEMENTATION_PLAN.md) | Planning | How to build it — exact code locations and snippets |
| [plans/security-fixes/CONVERSATION_PROMPTS.md](../security-fixes/CONVERSATION_PROMPTS.md) | Planning | Verbatim prompts given to each builder agent |
| [plans/security-fixes/PROGRESS.md](../security-fixes/PROGRESS.md) | Pipeline | Running status — which conversations are DONE |
| [plans/security-fixes/RETRO.md](../security-fixes/RETRO.md) | Retro | Human-readable retrospective for the next pipeline run |
| [lessons/LESSONS.md](../../lessons/LESSONS.md) | Lessons | Promoted patterns — planner reads this before every new plan |

---

## How pathly pipeline relates to these docs

```
/pathly go <feature>
    └─► director classifies intent → team-flow skill
            └─► orchestrator (deterministic FSM)
                    ├─► spawns agents in sequence
                    ├─► writes plan files as checkpoints
                    ├─► routes feedback files between agents
                    └─► advances only when guards pass
```

The plan files are not just documentation — they are the FSM's persistent state.
An interrupted pipeline can be resumed by reading PROGRESS.md and re-entering at the
last incomplete conversation.
