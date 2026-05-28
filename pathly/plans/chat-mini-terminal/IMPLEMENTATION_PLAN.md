# Implementation Plan

## Conversation 1 - Interactive Mini Terminal Core

Goal: Replace passive expanded output snippets with an interactive xterm-backed mini terminal attached to the same PTY tab.

Tasks:

1. Add renderer terminal scrollback buffering keyed by terminal tab id.
2. Update `writeToTerminal(...)` integration so `ChatPanel` keeps the active tab id for each target.
3. Create `MiniTerminalCard.tsx` in `components/ChatPanel`.
4. Reuse the xterm setup pattern from `TerminalTabView.tsx`:
   - create a local xterm instance,
   - replay buffered output,
   - subscribe to `window.pathly.terminal.onData(tabId, ...)`,
   - write xterm input through `window.pathly.terminal.write(tabId, data)`,
   - fit on mount and resize.
5. Replace expanded `OutputSnippet` usage with `MiniTerminalCard` for the active target.
6. Add an "open full terminal" button that opens the bottom terminal and selects the same tab.

Files likely touched:

- `studio/src/renderer/src/components/ChatPanel/index.tsx`
- `studio/src/renderer/src/components/ChatPanel/OutputSnippet.tsx`
- `studio/src/renderer/src/components/ChatPanel/OutputSnippet.module.css`
- `studio/src/renderer/src/components/ChatPanel/MiniTerminalCard.tsx`
- `studio/src/renderer/src/components/ChatPanel/MiniTerminalCard.module.css`
- `studio/src/renderer/src/store/terminalStore.ts`
- `studio/src/renderer/src/lib/launchTerminal.ts`

Verification:

- `npm.cmd run typecheck`
- `npm.cmd test`

## Conversation 2 - Polish And Safety

Goal: Make the mini terminal ergonomic inside the chat panel.

Tasks:

1. Add collapsed/expanded states with a compact preview.
2. Make focus state obvious.
3. Keep terminal card height constrained and scrollable.
4. Ensure close/collapse does not kill the process.
5. Verify Claude, Codex, and shell targets.
6. Add focused tests for store state and component behavior where practical.

Verification:

- `npm.cmd run typecheck`
- `npm.cmd test`
- Manual Studio smoke test with a prompt requiring input.

## Non-Goals

- Do not remove the full Pathly terminal.
- Do not implement split panes inside the chat card.
- Do not create a second PTY process for the mini terminal.
