---

---
# 01 — Pipeline Flow: {{FEATURE}}

_Date: {{DATE}} | Branch: {{BRANCH}}_

Every agent spawn, feedback loop, and gate — in execution order.

---

## Execution trace

```
User intent: "{{USER_INTENT}}"
│
│  [Stage 0 — Discovery]
{{DISCOVERY_TRACE}}
│
│  [Stage 1 — Planning]
├─► Planner agent
│   Produces:
│     plans/{{FEATURE}}/USER_STORIES.md
│     plans/{{FEATURE}}/IMPLEMENTATION_PLAN.md
│     plans/{{FEATURE}}/CONVERSATION_PROMPTS.md
│     plans/{{FEATURE}}/PROGRESS.md
│
{{ARCHITECT_CONSULT_TRACE}}
│  [Stage 2–3 — Build + Review]
│
{{CONVERSATION_TRACES}}
│
│  [Stage 4 — Test]
{{TEST_TRACES}}
│
│  [Stage 5 — Retro]
└─► Retro agent
    Writes: plans/{{FEATURE}}/RETRO.md
            pipeline-walkthrough/{{FEATURE}}/  ← this folder
```

---

## How agents communicate

Agents never call each other. The orchestrator is the only router.
Communication happens via files on disk:

| File | Written by | Resolved by | Means |
|---|---|---|---|
| `CONSULT_architect.md` | Architect | Builder (deletes) | Pre-build findings to incorporate |
| `REVIEW_FAILURES.md` | Reviewer | Builder (deletes) | Implementation must change |
| `TEST_FAILURES.md` | Tester | Builder or user (deletes) | Stories not satisfied |
| `HUMAN_QUESTIONS.md` | Any agent | User | Pipeline blocked on human decision |

---

## Feedback loop summary

| Stage | Loops | Cause | Resolution |
|---|---|---|---|
{{FEEDBACK_LOOP_TABLE}}

---

## FSM states traversed

```
{{FSM_STATES}}
```
