# visible-runner — Progress

## Status: IN PROGRESS

## Story Status

| Story | Title | Delivered by | Status |
|---|---|---|---|
| S1 | Live terminal tab per stage | Conv 1+2 | TODO |
| S2 | User can type to intervene | Conv 2 | TODO |
| S3 | Runner lifecycle controls with terminal tabs | Conv 1+2 | TODO |
| S4 | RunnerLogCard in HQ chat | Conv 3 | TODO |
| S5 | Live jump button | Conv 3 | TODO |
| S6 | Decision point visibility | Conv 3 | TODO |
| S7 | Headless fallback | Conv 1 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|---|---|---|---|---|
| 1 | 0–3 | S1, S3, S7 | DONE | `python -m pytest tests/ -q` |
| 2 | 4–9 | S1, S2, S3 | TODO | `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json && node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json` |
| 3 | 10–13 | S4, S5, S6 | TODO | `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|---|---|---|---|---|---|
| 1 | 0 Pre-flight | `src/pathly_orchestrator/supervisor.py` | Run pytest baseline | `python -m pytest tests/ -q` exits 0 | DONE |
| 1 | 1 Extract argv builder | `src/pathly_orchestrator/runner.py` | `resolve_argv()` function extracted | `grep -n "def resolve_argv" src/pathly_orchestrator/runner.py` returns match | DONE |
| 1 | 2 HTTP endpoints | `src/pathly_orchestrator/http_server.py` | Add `/runner/terminal/started` + `/runner/terminal/result` | curl to `/runner/terminal/started` returns `{"ok":true}` | DONE |
| 1 | 3 _loop refactor | `src/pathly_orchestrator/supervisor.py` | Add `_run_stage_via_terminal()` with threading.Event and fallback | `grep -n "_run_stage_via_terminal\|TERMINAL_SPAWN" src/pathly_orchestrator/supervisor.py` returns matches | DONE |
| 2 | 4 CSS tokens | `studio/src/renderer/src/styles/tokens.css` | Add `--runner-bg` + `--runner-border` | `grep -n "runner-bg" studio/src/renderer/src/styles/tokens.css` returns 2+ matches | TODO |
| 2 | 5 TerminalTab type | `studio/src/renderer/src/types/terminal.ts` | Add `runnerOwned?: boolean` | grep for field returns match | TODO |
| 2 | 6 runnerStore additions | `studio/src/renderer/src/store/runnerStore.ts` | Add stageLog, activeRunnerTabId, logCardExpanded | grep for all 3 fields returns matches | TODO |
| 2 | 7 useHQ SSE handlers | `studio/src/renderer/src/components/HQ/useHQ.tsx` | Handle TERMINAL_SPAWN + TERMINAL_SIGNAL | grep for both event names returns matches | TODO |
| 2 | 8 terminal.ts result POST | `studio/src/main/ipc/terminal.ts` | Buffer PTY output; POST result on exit | grep for `/runner/terminal/result` returns match | TODO |
| 2 | 9 PaneTabBar styling | `studio/src/renderer/src/components/Terminal/PaneTabBar.tsx` | runnerOwned tab CSS class | grep for `runnerOwned\|runnerTab` returns matches | TODO |
| 3 | 10 RunnerLogCard | `studio/src/renderer/src/components/HQ/RunnerLogCard/RunnerLogCard.tsx` | New flat card component | file exists + typecheck passes | TODO |
| 3 | 11 Live button | `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` | [live ↗] pill button | grep for `liveBtn` returns match | TODO |
| 3 | 12 DECISION_MENU | `studio/src/renderer/src/components/HQ/useHQ.tsx` | Auto-expand + toast | grep for `waiting for your decision` returns match | TODO |
| 3 | 13 Wire LogCard | `studio/src/renderer/src/components/HQ/HQPanel.tsx` | Mount RunnerLogCard in panel | grep for `RunnerLogCard` in HQPanel returns match | TODO |

## Prerequisites

- `python -m pytest tests/ -q` exits 0 before Conv 1 begins
- Studio typechecks clean before Conv 2: `npm run typecheck`

## Blocked By

- Nothing
