# Pipeline Walkthrough — {{FEATURE}}

_Generated: {{DATE}} | Rigor: {{RIGOR}} | Conversations: {{CONV_COUNT}}_

This folder is the metrics record for the **{{FEATURE}}** team pipeline run.
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
| [pathly/features/{{FEATURE}}/USER_STORIES.md](../../pathly/features/{{FEATURE}}/USER_STORIES.md) | Planning | Acceptance criteria |
| [pathly/features/{{FEATURE}}/IMPLEMENTATION_PLAN.md](../../pathly/features/{{FEATURE}}/IMPLEMENTATION_PLAN.md) | Planning | Exact code changes |
| [pathly/features/{{FEATURE}}/CONVERSATION_PROMPTS.md](../../pathly/features/{{FEATURE}}/CONVERSATION_PROMPTS.md) | Planning | Verbatim builder prompts |
| [pathly/features/{{FEATURE}}/PROGRESS.md](../../pathly/features/{{FEATURE}}/PROGRESS.md) | Pipeline | Conversation status |
| [pathly/features/{{FEATURE}}/RETRO.md](../../pathly/features/{{FEATURE}}/RETRO.md) | Retro | Human retrospective |
| [lessons/LESSONS.md](../../lessons/LESSONS.md) | Lessons | Promoted patterns for next planner |

---

## Pipeline shape

```
/pathly go {{FEATURE}}
    └─► director → team ({{RIGOR}} rigor)
            ├─ discovery     {{DISCOVERY_NOTE}}
            ├─ planning      {{PLANNING_NOTE}}
            ├─ build/review  {{CONV_COUNT}} conversations, {{REVIEW_LOOPS}} review loops
            ├─ test          {{TEST_RUNS}} test runs, {{TEST_LOOPS}} fix loops
            └─ retro         → this folder scaffolded
```
