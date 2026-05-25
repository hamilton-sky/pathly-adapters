# pathly-runner — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## What is pathly-runner?

`pathly-runner` adds a `pathly-run <topic>` CLI command that drives the Pathly FSM autonomously from the current state all the way to DONE. Rather than requiring a human to manually invoke each builder conversation, the runner loops over `_next_action` and `_complete_stage` from `http_server.py`, invokes the correct agent via a `claude -p` subprocess for each stage, surfaces human checkpoints and decide blocks interactively in the terminal, and writes every state transition to EVENTS.jsonl so the Studio Monitor picks them up automatically via its existing SSE tail — no extra wiring needed.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Architect, Builder | Component structure, data flow, key decisions |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder | Phase-by-phase design — the what and how |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `CONVERSATION_PROMPTS.md` | no | Inline into IMPLEMENTATION_PLAN.md for this feature |
| `EDGE_CASES.md` | no | Edge cases inlined into USER_STORIES.md |
| `HAPPY_FLOW.md` | no | Not needed — flow is fully described in ARCHITECTURE_PROPOSAL.md |
| `FLOW_DIAGRAM.md` | no | Diagram inlined into ARCHITECTURE_PROPOSAL.md |

---

## Stories

| Story | Title | Status |
|---|---|---|
| S1 | `pathly-run <topic>` drives FSM autonomously from current state to DONE | TODO |
| S2 | Each stage's agent output streams to terminal in real-time | TODO |
| S3 | Studio shows live progress while runner is active (no extra wiring needed) | TODO |
| S4 | Human checkpoints pause runner, print question, resume after user confirms | TODO |
| S5 | Decide blocks surface options to user in terminal, runner waits for choice | TODO |
| S6 | `--flow`, `--rigor`, `--model`, `--project-root` flags | TODO |
| S7 | Runner recovers from STATE.json on restart (resume interrupted runs) | TODO |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_orchestrator/runner.py` | Conv 1, 2, 3 | CREATE in Conv 1; replace invoke_agent stub in Conv 2; add resolve_stage in Conv 3 |
| `pyproject.toml` | Conv 1 | Add `pathly-run` entry point |
| `tests/test_runner.py` | Conv 4 | CREATE — unit tests with mocks |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Runner skeleton + FSM loop (no Claude) | S1 partial, S6, S7 | TODO | `src/pathly_orchestrator/runner.py`, `pyproject.toml` |
| 2 | Claude subprocess integration | S1 complete, S2 | TODO | `src/pathly_orchestrator/runner.py` |
| 3 | Human checkpoints + feedback loop | S4, S5 | TODO | `src/pathly_orchestrator/runner.py` |
| 4 | Tests | — | TODO | `tests/test_runner.py` |

---

## Feedback files (transient — deleted after resolution)

Live in `plans/pathly-runner/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
