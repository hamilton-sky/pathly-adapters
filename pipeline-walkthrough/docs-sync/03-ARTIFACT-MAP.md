# 03 — Artifact Map: docs-sync

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading
PROGRESS.md and re-entering at the last incomplete conversation.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Builder | Exact doc changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Builder | Orchestrator | Conversation status — the checkpoint |
| RETRO.md | Retro | Humans, /lessons | What we learned — the feedback loop |
| STATE.json | Orchestrator | Orchestrator | FSM state snapshot |
| EVENTS.jsonl | Orchestrator | Retro, walkthrough | Full event log |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| feedback/REVIEW_FAILURES.md (×2) | Reviewer | Builder | Stale path prefixes; invented package names |
| feedback/HUMAN_QUESTIONS.md | Orchestrator | Orchestrator (grep confirmed resolved) | Retry limit escalation — violations confirmed absent |
| feedback/TEST_FAILURES.md | Tester | Orchestrator (inline fix) | pathly_data/ label missing src/ prefix on line 40 |

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `docs/ARCHITECTURE.md` | S1, S5 | install_cli/ paths prefixed with src/; orchestrator/ row added |
| `docs/PATHLY_ARCHITECTURE.md` | S1, S3, S4 | install_cli/ and pathly_data/ paths fixed; Python Package Layout section added |
| `docs/MULTI_TOOL_DESIGN.md` | S2 | pathly-engine monorepo replaced with real single-repo layout |
| `docs/FLOW_DIAGRAM.md` | S2 | pathly-engine CLI node replaced; adapter source paths prefixed |
| `docs/SECURITY.md` | S1 | Plugin manifest paths prefixed with src/pathly_data/ |
| `docs/SYSTEM_REVIEW.md` | S1 | core/ and adapters/ paths prefixed with src/pathly_data/ |
| `docs/PRODUCTION_READINESS.md` | S1 | Plugin manifest paths prefixed with src/pathly_data/ |

---

## Artifact flow diagram

```
USER_STORIES.md          ←── what to fix (5 stale claims + missing sections)
       │
       ▼
IMPLEMENTATION_PLAN.md   ←── which lines in which files to change
       │
       ▼
CONVERSATION_PROMPTS.md  ←── exact builder prompt (verify-then-edit pattern missing ← lesson)
       │
       ▼
PROGRESS.md              ←── Conv 1 DONE
       │
       ▼
RETRO.md                 ←── 3 lessons extracted
       │
       ▼
lessons/LESSONS_CANDIDATE.md  ←── 3 candidate patterns → promote via /lessons
pipeline-walkthrough/docs-sync/  ←── this folder
```
