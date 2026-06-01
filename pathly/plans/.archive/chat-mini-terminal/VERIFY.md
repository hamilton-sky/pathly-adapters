RESULT: PASS

## Conversation 1 - Interactive Mini Terminal Core

Verified:

- Conductor creates background terminal tabs without revealing the full bottom terminal.
- `MiniTerminalCard` attaches to the same terminal tab id used by the full terminal.
- Terminal input is written through `window.pathly.terminal.write`.
- The full bottom terminal remains available.

## Conversation 2 - Polish Mini Terminal UX

Verified:

- Mini card supports peek/banner behavior.
- Focus state is visible.
- Opening the full terminal selects the same terminal tab.
- Hiding the mini card does not kill the process.

## Conversation 3 - Full Terminal Controls And Runtime Icons

Verified:

- Full terminal tab actions are always visible.
- X hides a terminal view while preserving the PTY.
- Bin kills the PTY, disposes the shared xterm, and removes the tab.
- The hamburger button opens/closes the right-side instance rail.
- The instance rail can focus/show, hide, and kill terminal instances.
- Shell, Claude, and Codex icons are shared across terminal tabs, instance rail,
  mini cards, launcher dropdown, and Conductor header.
- Shell/PowerShell activates the Conductor header dot when a shell tab exists.

## Commands

```text
npm.cmd run typecheck
EXIT: 0

npm.cmd test
EXIT: 0
```

Known test-suite warning: `useFlowFile.test.ts` still emits existing React
`act(...)` warnings. The tests pass.
