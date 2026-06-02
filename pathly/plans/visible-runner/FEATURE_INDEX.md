# visible-runner — Feature Index

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
| `HAPPY_FLOW.md` | Planner | Builder | Golden-path narrative |
| `EDGE_CASES.md` | Planner | Builder, Tester | Failure modes and risk scenarios |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Architect, Builder | Cross-layer design contracts |
| `FLOW_DIAGRAM.md` | Planner | Builder | Inter-process interaction diagram |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-layer design decisions |
| `EDGE_CASES.md` | yes | Failure modes and risk scenarios |
| `HAPPY_FLOW.md` | yes | Golden-path narrative |
| `FLOW_DIAGRAM.md` | yes | Multi-component interaction diagram |

---

## Codebase touchpoints

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

| Codebase file | Conv | What changes |
|---|---|---|
| `src/pathly_orchestrator/supervisor.py` | 1 | Add `_run_stage_via_terminal()`, threading.Event wait, TERMINAL_SPAWN/SIGNAL broadcasts, headless fallback |
| `src/pathly_orchestrator/http_server.py` | 1 | Add `POST /runner/terminal/started` and `POST /runner/terminal/result` endpoints |
| `src/pathly_orchestrator/runner.py` | 1 | Extract argv builder into `resolve_argv()`, keep `invoke_agent` as headless path |
| `studio/src/renderer/src/styles/tokens.css` | 2 | Add `--runner-bg` and `--runner-border` to all theme blocks |
| `studio/src/renderer/src/store/runnerStore.ts` | 2 | Add `stageLog`, `activeRunnerTabId`, `logCardExpanded`; actions `recordStageStart`, `recordStageEnd`, `setActiveRunnerTabId`, `setLogCardExpanded` |
| `studio/src/renderer/src/store/terminalStore.ts` | 2 | No changes — used as-is via `addTab` + `openTab` |
| `studio/src/renderer/src/types/terminal.ts` | 2 | Add `runnerOwned?: boolean` field to `TerminalTab` type |
| `studio/src/main/ipc/terminal.ts` | 2 | Buffer PTY output; on exit extract last JSON line and POST to `/runner/terminal/result` |
| `studio/src/renderer/src/components/HQ/useHQ.tsx` | 2 | Handle `TERMINAL_SPAWN` and `TERMINAL_SIGNAL` SSE events |
| `studio/src/renderer/src/components/Terminal/PaneTabBar.tsx` | 2 | Add `runnerOwned` tab visual treatment (`.runnerTab` CSS class) |
| `studio/src/renderer/src/components/HQ/RunnerLogCard/RunnerLogCard.tsx` | 3 | New component — flat sticky card with stage history |
| `studio/src/renderer/src/components/HQ/RunnerLogCard/RunnerLogCard.module.css` | 3 | New CSS module |
| `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` | 3 | Add `[live ↗]` button when `status === 'running'` |
| `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.module.css` | 3 | Add `.liveBtn` style |

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Backend contracts | S1, S3, S7 | TODO | `supervisor.py`, `http_server.py`, `runner.py` |
| 2 | Studio wiring | S1, S2, S3 | TODO | `terminal.ts`, `useHQ.tsx`, `PaneTabBar.tsx`, `runnerStore.ts`, `tokens.css` |
| 3 | RunnerLogCard + polish | S4, S5, S6 | TODO | `RunnerLogCard/`, `StageStatusStrip.tsx` |

---

## Feedback files (transient — deleted after resolution)

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |

---

## Key architecture decisions (read before touching any file)

1. **Option E SSE relay**: Supervisor broadcasts `TERMINAL_SPAWN` SSE → Studio opens tab + spawns PTY → Studio POSTs `/runner/terminal/result` when PTY exits. No direct cross-process calls.
2. **Headless fallback**: If no Studio client receives `TERMINAL_SPAWN` within 5 seconds (no `/runner/terminal/started` callback), supervisor falls back to `invoke_agent()`. Pipeline never blocks on UI.
3. **Abort via SSE**: Supervisor broadcasts `TERMINAL_SIGNAL {signal:"term"}` → Studio calls `window.pathly.terminal.kill(tabId)`. Supervisor never holds the PTY PID.
4. **Pause between stages only**: No mid-stage PTY pause. `_pause_flag` is checked at stage boundaries as today.
5. **New tab per stage**: Each stage opens a new terminal tab (preserves scroll history). Tabs stay open after pipeline ends.
6. **Result extraction**: Studio buffers PTY output; on PTY exit, walks buffer backwards for last valid JSON line and POSTs it to `/runner/terminal/result`.
