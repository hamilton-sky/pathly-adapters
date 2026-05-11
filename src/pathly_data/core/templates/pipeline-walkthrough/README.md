# Pipeline Walkthrough — {{FEATURE}}

_Generated: {{DATE}} | Rigor: {{RIGOR}} | Conversations: {{CONV_COUNT}}_

This folder is the metrics record for the **{{FEATURE}}** team-flow pipeline run.
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
| [plans/{{FEATURE}}/USER_STORIES.md](../../plans/{{FEATURE}}/USER_STORIES.md) | Planning | Acceptance criteria |
| [plans/{{FEATURE}}/IMPLEMENTATION_PLAN.md](../../plans/{{FEATURE}}/IMPLEMENTATION_PLAN.md) | Planning | Exact code changes |
| [plans/{{FEATURE}}/CONVERSATION_PROMPTS.md](../../plans/{{FEATURE}}/CONVERSATION_PROMPTS.md) | Planning | Verbatim builder prompts |
| [plans/{{FEATURE}}/PROGRESS.md](../../plans/{{FEATURE}}/PROGRESS.md) | Pipeline | Conversation status |
| [plans/{{FEATURE}}/RETRO.md](../../plans/{{FEATURE}}/RETRO.md) | Retro | Human retrospective |
| [lessons/LESSONS.md](../../lessons/LESSONS.md) | Lessons | Promoted patterns for next planner |

---

## Pipeline shape

```
/pathly go {{FEATURE}}
    └─► director → team-flow ({{RIGOR}} rigor)
            ├─ discovery     {{DISCOVERY_NOTE}}
            ├─ planning      {{PLANNING_NOTE}}
            ├─ build/review  {{CONV_COUNT}} conversations, {{REVIEW_LOOPS}} review loops
            ├─ test          {{TEST_RUNS}} test runs, {{TEST_LOOPS}} fix loops
            └─ retro         → this folder scaffolded
```
