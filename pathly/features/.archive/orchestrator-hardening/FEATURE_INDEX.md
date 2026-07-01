# orchestrator-hardening — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | no | Lite rigor — architecture notes inlined into IMPLEMENTATION_PLAN.md |
| `EDGE_CASES.md` | no | Lite rigor — edge cases inlined into USER_STORIES.md |
| `HAPPY_FLOW.md` | no | Lite rigor — not needed for this hardening work |
| `FLOW_DIAGRAM.md` | no | Lite rigor — not needed for this hardening work |

---

## Context

This plan implements the 8 recommendations from the analysis of Pathly's orchestrator
and FSM code. Source: chat-thread analysis of `orchestrator/`, `hooks/`,
`protocol_contract.yaml`, and FSM usage in `src/pathly_data/core/`.

The work is documentation-and-infra hardening — no user-facing feature change.
After this plan, `orchestrator/` and `hooks/` either ship cleanly or are clearly
labeled as schema reference; STATE.json is validated; EVENTS.jsonl is concurrency-safe;
the cross-repo contract has version checking.

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `orchestrator/__init__.py` | Conv 1 | MOVE → `src/pathly_orchestrator/__init__.py` |
| `orchestrator/state.py` | Conv 1, 2 | MOVE in Conv 1; add validator + schema reference in Conv 2 |
| `orchestrator/events.py` | Conv 1 | MOVE → `src/pathly_orchestrator/events.py` |
| `orchestrator/eventlog.py` | Conv 1, 2 | MOVE in Conv 1; add file lock in Conv 2; add `_print_summary_main` entry in Conv 1 |
| `hooks/classify_feedback.py` | Conv 1, 3 | MOVE in Conv 1; tighten heuristic in Conv 3 |
| `hooks/inject_feedback_ttl.py` | Conv 1 | MOVE → `src/pathly_hooks/inject_feedback_ttl.py` |
| `pyproject.toml` | Conv 1 | Add `pathly_orchestrator*`, `pathly_hooks*` to `packages.find`; add `pathly-events`, `pathly-state` console scripts |
| `schemas/pathly-meta.schema.json` | (read only) | Reference pattern for new schema |
| `schemas/state.schema.json` | Conv 2 | CREATE — JSON Schema for STATE.json with state enum + transition table |
| `protocol_contract.yaml` | Conv 3 | Add `version` field + cross-repo version-check rule |
| `tests/test_hooks.py` | Conv 1, 3 | Update import paths after move; add classification-edge-case tests |
| `tests/test_feedback_protocol.py` | Conv 3 | Add version-mismatch test |
| `tests/test_orchestrator.py` | Conv 2 | CREATE — state/event schema tests + concurrency test for append |
| `README.md` | Conv 1, 4 | Mention `pathly-events`/`pathly-state` console scripts; note Claude-only hook surface |
| `docs/SECURITY.md` | Conv 4, 5 | Document hook parity gap; update to show deployed status after Conv 5 |
| `src/pathly_data/core/skills/team-flow.md` | Conv 4 | Update state model to per-stage iteration counter (if accepted) |
| `src/pathly_data/core/agents/README_routing.md` | (read only) | Cross-check FSM state references |
| `src/install_cli/materialize.py` | Conv 5 | Deploy hook files to Codex (`~/.codex/hooks.json`) and Copilot VS Code (`.github/hooks/`) |
| `src/pathly_data/adapters/codex/install.yaml` | Conv 5 | Update hook event name to `PostToolUse`; add `apply_patch` matcher |
| `src/pathly_data/adapters/copilot/install.yaml` | Conv 5 | Update hook event name to `PostToolUse`; add platform-keyed command format |
| `tests/test_materialize_hooks.py` | Conv 5 | CREATE — assert hook files written and cleaned up for each host |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Ship orchestrator + hooks as real packages | S1, S4 | DONE | `src/pathly_orchestrator/*`, `src/pathly_hooks/*`, `pyproject.toml`, `tests/test_hooks.py` |
| 2 | FSM hardening: STATE.json schema + EVENTS.jsonl concurrency | S2, S3 | TODO | `schemas/state.schema.json`, `src/pathly_orchestrator/state.py`, `eventlog.py`, `tests/test_orchestrator.py` |
| 3 | Contract integrity: classify hook + protocol version | S5, S6 | TODO | `src/pathly_hooks/classify_feedback.py`, `protocol_contract.yaml`, `tests/test_feedback_protocol.py` |
| 4 | Cross-host hook parity docs + per-stage iteration | S7, S8 | TODO | `docs/SECURITY.md`, `README.md`, `src/pathly_data/core/skills/team-flow.md` |
| 5 | Deploy hooks to Codex + Copilot VS Code | S9, S7 | TODO | `src/install_cli/materialize.py`, `codex/install.yaml`, `copilot/install.yaml`, `tests/test_materialize_hooks.py` |

---

## Feedback files (transient — deleted after resolution)

Live in `plans/orchestrator-hardening/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
