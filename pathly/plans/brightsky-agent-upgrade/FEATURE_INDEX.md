---
name: Feature Index
---
# BrightSky Agent Upgrade — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — 11 stories across 4 conversations |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — 14 phases across 4 conversations |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |

### Optional plan files (present)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-repo design decisions: WebSocket tool bridge, Gemini thinking, IPC channel pattern, search tool routing |
| `EDGE_CASES.md` | yes | Failure modes: stream_end without thinking, tool timeout, missing plan folder |
| `HAPPY_FLOW.md` | yes | Golden-path: agent lists plans, reads failures, responds with reasoning box |
| `FLOW_DIAGRAM.md` | yes | Multi-component: Studio ↔ BrightSky tool round-trip + thinking stream |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

### pathly-adapters repo (C:\Users\Yafit\pathly-adapters)

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/renderer/src/lib/studioAnalyzer.ts` | Conv 1 | Add 6 new tool handlers: list_plans, get_events, get_failures, create_plan, navigate_to, get_layout |
| `studio/src/renderer/src/lib/studioAnalyzer.ts` | Conv 2 | Add run_skill handler using new `window.pathly.fsm.runSkill` IPC |
| `studio/src/main/ipc/fsm.ts` | Conv 2 | Add `fsm:runSkill` IPC handler — POST to FSM `/runner/start` |
| `studio/src/main/preload/index.ts` | Conv 2 | Expose `window.pathly.fsm.runSkill(topic, skill, projectPath)` |
| `studio/src/renderer/src/types/global.d.ts` | Conv 2 | Add `fsm.runSkill` type signature |
| `studio/src/renderer/src/lib/brightskyClient.ts` | Conv 2 | Fix stream_end: call splitThinkingContent to populate msg.thinking for Reasoning box |

### brightsky-ai repo (C:\Users\Yafit\brightsky-ai)

| Codebase file | Conversation | What changes |
|---|---|---|
| `backend/src/mcp/tools/studio-bridge-tool.ts` | Conv 3 | Add 7 new StudioBridgeTool subclasses (list_plans, get_events, get_failures, create_plan, navigate_to, run_skill, get_layout) |
| `backend/src/mcp/mcp.module.ts` | Conv 3 | Register all 7 new tools in tool provider array (near line 365) |
| `backend/src/services/unified-ai.service.ts` | Conv 3 | Pin provider to Gemini for pathly_chat; enable web_search, youtube_search, youtube_transcript in Pathly tool set |
| `backend/src/services/gemini.service.ts` | Conv 4 | Add `thinkingConfig: { thinkingBudget: 8000 }` to generateContentStream for pathly_chat messages |
| `backend/src/chat/gateways/session/services/reasoning-timer.service.ts` | Conv 4 | Guard: skip synthetic steps for pathly_chat; route Gemini thinking parts as `<think>` stream_chunks |

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Studio: 6 read/write tools + layout | S-01–S-06 | TODO | `studioAnalyzer.ts` |
| 2 | Studio: run_skill IPC + reasoning box | S-07, S-08 | TODO | `studioAnalyzer.ts`, `fsm.ts`, `preload/index.ts`, `global.d.ts`, `brightskyClient.ts` |
| 3 | BrightSky: register 7 tools + search routing | S-09, S-10 | TODO | `studio-bridge-tool.ts`, `mcp.module.ts`, `unified-ai.service.ts` |
| 4 | BrightSky: Gemini thinking stream | S-11 | TODO | `gemini.service.ts`, `reasoning-timer.service.ts` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/brightsky-agent-upgrade/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
