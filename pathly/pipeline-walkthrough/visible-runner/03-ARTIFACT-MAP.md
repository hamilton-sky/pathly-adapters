# 03 — Artifact Map: visible-runner

Every file produced or consumed during this pipeline run.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Builder agents | Exact code changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| RETRO.md | Retro | Humans | What we learned |

---

## Transient feedback files (deleted after resolution)

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| feedback/REVIEW_FAILURES.md (×2) | Reviewer (rounds 1) | Builder (fix passes) | Conv 2: mode field + recordStageStart + tab_id; Conv 3: hardcoded rgba + dead cardRunning class |
| feedback/TEST_FAILURES.md | Tester | Builder (2 builders in parallel) | 6 failing ACs: banner label, green dot, first-focus warning, abort SSE, multi-run history |

---

## Source files changed

### Python backend

| File | Stories | What changed |
|---|---|---|
| `src/pathly_orchestrator/runner.py` | S1, S7 | `resolve_argv()` extracted; `parse_result(adapter, raw)` extracted; `handle_decide(interactive=True)` |
| `src/pathly_orchestrator/http_server.py` | S1, S3 | `POST /runner/terminal/started`; `POST /runner/terminal/result` (adapter-aware); `run_id` in /runner/start response |
| `src/pathly_orchestrator/supervisor.py` | S1, S3, S7 | `_run_stage_via_terminal()` with spawn/wait/fallback; `active_tab_id` field; `abort_run()` broadcasts TERMINAL_SIGNAL; `start_run()` broadcasts RUN_STARTED; TERMINAL_SPAWN/RUNNER_WARNING SSE |

### Studio — Electron main process

| File | Stories | What changed |
|---|---|---|
| `studio/src/main/ipc/terminal.ts` | S1, S2, S3 | PTY output buffer; done/aborted banner with label; result POST on exit; `runnerWarnShown` first-focus ANSI warning; `runnerTabMeta` with label field |
| `studio/src/main/preload/index.ts` | S1 | `registerRunner(tabId, topic, runId, label?)` — added label param |

### Studio — React renderer

| File | Stories | What changed |
|---|---|---|
| `studio/src/renderer/src/styles/tokens.css` | S1 | `--runner-bg`, `--runner-border`, `--runner-bg-active` in all 11 theme blocks |
| `studio/src/renderer/src/types/terminal.ts` | S1 | `runnerOwned?: boolean` on TerminalTab |
| `studio/src/renderer/src/types/global.d.ts` | S1 | `registerRunner(tabId, topic, runId, label?)` — added label param |
| `studio/src/renderer/src/store/terminalStore.ts` | S1 | `updateTabStatus(id, status)` action |
| `studio/src/renderer/src/store/runnerStore.ts` | S4, S5, S6 | `stageLog` (with mode field), `activeRunnerTabId`, `logCardExpanded`, `runStartedAt`, `runHistory`, `attachTerminalToStage`, `snapshotRun`, `jumpToLiveTab` |
| `studio/src/renderer/src/components/HQ/useHQ.tsx` | S1–S6 | TERMINAL_SPAWN, TERMINAL_SIGNAL, RUNNER_WARNING, STAGE_CHANGE, DECISION_MENU, RUN_STARTED SSE handlers |
| `studio/src/renderer/src/components/HQ/index.tsx` | S4 | RunnerLogCard mounted; runHistory historical cards rendered |
| `studio/src/renderer/src/components/HQ/RunnerLogCard/RunnerLogCard.tsx` | S4, S5 | New component — collapsed/expanded toggle, live/jump buttons, historicalRun prop |
| `studio/src/renderer/src/components/HQ/RunnerLogCard/RunnerLogCard.module.css` | S4 | Card, headerRow, dot, table, footer, jumpBtn styles |
| `studio/src/renderer/src/components/HQ/RunnerLogCard/RunnerLogRow.tsx` | S4 | Extracted sub-component for table rows |
| `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` | S5 | [live ↗] pill button when running |
| `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.module.css` | S5 | `.liveBtn` with runner token vars |
| `studio/src/renderer/src/components/Terminal/PaneTabBar.tsx` | S1 | `runnerOwned` → `.tabRunner` CSS class applied |
| `studio/src/renderer/src/components/Terminal/Terminal.module.css` | S1 | `.tabRunner`, `.tabRunner:hover` styles |
| `studio/src/renderer/src/components/Terminal/index.tsx` | S1 | `updateTabStatus(tabId, 'done')` on terminal:exit |
