# docs-sync — Feature Index

> **Read this first.** Every agent working on this feature should load this file
> before any other plan file. It maps every file in this folder and every
> codebase file this feature touches.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point |
| `USER_STORIES.md` | Planner | Tester, Reviewer | 5 stories — stale claims + missing sections |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder | Edit-by-edit fix instructions |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | 1 conversation prompt with verify commands |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status checkpoint |
| `RETRO.md` | Retro | Humans, /lessons | What we learned |
| `STATE.json` | Orchestrator | Orchestrator | FSM state snapshot |
| `EVENTS.jsonl` | Orchestrator | Retro, walkthrough | Full event log |

### Optional plan files
| File | Present? |
|---|---|
| `ARCHITECTURE_PROPOSAL.md` | no |
| `EDGE_CASES.md` | no |
| `HAPPY_FLOW.md` | no |
| `FLOW_DIAGRAM.md` | no |

---

## Codebase touchpoints

> **Verify these paths exist before editing.** Glob each one. Correct any discrepancy before proceeding.

| Codebase file | Conv | What changes |
|---|---|---|
| `docs/ARCHITECTURE.md` | 1 | Remove phantom materialize.py reference; add orchestrator/ row |
| `docs/PATHLY_ARCHITECTURE.md` | 1 | Fix install_cli/ paths; fix pathly_data/ → src/pathly_data/; add Python Package Layout section |
| `docs/MULTI_TOOL_DESIGN.md` | 1 | Replace pathly-engine monorepo tree with real single-repo layout |
| `docs/FLOW_DIAGRAM.md` | 1 | Fix adapter source paths to include src/pathly_data/ prefix |
| `docs/SECURITY.md` | 1 | Fix plugin manifest paths |
| `docs/SYSTEM_REVIEW.md` | 1 | Fix core/ and adapters/ paths to src/pathly_data/ prefix |
| `docs/PRODUCTION_READINESS.md` | 1 | Fix plugin manifest paths |

---

## Conversation map

| Conv | Title | Stories | Status | Key files |
|---|---|---|---|---|
| 1 | Fix stale claims + add missing sections | S1, S2, S3, S4, S5 | DONE | 7 docs files above |

---

## Feedback files (transient — deleted after resolution)

| File | Written by | Resolved by |
|---|---|---|
| `feedback/REVIEW_FAILURES.md` | Reviewer | Builder |
| `feedback/TEST_FAILURES.md` | Tester | Builder |
| `feedback/IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `feedback/DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `feedback/HUMAN_QUESTIONS.md` | Any agent | User |
