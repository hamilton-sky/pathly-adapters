# Run Executor Headless Assessment

## Issue

Goal-card runs are meant to spawn a headless CLI stage: a visible PTY tab opens, but the agent runs one-shot with no terminal input. The current UI made that look interactive in at least one key surface.

## Verified Behavior

- The goal executor backend already forces `interactive=False` for goal-card team runs in `src/pathly_orchestrator/supervisor/goal_executor.py:349-352`.
- The terminal bridge reads the spawn payload's `interactive` flag in `studio/src/renderer/src/components/TerminalSpawnListener.tsx:62`.
- Electron already treats runner tabs with no `initialInput` as headless one-shots in `studio/src/main/ipc/terminal.ts` and uses the non-interactive runner shell path, so the PTY exits when the agent finishes.

## Root Cause

The renderer was not preserving terminal mode on the tab model. `TerminalSpawnListener` received the correct `interactive` flag from the spawn event, but the tab model did not store it, and `MiniTerminalCard` fell back to showing every running runner tab as `interactive`. That made headless goal-card runs look like live interactive sessions even though the backend behavior was correct.

## Fix

- Added `mode?: 'headless' | 'interactive'` to `studio/src/renderer/src/types/terminal.ts`.
- Threaded the mode through `studio/src/renderer/src/store/terminalStore.ts` so spawned tabs retain their actual run mode.
- Set tab mode from `TERMINAL_SPAWN.interactive` in `studio/src/renderer/src/components/TerminalSpawnListener.tsx:65-73`.
- Updated `studio/src/renderer/src/components/HQ/MiniTerminalCard/MiniTerminalCard.tsx:101-104` to show `headless` for running headless tabs instead of assuming `interactive`.
- Updated `studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.tsx` tooltip copy so headless is described as a visible PTY one-shot with no terminal input, which matches the real runtime.

## Verification

- `cmd /c npm run typecheck` in `studio/` passed.
- The executor path remains unchanged: goal-card runs still open a visible PTY tab, but they stay headless because no prompt is injected and the non-interactive runner shell path is used.
- The renderer now reflects the actual spawn mode instead of inferring `interactive` from `running`.
