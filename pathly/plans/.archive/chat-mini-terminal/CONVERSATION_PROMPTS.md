# Conversation Prompts

## Conversation 1 - Build Interactive Mini Terminal Core

Implement the interactive mini terminal card for Conductor chat.

Start from these files:

- `studio/src/renderer/src/components/ChatPanel/index.tsx`
- `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx`
- `studio/src/renderer/src/components/ChatPanel/ChatInput.module.css`
- `studio/src/renderer/src/components/ChatPanel/MiniTerminalCard.tsx`
- `studio/src/renderer/src/components/ChatPanel/MiniTerminalCard.module.css`
- `studio/src/renderer/src/components/ChatPanel/OutputSnippet.tsx`
- `studio/src/renderer/src/components/Terminal/index.tsx`
- `studio/src/renderer/src/components/Terminal/PaneTabBar.tsx`
- `studio/src/renderer/src/components/Terminal/TerminalTabView.tsx`
- `studio/src/renderer/src/components/Terminal/types.ts`
- `studio/src/renderer/src/components/Terminal/xtermRegistry.ts`
- `studio/src/renderer/src/store/terminalStore.ts`
- `studio/src/renderer/src/lib/launchTerminal.ts`

Requirements:

- The mini terminal must attach to the same terminal tab id used by the full terminal.
- It must use xterm and write input through `window.pathly.terminal.write`.
- It must subscribe to `window.pathly.terminal.onData`.
- It must not kill or replace the bottom terminal.
- It must let users answer prompts directly inside the chat panel.
- Run `npm.cmd run typecheck` and `npm.cmd test`.

## Conversation 2 - Polish The Mini Terminal UX

Improve the mini terminal card after the core behavior works.

Requirements:

- Add a compact collapsed preview.
- Keep expanded height constrained.
- Add a clear focus/active state.
- Add or preserve an "open full terminal" action.
- Verify Claude, Codex, and shell targets.
- Run `npm.cmd run typecheck` and `npm.cmd test`.
